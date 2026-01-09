import datetime
from decimal import Decimal
from logging import Logger
from os import PathLike
from typing import Optional, Annotated, Union, Tuple, List

from antlr4.ParserRuleContext import ParserRuleContext
from antlr4.tree.Tree import ParseTreeVisitor
from fhir.resources.R4B.coding import Coding
from fhir.resources.R4B.elementdefinition import ElementDefinition
from fhir.resources.R4B.period import Period
from fhir.resources.R4B.quantity import Quantity
from fhir.resources.R4B.reference import Reference

from cohort_selection_ontology.core.generators.cql import (
    aggregate_cardinality_of_element_chain,
    aggregate_cardinality_using_element,
    select_element_compatible_with_cql_operations,
)
from cohort_selection_ontology.model.mapping.cql import (
    Component,
    ContextGroup,
    AttributeComponent,
    ReferenceGroup,
)

from common.model.structure_definition import StructureDefinitionSnapshot
from common.util.fhir.enums import FhirComplexDataType, FhirPrimitiveDataType
from common.util.fhir.fhirpath import fhirpath_filter_for_slice
from common.util.fhirpath import fhirpathParser, parse_expr
from common.util.fhirpath.fhirpathVisitor import fhirpathVisitor
from common.util.fhirpath.functions import (
    unsupported_fhirpath_expr,
    invalid_fhirpath_expr,
    get_symbol,
    get_path,
    join_fhirpath,
)
from common.util.functions import first
from common.util.log.functions import get_logger, get_class_logger
from common.util.model import field_names
from common.util.project import Project
from common.util.structure_definition.functions import (
    get_types_supported_by_element,
    get_profiles_with_base_definition,
    get_element_chain,
    get_slice_name,
)
from common.util.wrapper import dotdict

_logger = get_logger(__name__)


ElementChain = List[Tuple[StructureDefinitionSnapshot, ElementDefinition]]


ContextGroupDict = Annotated[
    dotdict,
    (
        "Raw pre-validated key value map from which a ContextGroup instance will be "
        "constructed. Serves as an intermediate"
    ),
]
ReferenceGroupDict = Annotated[
    dotdict,
    (
        "Raw pre-validated key value map from which a ReferenceGroup instance will be "
        "constructed. Serves as an intermediate"
    ),
]
AttributeComponentDict = Annotated[
    dotdict,
    (
        "Raw pre-validation key value map from which an AttributeComponent instance "
        "will be constructed. Serves as an intermediate"
    ),
]
ComponentDict = Union[ContextGroupDict, AttributeComponentDict]


def _split_pure_path(fhirpath: str) -> List[Tuple[str, Optional[str]]]:
    """
    Splits the given pure FHIRPath expression (e.g. containing only element navigation) into a list of element nodes

    :param fhirpath: FHIRPath expression
    :return: List of tuples containing the element name of the node and (optionally) the slice name
    """
    return [
        (
            (n, None)
            if not (slice_name := get_slice_name(n))
            else (n[: -len(slice_name) - 1], slice_name)
        )
        for n in fhirpath.split(".")
    ]


