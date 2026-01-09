from functools import cached_property
from typing import Optional, TypeVar, Any, Self, Tuple, List, Literal, Annotated

from antlr4.tree.Tree import ParseTreeVisitor
from fhir.resources.R4B.coding import Coding
from fhir.resources.R4B.quantity import Quantity
import decimal

from pydantic import BaseModel, Field

from cohort_selection_ontology.model.mapping import SimpleCardinality
from cohort_selection_ontology.model.mapping.cql import (
    Component,
    AttributeComponent,
    ContextGroup,
)
from common.exceptions.profile import NoSuchElemDefError
from common.model.structure_definition import IndexedStructureDefinition
from common.util.fhirpath import fhirpathParser, parse_expr
from common.util.log.functions import get_logger
from common.util.project import Project
from datetime import date, time, datetime


_logger = get_logger(__name__)


def get_fhirpath_expression_root_node(
    tree: fhirpathParser.ExpressionContext,
) -> fhirpathParser.ExpressionContext:
    """
    Navigate down the left side of the parse tree to arrive at and return the expression node representing the root node
    of the FHIRPath expression

    :param tree: Parse tree to find the FHIRPath root node of
    :return: FHIRPath root node
    """
    child = tree
    while isinstance(child, fhirpathParser.InvocationExpressionContext):
        child = child.getChild(0)
    return child


class NoOpComponent(Component):
    path = Literal["$this"]

    def __add__(self, other: Component) -> Component:
        return other

    def and_then(self, *cs: Component) -> Component:
        match cs:
            case []:
                return self
            case [c]:
                return c
            case _:
                return ContextGroup(path="$this", components=cs)


VT = TypeVar("VT", bound="FhirContextVisitor", covariant=True)


class FhirContextVisitor(BaseModel, ParseTreeVisitor):
    project: Project
    profile: IndexedStructureDefinition
    rel_id: str = "$this"
    vis_ctx: Optional[Self] = None

    @classmethod
    def from_ctx(cls, obj: VT, **kwargs) -> Self:
        """
        Builds an instance of this class based on the provided visitor that serves as its parent context

        :param obj: Parent (calling) visitor
        :param kwargs: Provided field values are assigned to the new instances matching fields instead of taking them
                       from the parent visitor
        :return: New instance
        """
        project = kwargs["project"] if "project" in kwargs else obj.project
        profile = kwargs["profile"] if "profile" in kwargs else obj.profile
        rel_id = kwargs["rel_id"] if "rel_id" in kwargs else "$this"
        return cls(project=project, profile=profile, rel_id=rel_id, vis_ctx=obj)

    @cached_property
    def abs_id(self) -> str:
        """
        Returns absolute ID from Resource root instead of relative ID to parent visitor context contained in the
        `rel_id` field

        :return: Absolute ID to Resource root
        """
        if not self.vis_ctx:
            return self.rel_id
        elif self.rel_id == "$this":
            return self.vis_ctx.abs_id
        else:
            return self.vis_ctx.abs_id + "." + self.rel_id

    @cached_property
    def rel_path(self) -> str:
        return ".".join([node.split(":")[0] for node in self.rel_id.split(".")])

    @cached_property
    def abs_path(self) -> str:
        """
        Returns absolute path from Resource root instead of relative path to parent visitor context contained in the
        `path` field

        :return: Absolute path to Resource root
        """
        if not self.vis_ctx:
            return self.rel_path
        elif self.rel_path == "$this":
            return self.vis_ctx.abs_path
        else:
            return self.vis_ctx.abs_path + "." + self.rel_path

    @cached_property
    def data_types(self) -> List[Tuple[str, List[str]]]:
        """
        Returns data types supported by the element definition as identified by the `abs_path` fields value

        :return: Supported data types element definition the visitor targets
        """
        if self.path == "$this":
            return self.vis_ctx.data_types
        if elem_def := self.profile.get_element_by_id(self.abs_path):
            match elem_def.type:
                case []:
                    return []
                case _ as ts:
                    return [
                        (
                            t.code,
                            (
                                t.targetProfile
                                if t.code == "Reference" or t.code == "canonical"
                                else t.profile
                            ),
                        )
                        for t in ts
                    ]
        else:
            raise NoSuchElemDefError(self.profile, id=self.abs_path)


