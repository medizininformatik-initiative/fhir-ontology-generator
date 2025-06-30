from datetime import datetime, date, time
from decimal import Decimal
from typing import Optional

from antlr4.ParserRuleContext import ParserRuleContext
from fhir.resources.R4B.coding import Coding
from fhir.resources.R4B.period import Period
from fhir.resources.R4B.quantity import Quantity

from cohort_selection_ontology.core.generators.cql.generator import (
    aggregate_cardinality_using_element,
)
from cohort_selection_ontology.model.mapping.cql import (
    Component,
    ContextGroup,
    AttributeComponent,
)
from cohort_selection_ontology.util.fhir.structure_definition import (
    get_element_from_snapshot_by_path,
)
from common.util.fhir.enums import FhirComplexDataType, FhirPrimitiveDataType
from common.util.fhir.structure_definition import (
    Snapshot,
    get_types_supported_by_element,
    ElementDefinitionDict,
    get_element_from_snapshot,
)
from common.util.fhirpath import fhirpathParser
from common.util.fhirpath.functions import (
    unsupported_fhirpath_expr,
    invalid_fhirpath_expr,
    get_symbol,
    get_path,
)
from common.util.log.functions import get_logger


_logger = get_logger(__name__)


def get_components_from_invocation_expression(
    expr: fhirpathParser.InvocationExpressionContext,
    component: Optional[Component] = None,
) -> Component:
    pre_expr, path = get_path(expr)
    if component is not None:
        component.path = path
    elif path is not None:
        component = AttributeComponent.model_construct(
            types=[],  # Will be assigned during post-processing
            path=path,  # Will be assigned in when parent elements are processed
            cardinality=None,  # Will be assigned during post-processing
            values=[],
        )
    if pre_expr is None:
        if component is None:
            raise invalid_fhirpath_expr(
                expr,
                "Expression contains neither membership expression nor function "
                "invocation",
            )
        return component
    else:
        return get_components_from_function(pre_expr, component)


def get_components_from_equality_expression(
    expr: fhirpathParser.EqualityExpressionContext,
) -> Component:
    term_expr: fhirpathParser.TermExpressionContext = expr.getChild(2)
    attr_component = AttributeComponent.model_construct(
        types=[],  # Will be assigned during post-processing
        path=None,  # Will be assigned in when parent elements are processed
        cardinality=None,  # Will be assigned during post-processing
        values=[  # Will be translated into proper FHIR data type during post-processing
            term_expr
        ],
    )
    return get_component_tree(expr.getChild(0), attr_component)


def get_components_from_and_expression(
    expr: fhirpathParser.AndExpressionContext,
) -> ContextGroup:
    right = get_component_tree(expr.getChild(2))
    match expr.getChild(0):
        case fhirpathParser.AndExpressionContext() as aec:
            left = get_components_from_and_expression(aec)
        case _ as other:
            left = get_component_tree(other)
    return ContextGroup.model_construct(
        path=None,  # Will be assigned in when parent elements are processed
        components=[left, right],
    )


def get_components_from_function_parameters(
    expr: fhirpathParser.ParamListContext,
) -> list[Component]:
    match expr.getChild(0):
        case (
            fhirpathParser.AndExpressionContext() as and_expr
        ):  # path.to.value = <value> and path.to.other.value.exists() and ...
            return [get_components_from_and_expression(and_expr)]
        case (
            fhirpathParser.EqualityExpressionContext() as eq_expr
        ):  # path.to.value = <value>
            return [get_components_from_equality_expression(eq_expr)]
        case (
            fhirpathParser.InvocationExpressionContext() as inv_expr
        ):  # path.to.value.exists(...)
            return [get_components_from_invocation_expression(inv_expr)]
        case _ as c:
            raise unsupported_fhirpath_expr(
                c, ["and expression", "equality expression", "invocation expression"]
            )