class AttributeResolutionContext:
    __logger: Logger = get_class_logger(__name__)

    __project: Project

    def __init__(self, project: Project):
        self.__project = project

    def resolve(
        self,
        attr_defining_expr: str,
        profile: str | StructureDefinitionSnapshot,
        module: str,
    ) -> Component:
        """
        Resolves the provided attribute defining (FHIRPath) expression into an attribute component tree

        :param attr_defining_expr: FHIRPath expression defining the attribute
        :param profile: `StructureDefinition` snapshot representing the data entity on which the attribute is defined
        :param module: Module containing criterion for which the attribute is defined
        :return: Attribute component tree
        """
        if isinstance(profile, str):
            profile = self.__project.package_manager.find(
                index_pattern={"url": profile}
            )
        return self._get_attribute_tree(attr_defining_expr, profile, module)

    def _get_components_from_invocation_expression(
        self,
        expr: fhirpathParser.InvocationExpressionContext,
        component: Optional[ComponentDict] = None,
    ) -> ComponentDict:
        pre_expr, path = get_path(expr)
        if component is not None:
            new_component = component.copy()
            new_component.path = join_fhirpath(path, component.path)
        elif path is not None:
            new_component = dotdict(
                {
                    "_type": AttributeComponent.__name__,
                    "type": None,  # Will be assigned during post-processing
                    "path": path,  # Will be assigned in when parent elements are processed
                    "cardinality": None,  # Will be assigned during post-processing
                    "values": [],
                }
            )
        else:
            new_component = None
        if pre_expr is None:
            if new_component is None:
                raise invalid_fhirpath_expr(
                    expr,
                    "Expression contains neither membership expression nor function "
                    "invocation",
                )
            return new_component
        else:
            return self._get_component_tree(
                pre_expr.getChild(0),
                self._get_components_from_function(pre_expr.getChild(2), new_component),
            )

    def _get_components_from_equality_expression(
        self,
        expr: fhirpathParser.EqualityExpressionContext,
    ) -> ComponentDict:
        term_expr: fhirpathParser.TermExpressionContext = expr.getChild(2)
        attr_component = dotdict(
            {
                "_type": AttributeComponent.__name__,
                "type": None,  # Will be assigned during post-processing
                "path": None,  # Will be assigned in when parent elements are processed
                "cardinality": None,  # Will be assigned during post-processing
                "values": [  # Will be translated into proper FHIR data type during post-processing
                    term_expr
                ],
            }
        )
        return self._get_component_tree(expr.getChild(0), attr_component)

    def _get_components_from_and_expression(
        self,
        expr: fhirpathParser.AndExpressionContext,
    ) -> ContextGroupDict:
        right = self._get_component_tree(expr.getChild(2))
        match expr.getChild(0):
            case fhirpathParser.AndExpressionContext() as aec:
                left = self._get_components_from_and_expression(aec)
            case _ as other:
                left = self._get_component_tree(other)
        return dotdict(
            {
                "_type": ContextGroup.__name__,
                "path": None,  # Will be assigned in when parent elements are processed
                "components": [left, right],
            }
        )

    def _get_components_from_function_parameters(
        self,
        expr: fhirpathParser.ParamListContext | None,
    ) -> list[ComponentDict]:
        if expr is None:
            return []
        match expr.getChild(0):
            case (
                fhirpathParser.AndExpressionContext() as and_expr
            ):  # path.to.value = <value> and path.to.other.value.exists() and ...
                return [self._get_components_from_and_expression(and_expr)]
            case (
                fhirpathParser.EqualityExpressionContext() as eq_expr
            ):  # path.to.value = <value>
                return [self._get_components_from_equality_expression(eq_expr)]
            case (
                fhirpathParser.InvocationExpressionContext() as inv_expr
            ):  # path.to.value.exists(...)
                return [self._get_components_from_invocation_expression(inv_expr)]
            case _ as c:
                raise unsupported_fhirpath_expr(
                    c,
                    ["and expression", "equality expression", "invocation expression"],
                )

    def _get_components_from_function(
        self,
        expr: fhirpathParser.FunctionInvocationContext,
        component: Optional[ComponentDict] = None,
    ) -> ComponentDict:
        try:
            # FunctionInvocationContext -> FunctionContext
            func_expr: fhirpathParser.FunctionContext = expr.function()
            assert isinstance(
                func_expr, fhirpathParser.FunctionContext
            ), "Expression contains no function"
        except Exception as exc:
            raise unsupported_fhirpath_expr(expr, "function invocation", exc)

        match get_symbol(func_expr.getChild(0)):
            case "where":
                # if component is None:
                #    raise invalid_fhirpath_expr(
                #        func_expr,
                #        "Function 'where' should not terminate an expression",
                #    )
                cs = self._get_components_from_function_parameters(
                    func_expr.paramList()
                )
                cs.append(component)
                component = dotdict(
                    {
                        "_type": ContextGroup.__name__,
                        "path": None,  # Will be assigned in when parent elements are processed
                        "components": cs,
                    }
                )
            case "exists":
                if component is not None:
                    raise invalid_fhirpath_expr(
                        func_expr,
                        "Function 'exists' returns a boolean value and thus should "
                        "terminate the expression",
                    )
                match self._get_components_from_function_parameters(
                    func_expr.paramList()
                ):
                    case [c]:
                        component = c
                    case _ as cs:
                        component = dotdict(
                            {
                                "_type": ContextGroup.__name__,
                                "path": None,  # Will be assigned in when parent elements are processed
                                "components": cs,
                            }
                        )
            case "ofType":
                if component is not None:
                    raise invalid_fhirpath_expr(
                        expr,
                        "Function invocation 'ofType' with trailing expression is "
                        "currently not supported",
                    )
                else:
                    component = dotdict(
                        {
                            "_type": AttributeComponent.__name__,
                            "type": get_symbol(func_expr.paramList()),
                            "path": None,  # Will be assigned in when parent elements are processed
                            "cardinality": None,  # Will be assigned during post-processing
                            "values": [],  # Will be translated into proper FHIR data type during post-processing
                        }
                    )
            case "resolve":
                if component is not None:
                    child = component
                    # TODO: For now we will only support references as values of attributes and not their resolution in
                    #       fixed parts of the attribute selection
                    # component = dotdict(
                    #    {
                    #        "_type": ReferenceGroup.__name__,
                    #        "type": None,
                    #        "path": None,
                    #        "components": [child],
                    #    }
                    # )
                    component = dotdict(
                        {
                            "_type": AttributeComponent.__name__,
                            "type": "Reference",
                            "path": None,
                            "values": [child],
                        }
                    )
                else:
                    component = dotdict(
                        {
                            "_type": AttributeComponent.__name__,
                            "type": "Reference",
                            "cardinality": None,
                            "values": [],
                        }
                    )
            case _:
                raise unsupported_fhirpath_expr(
                    func_expr,
                    [
                        "where function expression",
                        "exists function expression",
                        "ofType function expression",
                        "resolve function expression",
                    ],
                )

        # return _get_component_tree(expr.getChild(0), component)
        return component

    def _get_components_from_term_expression(
        self,
        expr: fhirpathParser.TermExpressionContext,
        component: Optional[ComponentDict] = None,
    ) -> ComponentDict:
        invoc = expr.term().invocation()
        match invoc:
            case fhirpathParser.FunctionInvocationContext() as fic:
                component = self._get_components_from_function(fic, component)
            case _ as ec:
                symbol = get_symbol(ec)
                if component is None:
                    return dotdict(
                        {
                            "_type": AttributeComponent.__name__,
                            "type": None,
                            "path": symbol,
                            "cardinality": None,
                            "values": [],
                        }
                    )
                component["path"] = (
                    f"{symbol}.{component.path}"
                    if component.path is not None
                    else symbol
                )
        return component

    def _enrich_reference_typed_tree(
        self,
        tree: ReferenceGroupDict,
        element: ElementDefinition,
        module: str,
    ) -> ReferenceGroup:
        ref_type = first(
            get_types_supported_by_element(element), lambda x: x.code == "Reference"
        )
        target_profiles = ref_type.targetProfile
        if target_profiles and len(target_profiles) == 1:
            profiles = [
                t
                for tp in target_profiles
                for t in get_profiles_with_base_definition(
                    self.__project.input.cso / "modules", tp
                )
            ]
            if len(profiles) == 1:
                (referenced_profile, _) = profiles[0]
                res_type = referenced_profile.type
                return ReferenceGroup(
                    type=res_type,
                    path=tree.path,
                    components=[
                        self._enrich_tree_with_types_and_values(
                            c, referenced_profile, module, res_type
                        )
                        for c in tree.components
                    ],
                )
            else:
                raise Exception(
                    f"Unsupported number of resolved target profiles in referencing element '{element.id}' "
                    f"[expected=1, actual={len(profiles)}, profiles={profiles}]"
                )
        else:
            raise Exception(
                f"Unsupported number of target profiles in referencing element '{element.id}' "
                f"[expected=1, actual={len(target_profiles)}]"
            )

    def _enrich_coding_typed_tree(
        self, tree: ContextGroupDict, chain: ElementChain
    ) -> AttributeComponent:
        coding = Coding()
        for c in tree.components:
            match c.path:
                case "system":
                    coding.system = get_symbol(c["values"][0])
                case "code":
                    coding.code = get_symbol(c["values"][0])
                case "display":
                    coding.display = get_symbol(c["values"][0])
                case _:
                    _logger.warning(
                        f"Element path '{c.path}' is not supported for FHIR datatype 'Coding' => Skipping"
                    )
        return AttributeComponent(
            type=FhirComplexDataType.CODING,
            path=tree.path,
            cardinality=aggregate_cardinality_of_element_chain(chain),
            values=[coding],
        )

    def _enrich_quantity_tree(
        self, tree: ContextGroupDict, chain: ElementChain
    ) -> AttributeComponent:
        quantity = Quantity()
        for c in tree.components:
            match c.path:
                case "value":
                    quantity.value = get_symbol(c["values"][0])
                case "unit":
                    quantity.unit = get_symbol(c["values"][0])
                case "system":
                    quantity.system = get_symbol(c["values"][0])
                case "code":
                    quantity.code = get_symbol(c["values"][0])
        return AttributeComponent(
            type=FhirComplexDataType.QUANTITY,
            path=tree.path,
            cardinality=aggregate_cardinality_of_element_chain(chain),
            values=[quantity],
        )

    def _enrich_literal_quantity_tree(
        self, tree: AttributeComponentDict, chain: ElementChain
    ) -> AttributeComponent:
        if tree["values"]:
            expr: fhirpathParser.LiteralTermContext = tree["values"][0]
            qc: fhirpathParser.QuantityContext = expr.literal().quantity()
            quantity = Quantity(
                system="http://unitsofmeasure.org",
                code=get_symbol(qc.unit()),
                value=get_symbol(qc.NUMBER()),
            )
        else:
            quantity = None
        return AttributeComponent(
            type=FhirComplexDataType.QUANTITY,
            path=tree.path,
            cardinality=aggregate_cardinality_of_element_chain(chain),
            values=[quantity] if quantity else [],
        )

    def _parse_temporal_literal(
        self, literal: str, fhir_type: FhirPrimitiveDataType
    ) -> datetime.time | datetime.datetime | datetime.date:
        v = literal.lstrip("@")
        match fhir_type:
            case FhirPrimitiveDataType.TIME:
                return datetime.time.fromisoformat(v)
            case FhirPrimitiveDataType.DATE_TIME | FhirPrimitiveDataType.INSTANT:
                return datetime.datetime.fromisoformat(v)
            case FhirPrimitiveDataType.DATE:
                return datetime.date.fromisoformat(v)
            case _:
                raise ValueError(f"Type '{fhir_type}' is not a FHIR temporal type")

    def _enrich_period_tree(
        self, tree: ContextGroupDict, chain: ElementChain
    ) -> AttributeComponent:
        period = Period()
        for c in tree.components:
            match c.path:
                case "start":
                    period.start = self._parse_temporal_literal(
                        get_symbol(c["values"][0]), FhirPrimitiveDataType.DATE_TIME
                    )
                case "end":
                    period.end = self._parse_temporal_literal(
                        get_symbol(c["values"][0]), FhirPrimitiveDataType.DATE_TIME
                    )
                case _:
                    raise Exception(
                        f"Element path '{c}' is not supported for FHIR datatype 'Period'"
                    )
        return AttributeComponent(
            type=FhirComplexDataType.PERIOD,
            path=tree.path,
            cardinality=aggregate_cardinality_of_element_chain(chain),
            values=[period],
        )

    def _enrich_reference_typed_attribute(
        self,
        tree: AttributeComponentDict,
        chain: ElementChain,
        module: str,
    ) -> AttributeComponent:
        _, element = chain[-1]
        ref_type = first(
            get_types_supported_by_element(element), lambda x: x.code == "Reference"
        )
        target_profiles = ref_type.targetProfile
        if target_profiles and len(target_profiles) >= 1:
            module_dir_path = self.__project.input.cso / "modules" / module
            profiles = [
                t
                for tp in target_profiles
                for t in get_profiles_with_base_definition(module_dir_path, tp)
            ]
            types = {p.type for p, _ in profiles}
            return AttributeComponent(
                type=FhirComplexDataType.REFERENCE,
                path=tree.path,
                cardinality=aggregate_cardinality_of_element_chain(chain),
                values=[Reference(type=t) for t in types] if types else [Reference()],
            )
        else:
            raise Exception(
                f"Element '{element.get('id')}' does not support type 'Reference' or target profiles"
            )

    def _enrich_coding_typed_attribute(self, chain: ElementChain) -> AttributeComponent:
        snapshot, element = chain[-1]
        (compatible_element, _) = select_element_compatible_with_cql_operations(
            element, snapshot
        )
        return AttributeComponent(
            type=get_types_supported_by_element(compatible_element)[0].code,
            path=compatible_element.path,
            cardinality=aggregate_cardinality_of_element_chain(chain[:-1])
            * aggregate_cardinality_using_element(element, snapshot),
            values=[],
        )

    def _enrich_primitive_typed_tree(
        self,
        tree: AttributeComponentDict,
        chain: ElementChain,
        datatype: FhirPrimitiveDataType,
    ) -> AttributeComponent:
        match datatype:
            case FhirPrimitiveDataType.BOOLEAN:
                values = [bool(get_symbol(c)) for c in tree["values"]]
            case (
                FhirPrimitiveDataType.INTEGER
                | FhirPrimitiveDataType.POSITIVE_INT
                | FhirPrimitiveDataType.UNSIGNED_INT
            ):
                values = [int(get_symbol(c)) for c in tree["values"]]
            case FhirPrimitiveDataType.DECIMAL:
                values = [Decimal(get_symbol(c)) for c in tree["values"]]
            case (
                FhirPrimitiveDataType.DATE
                | FhirPrimitiveDataType.TIME
                | FhirPrimitiveDataType.DATE_TIME
                | FhirPrimitiveDataType.INSTANT
            ):
                values = [
                    self._parse_temporal_literal(get_symbol(c), datatype)
                    for c in tree["values"]
                ]
            case _:
                values = [get_symbol(c) for c in tree["values"]]
        return AttributeComponent(
            type=tree.type,
            path=tree.path,
            cardinality=aggregate_cardinality_of_element_chain(chain),
            values=values,
        )

    def _get_component_tree(
        self, expr: ParserRuleContext, component: Optional[ComponentDict] = None
    ) -> ComponentDict:
        match expr:
            case fhirpathParser.EntireExpressionContext() as full_expr:
                if component is not None:
                    _logger.warning(
                        "Provided tree already represents entire FHIRPath expression => Ignoring additionally "
                        "provided components"
                    )
                return self._get_component_tree(full_expr.expression())
            case fhirpathParser.EqualityExpressionContext() as eec:
                if component is not None:
                    raise invalid_fhirpath_expr(
                        eec,
                        "Trailing expressions are not supported for boolean expressions",
                    )
                return self._get_components_from_equality_expression(eec)
            case fhirpathParser.InvocationExpressionContext() as iec:
                return self._get_components_from_invocation_expression(iec, component)
            case fhirpathParser.TermExpressionContext() as tec:
                return self._get_components_from_term_expression(tec, component)
            case _ as unexpected:
                raise unsupported_fhirpath_expr(
                    unexpected,
                    [
                        "equality expression",
                        "invocation expression",
                        "term expression",
                    ],
                )

    def _expand_slices(
        self,
        tree: Component,
        snapshot: StructureDefinitionSnapshot,
        module: str,
        project: Project,
    ) -> Component:
        leaf = tree
        nodes = tree.path.split(".")
        path_split = _split_pure_path(tree.path)
        for idx, t in enumerate(reversed(path_split)):
            match t:
                case (n, None):
                    leaf.path = f"{n}.{leaf.path}"
                case (_, _):
                    slice_def_elem_def = snapshot.get_element_by_id(
                        ".".join(nodes[: len(path_split) - idx])
                    )
                    fp_filter = fhirpath_filter_for_slice(
                        slice_def_elem_def, snapshot, project.package_manager
                    )
                    filter_tree = self._get_attribute_tree(
                        f"{slice_def_elem_def.path}.{fp_filter}", snapshot, module
                    )
                    leaf = ContextGroup(
                        path=slice_def_elem_def.path, components=[filter_tree, leaf]
                    )
        return leaf

    def _enrich_tree_with_types_and_values(
        self,
        tree: ComponentDict,
        profile_snapshot: StructureDefinitionSnapshot,
        module: PathLike[str] | str,
        _parent_path: Optional[str] = None,
    ) -> Component:
        """
        Uses information in the profile snapshot to replace preliminarily assigned values in all leaf nodes (e.g.
        `AttributeComponent` objects) with suitable FHIR data types and assign type information

        :param tree: Attribute component tree to enrich
        :param profile_snapshot: Profile snapshot on which the attributes are based
        :param module: Module to start search for profiles in
        :param _parent_path: Parent path to the elements of the given tree. Does not have to be provided when passing full
                             tree
        :return: Enriched profile tree
        """
        base_path = tree.path if not _parent_path else f"{_parent_path}.{tree.path}"
        # modules_dir_path = project.input.cso / "modules"
        # element = get_element_defining_elements(
        #    profile_snapshot, base_path, module, modules_dir_path
        # )[-1]
        element = profile_snapshot.get_element_by_id(base_path)
        chain = get_element_chain(base_path, profile_snapshot, module, self.__project)
        types = get_types_supported_by_element(element)
        if len(types) == 1:
            t = types[0]
            match tree:
                case {"_type": ContextGroup.__name__} as cg:
                    match t.code:
                        case "Coding":
                            return self._enrich_coding_typed_tree(cg, chain)
                        case "Quantity":
                            return self._enrich_quantity_tree(cg, chain)
                        case "Period":
                            return self._enrich_period_tree(cg, chain)
                        case _:
                            return ContextGroup(
                                path=cg.path,
                                components=[
                                    self._enrich_tree_with_types_and_values(
                                        c, profile_snapshot, module, base_path
                                    )
                                    for c in cg.components
                                ],
                            )
                case {"_type": AttributeComponent.__name__} as ac:
                    if t.code in FhirPrimitiveDataType:
                        return self._enrich_primitive_typed_tree(ac, chain, t.code)
                    elif t.code in FhirComplexDataType:
                        match t.code:
                            case "Quantity":
                                return self._enrich_literal_quantity_tree(ac, chain)
                            case "Reference":
                                return self._enrich_reference_typed_attribute(
                                    ac, chain, module
                                )
                            case "Coding":
                                return self._enrich_coding_typed_attribute(chain)
                            case _:
                                raise Exception(
                                    f"Unsupported complex datatype '{t.code}' of element '{element.id}' represented by AttributeComponent instance"
                                )
                    else:
                        raise Exception(
                            f"Unknown datatype '{t.code}' of element '{element.id}' represented by AttributeComponent instance"
                        )
                case {"_type": ReferenceGroup.__name__} as rg:
                    return self._enrich_reference_typed_tree(rg, chain[-1][1], module)
                case _ as x:
                    raise KeyError(
                        f"Dictionary has to match either ContextGroup or AttributeComponent structure [actual={field_names(x)}]"
                    )
        else:
            raise Exception(
                f"Element '{element.id}' supports {'multiple' if types else 'no'} types which is currently not supported"
            )

    def _get_attribute_tree(
        self,
        attribute_defining_id: str,
        snapshot: StructureDefinitionSnapshot,
        module: PathLike[str] | str,
    ) -> ContextGroup | AttributeComponent:
        """
        Parses the provided attribute defining ID and generates its associated component tree representation

        :param attribute_defining_id: FHIRPath-like expression defining the attribute
        :param snapshot: `StructureDefinition`-typed profile snapshot representing the starting point for the component tree
                         resolution
        :param module: Module to which the snapshot belongs
        :return: Component tree of the attribute
        """
        parsed_expr = parse_expr(attribute_defining_id)
        preprocessed_tree = self._get_component_tree(parsed_expr)
        return self._enrich_tree_with_types_and_values(
            preprocessed_tree, snapshot, module
        )