class UnitVisitor(ParseTreeVisitor):
    def visit(self, tree) -> str:
        if not isinstance(tree, fhirpathParser.UnitContext):
            raise ValueError(
                f"Unsupported type [expected=QuantityContext, actual={type(tree)}]"
            )
        match tree.getText():
            case "year" | "years":
                return "a"
            case "month" | "months":
                return "mo"
            case "week" | "weeks":
                return "wk"
            case "day" | "days":
                return "d"
            case "hour" | "hours":
                return "h"
            case "minute" | "minutes":
                return "min"
            case "second" | "seconds":
                return "s"
            case "millisecond" | "milliseconds":
                return "ms"
            case _ as unit_str:
                return unit_str


class LiteralVisitor(ParseTreeVisitor):
    def visit(self, tree) -> Any:
        if not isinstance(tree, fhirpathParser.LiteralContext):
            raise ValueError(f"Unsupported type [type={type(tree)}]")
        match tree:
            case fhirpathParser.BooleanLiteralContext() as blc:
                match blc.getText():
                    case "true":
                        return True
                    case "false":
                        return False
            case fhirpathParser.StringLiteralContext() as slc:
                return slc.STRING.getText()
            case fhirpathParser.NumberLiteralContext() as nlc:
                num_str = nlc.NUMBER.getText()
                return float(num_str) if "." else int(num_str)
            case fhirpathParser.LongNumberLiteralContext as lnlc:
                # Drop 'L' at the end of the token string
                return int(lnlc.LONGNUMBER.getText()[:-1])
            case fhirpathParser.DateLiteralContext as dlc:
                return date.fromisoformat(dlc.DATE.getText())
            case fhirpathParser.DateTimeLiteralContext as dtlc:
                return datetime.fromisoformat(dtlc.DATETIME.getText())
            case fhirpathParser.TimeLiteralContext as tlc:
                return time.fromisoformat(tlc.TIME.getText())
            case fhirpathParser.QuantityLiteralContext as qlc:
                qc = qlc.quantity()
                return Quantity(
                    value=decimal.Decimal(qc.NUMBER.getText()),
                    code=UnitVisitor().visit(qc.unit()),
                )
            case _:
                raise NotImplementedError(f"Unsupported term type [type={tree}]")


class TermVisitor(FhirContextVisitor):
    def visit(self, tree):
        if not isinstance(tree, fhirpathParser.TermContext):
            raise ValueError(
                f"Unsupported type [expected=TermContext, actual={type(tree)}]"
            )
        match tree:
            case fhirpathParser.InvocationTermContext() as itc:
                return InvocationVisitor.from_ctx(self).visit(itc.invocation())
            case fhirpathParser.LiteralTermContext() as ltc:
                return LiteralVisitor().visit(ltc.literal())
            case _:
                raise NotImplementedError(f"Unsupported term type [type={tree}]")