def get_components_from_function(
    expr: ParserRuleContext,
    component: Optional[Component] = None,
) -> Component:
    try:
        # ParserRuleContext (e.g. containing expression) -> FunctionInvocationContext -> FunctionContext
        func_expr: fhirpathParser.FunctionContext = expr.getChild(2).function()
        assert isinstance(
            func_expr, fhirpathParser.FunctionContext
        ), "Expression contains no function invocation as immediate right operand"
    except Exception as exc:
        raise unsupported_fhirpath_expr(expr, "function invocation", exc)

    match get_symbol(func_expr.getChild(0)):
        case "where":
            if component is None:
                raise invalid_fhirpath_expr(
                    func_expr,
                    "Function 'where' returns no boolean value and thus cannot "
                    "terminate expression",
                )
            cs = get_components_from_function_parameters(func_expr.paramList())
            cs.append(component)
            component = ContextGroup.model_construct(
                path=None,  # Will be assigned in when parent elements are processed
                components=cs,
            )
        case "exists":
            if component is not None:
                raise invalid_fhirpath_expr(
                    func_expr,
                    "Function 'exists' returns a boolean value and thus should "
                    "terminate the expression",
                )
            match get_components_from_function_parameters(func_expr.paramList()):
                case [c]:
                    component = c
                case _ as cs:
                    component = ContextGroup.model_construct(
                        path=None,  # Will be assigned in when parent elements are processed
                        components=cs,
                    )
        case "ofType":
            if component is not None:
                raise invalid_fhirpath_expr(
                    expr,
                    "Function invocation 'ofType' with trailing expression is "
                    "currently not supported",
                )
            else:
                component = AttributeComponent.model_construct(
                    types=[get_symbol(func_expr.paramList())],
                    path=None,  # Will be assigned in when parent elements are processed
                    cardinality=None,  # Will be assigned during post-processing
                    values=[],  # Will be translated into proper FHIR data type during post-processing
                )
        case _:
            raise unsupported_fhirpath_expr(
                func_expr, ["where function expression", "exists function expression"]
            )

    return get_component_tree(expr.getChild(0), component)


def get_components_from_term_expression(
    expr: fhirpathParser.TermExpressionContext, component: Component
) -> Component:
    symbol = get_symbol(expr.term().invocation())
    component.path = (
        f"{symbol}.{component.path}" if component.path is not None else symbol
    )
    return component


def get_component_tree(
    expr: ParserRuleContext, component: Optional[Component] = None
) -> Component:
    match expr:
        case fhirpathParser.EntireExpressionContext() as full_expr:
            return get_component_tree(full_expr.expression())
        case fhirpathParser.EqualityExpressionContext() as eec:
            if component is not None:
                raise invalid_fhirpath_expr(
                    eec,
                    "Trailing expressions are not supported for boolean expressions",
                )
            return get_components_from_equality_expression(eec)
        case fhirpathParser.InvocationExpressionContext() as iec:
            return get_components_from_invocation_expression(iec, component)
        case fhirpathParser.TermExpressionContext() as tec:
            return get_components_from_term_expression(tec, component)
        case _ as unexpected:
            raise unsupported_fhirpath_expr(
                unexpected,
                ["equality expression", "invocation expression", "term expression"],
            )


def _enrich_coding_tree(
    tree: ContextGroup, profile: Snapshot, element: ElementDefinitionDict
) -> AttributeComponent:
    coding = Coding()
    for c in tree.components:
        match c.path:
            case "system":
                coding.system = get_symbol(c.values[0])
            case "code":
                coding.code = get_symbol(c.values[0])
            case _:
                raise Exception(
                    f"Element path '{c}' is not supported for FHIR datatype 'Coding'"
                )
    return AttributeComponent(
        types=[FhirComplexDataType.CODING],
        path=tree.path,
        cardinality=aggregate_cardinality_using_element(element, profile),
        values=[coding],
    )


def _enrich_quantity_tree(
    tree: ContextGroup, profile: Snapshot, element: ElementDefinitionDict
) -> Component:
    element_paths = {c.path for c in tree.components}
    # If all values are present to represent a valid quantity generate Quantity FHIR datatype instance
    if (
        "value" in element_paths
        and "system" in element_paths
        and "code" in element_paths
    ):
        quantity = Quantity()
        for c in tree.components:
            assert isinstance(
                c, AttributeComponent
            ), f"Unexpected type [actual='{type(c)}', expected='AttributeComponent']"
            match c.path:
                case "value":
                    quantity.value = get_symbol(c.values[0])
                case "unit":
                    quantity.unit = get_symbol(c.values[0])
                case "system":
                    quantity.system = get_symbol(c.values[0])
                case "code":
                    quantity.code = get_symbol(c.values[0])
        return AttributeComponent(
            types=[FhirComplexDataType.QUANTITY],
            path=tree.path,
            cardinality=aggregate_cardinality_using_element(element, profile),
            values=[quantity],
        )
    # Else treat the components as individual expressions
    else:
        return ContextGroup(
            path=tree.path,
            components=[
                enrich_tree_with_types_and_values(c, profile, tree.path)
                for c in tree.components
            ],
        )