class FunctionVisitor(FhirContextVisitor):
    def visit(self, tree: fhirpathParser.FunctionContext) -> Component:
        if not isinstance(tree, fhirpathParser.FunctionContext):
            raise ValueError(
                "Unsupported type [expected=TermContext, actual={type(tree)}]"
            )
        match tree.identifier().getText():
            case "where" | "exists":
                return self.__handle_criteria(tree.paramList())
            case "ofType":
                return self.__handle_type_filter(tree.paramList())
            case _ as fnc:
                raise NotImplementedError(f"Unsupported function '{fnc}'")

    def __handle_criteria(
        self, param_list: fhirpathParser.ParamListContext
    ) -> Component:
        sub_tree = ExpressionVisitor.from_ctx(self).visit(param_list.expression(0))
        match self.data_types:
            case [dt]:
                match dt[0]:
                    case "Coding":
                        return self.__handle_coding(sub_tree)
                    case _:
                        return sub_tree
            case _:
                return sub_tree

    def __handle_coding(self, tree: Component) -> AttributeComponent:
        # TODO: Implement handling of multiple values via OrExpressionContext
        match tree:
            case AttributeComponent() as ac:
                return ac
            case ContextGroup() as cg:
                coding = Coding()
                for c in cg.components:
                    match c.path:
                        case "system":
                            coding.system = c.values[0]
                        case "code":
                            coding.code = c.values[0]
                        case "display":
                            coding.display = c.values[0]
                return AttributeComponent(
                    path=cg.path,
                    type="Coding",
                    cardinality=self.profile.get_aggregated_max_cardinality(
                        self.abs_path
                    ),
                    operator="=",
                    values=[coding],
                )
            case _:
                raise ValueError(
                    f"Unexpected component type for data type 'Coding' [expected=AttributeComponent|ContextGroup, "
                    f"actual={type(tree)}]"
                )

    def __handle_type_filter(
        self, param_list: fhirpathParser.ParamListContext
    ) -> Component:
        type_identifier = param_list.getText()
        if ts := list(
            filter(lambda dt: dt[0] == type_identifier, self.vis_ctx.data_types)
        ):
            # TODO: Check if there is a cleaner solution to for propagating the type filter information
            # Update data types of parent visitor context since it will be used as a context for subsequent visitors.
            # ATM the parent visitor context should always be an `InvocationVisitor` instance
            self.vis_ctx.__dict__["data_types"] = ts
            return NoOpComponent()


class InvocationVisitor(FhirContextVisitor):
    def visit(self, tree):
        if not isinstance(tree, fhirpathParser.InvocationContext):
            raise ValueError(
                f"Unsupported type [expected=InvocationContext, actual={type(tree)}]"
            )
        match tree:
            case fhirpathParser.MemberInvocationContext() as mic:
                return self.visit_member_invocation(mic)
            case fhirpathParser.FunctionInvocationContext() as fic:
                return self.visit_function_invocation(fic)
            case fhirpathParser.ThisInvocationContext():
                return self.visit_this_invocation()
            case _:
                raise NotImplementedError(f"Unsupported invocation [type={type(tree)}]")

    def visit_member_invocation(
        self, ctx: fhirpathParser.MemberInvocationContext
    ) -> ContextGroup:
        identifier = ctx.identifier().getText()
        # Resolve slice
        if ":" in identifier:
            resolve
        return ContextGroup(path=self.path + "." + ctx.identifier().getText())

    def visit_function_invocation(self, ctx: fhirpathParser.FunctionInvocationContext):
        return FunctionVisitor.from_ctx(self).visit(ctx.function())

    def visit_this_invocation(self) -> ContextGroup:
        return ContextGroup(path="$this")