def _enrich_literal_quantity_tree(
    tree: AttributeComponent, profile: Snapshot, element: ElementDefinitionDict
) -> AttributeComponent:
    if tree.values:
        expr: fhirpathParser.LiteralTermContext = tree.values[0]
        qc: fhirpathParser.QuantityContext = expr.literal().quantity()
        quantity = Quantity(
            system="http://unitsofmeasure.org",
            code=get_symbol(qc.unit()),
            value=get_symbol(qc.NUMBER()),
        )
    else:
        quantity = None
    return AttributeComponent(
        types=[FhirComplexDataType.QUANTITY],
        path=tree.path,
        cardinality=aggregate_cardinality_using_element(element, profile),
        values=[quantity] if quantity else [],
    )


def _enrich_period_tree(
    tree: ContextGroup, profile: Snapshot, element: ElementDefinitionDict
) -> AttributeComponent:
    period = Period()
    for c in tree.components:
        match c.path:
            case "start":
                period.start = get_symbol(c)
            case "end":
                period.system = get_symbol(c)
            case _:
                raise Exception(
                    f"Element path '{c}' is not supported for FHIR datatype 'Period'"
                )
    return AttributeComponent(
        types=[FhirComplexDataType.PERIOD],
        path=tree.path,
        cardinality=aggregate_cardinality_using_element(element, profile),
        values=[period],
    )


def _enrich_primitive_typed_tree(
    tree: AttributeComponent,
    profile: Snapshot,
    element: ElementDefinitionDict,
    datatype: FhirPrimitiveDataType,
) -> AttributeComponent:
    match datatype:
        case FhirPrimitiveDataType.BOOLEAN:
            values = [bool(get_symbol(c)) for c in tree.values]
        case (
            FhirPrimitiveDataType.INTEGER
            | FhirPrimitiveDataType.POSITIVE_INT
            | FhirPrimitiveDataType.UNSIGNED_INT
        ):
            values = [int(get_symbol(c)) for c in tree.values]
        case FhirPrimitiveDataType.DECIMAL:
            values = [Decimal(get_symbol(c)) for c in tree.values]
        case FhirPrimitiveDataType.Date:
            values = [date.fromisoformat(get_symbol(c)) for c in tree.values]
        case FhirPrimitiveDataType.TIME:
            values = [time.fromisoformat(get_symbol(c)) for c in tree.values]
        case FhirPrimitiveDataType.DATE_TIME | FhirPrimitiveDataType.INSTANT:
            values = [datetime.fromisoformat(get_symbol(c)) for c in tree.values]
        case _:
            values = [get_symbol(c) for c in tree.values]
    tree.values = values
    tree.cardinality = aggregate_cardinality_using_element(element, profile)
    return tree


def enrich_tree_with_types_and_values(
    tree: Component, profile: Snapshot, _parent_path: Optional[str] = None
) -> Component:
    """
    Uses information in the profile snapshot to replace preliminarily assigned values in all leaf nodes (e.g.
    `AttributeComponent` objects) with suitable FHIR data types and assign type information

    :param tree: Attribute component tree to enrich
    :param profile: Profile snapshot on which the attributes are based
    :param _parent_path: Parent path to the elements of the given tree. Does not have to be provided when passing full tree
    :return: Enriched profile tree
    """
    base_path = tree.path if not _parent_path else f"{_parent_path}.{tree.path}"
    try:
        element = get_element_from_snapshot(profile, base_path)
    except KeyError:
        _logger.debug("Attempting to find element with polymorphic element name")
        element = get_element_from_snapshot(profile, base_path + "[x]")
    types = get_types_supported_by_element(element)
    match types:
        case [t]:
            match tree:
                case ContextGroup() as cg:
                    match t.code:
                        case "Coding":
                            return _enrich_coding_tree(cg, profile, element)
                        case "Quantity":
                            return _enrich_quantity_tree(cg, profile, element)
                        case "Period":
                            return _enrich_period_tree(cg, profile, element)
                        case _:
                            cg.components = [
                                enrich_tree_with_types_and_values(c, profile, base_path)
                                for c in cg.components
                            ]
                            return cg
                case AttributeComponent() as ac:
                    if t.code in FhirPrimitiveDataType:
                        return _enrich_primitive_typed_tree(
                            ac, profile, element, t.code
                        )
                    elif t.code in FhirComplexDataType:
                        match t.code:
                            case "Quantity":
                                return _enrich_literal_quantity_tree(
                                    ac, profile, element
                                )
                    else:
                        raise Exception(
                            f"Unsupported datatype '{t.code}' of element '{element.get('id')}' represented by AttributeComponent instance"
                        )
        case _:
            raise Exception(
                f"Element '{element.get('id')}' supports multiple types which is currently not supported"
            )