class ExpressionVisitor(FhirContextVisitor):
    def visit(self, tree) -> Component:
        if not isinstance(tree, fhirpathParser.ExpressionContext):
            raise ValueError(
                f"Unsupported type [expected=InvocationContext, actual={type(tree)}]"
            )
        match tree:
            case fhirpathParser.TermExpressionContext() as term_ec:
                return TermVisitor.from_ctx(self).visit(term_ec.term())
            case fhirpathParser.InvocationExpressionContext() as inv_ec:
                return self.visit_invocation_expression(inv_ec)
            case fhirpathParser.TypeExpressionContext() as type_ec:
                return self.visit_type_of_expression(type_ec)
            case fhirpathParser.EqualityExpressionContext() as eq_ec:
                return self.visit_equality_expression(eq_ec)
            case fhirpathParser.AndExpressionContext() as and_ec:
                return self.visit_and_expression(and_ec)
            case _:
                raise NotImplementedError(
                    f"Unsupported expression type [type={type(tree)}]"
                )

    def visit_invocation_expression(
        self, tree: fhirpathParser.InvocationExpressionContext
    ) -> Component:
        # Since we assume chained invocations to be path traversals, the parse tree should be traversed down the
        # left-most branch to arrive at the root node of the traversal. This should only be done one time once a new
        # expression parse tree is encountered
        if not isinstance(tree.parentCtx, fhirpathParser.InvocationExpressionContext):
            tree = get_fhirpath_expression_root_node(tree)
        # Invocation expressions are traversed according to the hierarchy of elements in the resource and not nodes in
        # the parse tree. As a consequence the parent context of the parse (sub)tree is treated as translated into a
        # child in the attribute component tree
        vis = InvocationVisitor.from_ctx(self)
        c = vis.visit(tree.invocation())
        c_vis = ExpressionVisitor.from_ctx(vis)
        cc = c_vis.visit(tree.parentCtx)
        match self.data_types:
            case [dt] if dt[0] == "CodeableConcept":
                # The equivalence operator in CQL can be leveraged to check if codings represent a concept. As such we
                # can "lift" Coding comparisons onto the CodeableConcept element level
                match c_vis.data_types:
                    case [dt] if dt[0] == "Coding":
                        if isinstance(cc, AttributeComponent):
                            cc.type = "CodeableConcept"
                            cc.path = "$this"
                            cc.cardinality = (
                                self.profile.get_aggregated_max_cardinality(
                                    self.abs_path
                                )
                            )
        return c.and_then(cc)

    def visit_type_of_expression(
        self, tree: fhirpathParser.TypeExpressionContext
    ) -> Component:
        c = ExpressionVisitor.from_ctx(self).visit(tree.parentCtx)
        match c:
            case AttributeComponent() as ac:
                ac.type = tree.typeSpecifier().toString()
            case _:
                _logger.debug(
                    f'Ignored type expression "{tree.toString()}" @ {tree.start}:{tree.stop}'
                )
        return c

    def visit_equality_expression(
        self, tree: fhirpathParser.EqualityExpressionContext
    ) -> AttributeComponent:
        if not isinstance(
            rh := tree.expression(1), fhirpathParser.TermExpressionContext
        ):
            raise NotImplementedError(
                f"Unsupported right hand expression type [type={type(rh)}]. Only term "
                f"expressions are supported ATM"
            )
        elem_def = self.profile.get_element_by_id(self.abs_path)
        if not elem_def:
            raise NoSuchElemDefError(self.profile, id=self.abs_path)
        elem_types = elem_def.type if elem_def.type else []
        if len(elem_types) != 1:
            raise ValueError(
                f"Ambiguous typing in element definition '{self.path}' in profile '{self.profile.url}'. "
                f"Expected exactly one type but found {len(elem_types)}"
            )
        max_card = self.profile.get_aggregated_max_cardinality(elem_def.id)
        return AttributeComponent(
            type=elem_types[0],
            path="$this",
            cardinality=(
                SimpleCardinality.MANY
                if max_card == "*" or max_card > 1
                else SimpleCardinality.SINGLE
            ),
            operator=tree.getChild(1).getText(),
            values=[TermVisitor.from_ctx(self).visit(tree.expression(1))],
        )

    def visit_and_expression(
        self, tree: fhirpathParser.AndExpressionContext
    ) -> Component:
        lh = ExpressionVisitor.from_ctx(self).visit(tree.expression(0))
        rh = ExpressionVisitor.from_ctx(self).visit(tree.expression(1))
        return lh + rh


class CQLAttributeResolutionVisitor(FhirContextVisitor):
    path: Annotated[
        str, Field(init=False, default_factory=lambda data: data["profile"].type)
    ]
    vis_ctx: Annotated[Optional[FhirContextVisitor], Field(init=False)] = None

    def visit(self, tree: fhirpathParser.EntireExpressionContext) -> Component:
        if not isinstance(tree, fhirpathParser.EntireExpressionContext):
            raise ValueError(
                f"Unsupported type [expected=EntireExpressionContext, actual={type(tree)}]"
            )
        attr_tree = ExpressionVisitor.from_ctx(self).visit(tree.expression())
        return self.__resolve_slices(attr_tree)

    def __resolve_slices(self, tree: Component) -> Component:
        pass


class CQLAttributeResolver:
    def __init__(self, profile: IndexedStructureDefinition, project: Project):
        self.__profile = profile
        self.__project = project

    def resolve(self, fhirpath: str) -> Component:
        expr = parse_expr(fhirpath)
        return CQLAttributeResolutionVisitor(
            profile=self.__profile, project=self.__project
        ).visit(expr)
