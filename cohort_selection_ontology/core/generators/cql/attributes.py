from datetime import datetime, date, time
from decimal import Decimal
from os import PathLike
from typing import Optional, Annotated, Union

from antlr4.ParserRuleContext import ParserRuleContext
from bs4.diagnose import profile
from fhir.resources.R4B.codeableconcept import CodeableConcept
from fhir.resources.R4B.coding import Coding
from fhir.resources.R4B.period import Period
from fhir.resources.R4B.quantity import Quantity
from fhir.resources.R4B.reference import Reference
from typing_extensions import deprecated

from cohort_selection_ontology.core.generators.cql.generator import (
    aggregate_cardinality_using_element,
    select_element_compatible_with_cql_operations,
)
from cohort_selection_ontology.model.mapping.cql import (
    Component,
    ContextGroup,
    AttributeComponent,
    ReferenceGroup,
)
from cohort_selection_ontology.util.fhir.structure_definition import (
    get_element_defining_elements,
    get_profiles_with_base_definition,
    get_element_type,
)
from common.util.collections.functions import flatten
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
    join_fhirpath,
)
from common.util.functions import first
from common.util.log.functions import get_logger
from common.util.model import field_names
from common.util.project import Project
from common.util.wrapper import dotdict

_logger = get_logger(__name__)


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


def get_components_from_invocation_expression(
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
                "types": [],  # Will be assigned during post-processing
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
        return get_components_from_function(pre_expr, new_component)


def get_components_from_equality_expression(
    expr: fhirpathParser.EqualityExpressionContext,
) -> ComponentDict:
    term_expr: fhirpathParser.TermExpressionContext = expr.getChild(2)
    attr_component = dotdict(
        {
            "_type": AttributeComponent.__name__,
            "types": [],  # Will be assigned during post-processing
            "path": None,  # Will be assigned in when parent elements are processed
            "cardinality": None,  # Will be assigned during post-processing
            "values": [  # Will be translated into proper FHIR data type during post-processing
                term_expr
            ],
        }
    )
    return get_component_tree(expr.getChild(0), attr_component)


def get_components_from_and_expression(
    expr: fhirpathParser.AndExpressionContext,
) -> ContextGroupDict:
    right = get_component_tree(expr.getChild(2))
    match expr.getChild(0):
        case fhirpathParser.AndExpressionContext() as aec:
            left = get_components_from_and_expression(aec)
        case _ as other:
            left = get_component_tree(other)
    return dotdict(
        {
            "_type": ContextGroup.__name__,
            "path": None,  # Will be assigned in when parent elements are processed
            "components": [left, right],
        }
    )


def get_components_from_function_parameters(
    expr: fhirpathParser.ParamListContext | None,
) -> list[ComponentDict]:
    if expr is None:
        return []
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
    component: Optional[ComponentDict] = None,
) -> ComponentDict:
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
                    "Function 'where' should not terminate an expression",
                )
            cs = get_components_from_function_parameters(func_expr.paramList())
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
            match get_components_from_function_parameters(func_expr.paramList()):
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
                        "types": [get_symbol(func_expr.paramList())],
                        "path": None,  # Will be assigned in when parent elements are processed
                        "cardinality": None,  # Will be assigned during post-processing
                        "values": [],  # Will be translated into proper FHIR data type during post-processing
                    }
                )
        case "resolve":
            if component is not None:
                child = component
                component = dotdict(
                    {
                        "_type": ReferenceGroup.__name__,
                        "type": None,
                        "path": None,
                        "components": [child],
                    }
                )
            else:
                component = dotdict(
                    {
                        "_type": AttributeComponent.__name__,
                        "types": ["Reference"],
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

    return get_component_tree(expr.getChild(0), component)


def get_components_from_term_expression(
    expr: fhirpathParser.TermExpressionContext, component: Optional[ComponentDict] = None
) -> ComponentDict:
    symbol = get_symbol(expr.term().invocation())
    if component is None:
        return dotdict({
            "_type": AttributeComponent.__name__,
            "types": [],
            "path": symbol,
            "cardinality": None,
            "values": []
        })
    component["path"] = (
        f"{symbol}.{component.path}" if component.path is not None else symbol
    )
    return component


def get_component_tree(
    expr: ParserRuleContext, component: Optional[ComponentDict] = None
) -> ComponentDict:
    match expr:
        case fhirpathParser.EntireExpressionContext() as full_expr:
            if component is not None:
                _logger.warning("Provided tree already represents entire FHIRPath expression => Ignoring additionally "
                                "provided components")
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
                [
                    "equality expression",
                    "invocation expression",
                    "term expression",
                ],
            )


def _enrich_reference_typed_tree(
    tree: ReferenceGroupDict,
    element: ElementDefinitionDict,
    project: Project,
    module: str,
) -> ReferenceGroup:
    ref_type = first(
        get_types_supported_by_element(element), lambda x: x.code == "Reference"
    )
    target_profiles = ref_type.targetProfile
    if target_profiles and len(target_profiles) == 1:
        profiles = list(
            flatten(
                [
                    get_profiles_with_base_definition(project.input.cso / "modules", tp)
                    for tp in target_profiles
                ]
            )
        )
        if len(profiles) == 1:
            (referenced_profile, _) = profiles[0]
            res_type = referenced_profile.get("type")
            return ReferenceGroup(
                type=res_type,
                path=tree.path,
                components=[
                    enrich_tree_with_types_and_values(
                        c, referenced_profile, project, module, res_type
                    )
                    for c in tree.components
                ],
            )
        else:
            raise Exception(
                f"Unsupported number of resolved target profiles in referencing element '{element.get('id')}' "
                f"[expected=1, actual={len(profiles)}, profiles={profiles}]"
            )
    else:
        raise Exception(
            f"Unsupported number of target profiles in referencing element '{element.get('id')}' "
            f"[expected=1, actual={len(target_profiles)}]"
        )


def _enrich_coding_typed_tree(
    tree: ContextGroupDict, profile: Snapshot, element: ElementDefinitionDict
) -> AttributeComponent:
    coding = Coding()
    for c in tree.components:
        match c.path:
            case "system":
                coding.system = get_symbol(c["values"][0])
            case "code":
                coding.code = get_symbol(c["values"][0])
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
    tree: ContextGroupDict,
    profile: Snapshot,
    element: ElementDefinitionDict,
    project: Project,
    module: PathLike[str],
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
            assert (
                field_names(AttributeComponent) == c.keys()
            ), f"Unexpected fields [expected={field_names(AttributeComponent)}, actual={c.keys()}]"
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
                enrich_tree_with_types_and_values(
                    c, profile, project, module, tree.path
                )
                for c in tree.components
            ],
        )


def _enrich_literal_quantity_tree(
    tree: AttributeComponentDict, profile: Snapshot, element: ElementDefinitionDict
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
        types=[FhirComplexDataType.QUANTITY],
        path=tree.path,
        cardinality=aggregate_cardinality_using_element(element, profile),
        values=[quantity] if quantity else [],
    )


def _enrich_period_tree(
    tree: ContextGroupDict, profile: Snapshot, element: ElementDefinitionDict
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


def _enrich_reference_typed_attribute(
    tree: AttributeComponentDict,
    profile: Snapshot,
    element: ElementDefinitionDict,
    modules_dir_path: PathLike | str,
) -> AttributeComponent:
    ref_type = first(
        get_types_supported_by_element(element), lambda x: x.code == "Reference"
    )
    target_profiles = ref_type.targetProfile
    if target_profiles and len(target_profiles) >= 1:
        profiles = [
            get_profiles_with_base_definition(modules_dir_path, tp)
            for tp in target_profiles
        ]
        types = {p.get("type") for p, _ in profiles}
        return AttributeComponent(
            types=["Reference"],
            path=tree.path,
            cardinality=aggregate_cardinality_using_element(element, profile),
            values=[Reference(type=t) for t in types] if types else [Reference()],
        )
    else:
        raise Exception(
            f"Element '{element.get('id')}' does not support type 'Reference' or target profiles"
        )


def _enrich_coding_typed_attribute(
    profile: Snapshot, element: ElementDefinitionDict
) -> AttributeComponent:
    (compatible_element, _) = select_element_compatible_with_cql_operations(
        element, profile
    )
    return AttributeComponent(
        types=[t.code for t in get_types_supported_by_element(compatible_element)],
        path=compatible_element.get("path"),
        cardinality=aggregate_cardinality_using_element(compatible_element, profile),
        values=[],
    )


def _enrich_primitive_typed_tree(
    tree: AttributeComponentDict,
    profile: Snapshot,
    element: ElementDefinitionDict,
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
        case FhirPrimitiveDataType.Date:
            values = [date.fromisoformat(get_symbol(c)) for c in tree["values"]]
        case FhirPrimitiveDataType.TIME:
            values = [time.fromisoformat(get_symbol(c)) for c in tree["values"]]
        case FhirPrimitiveDataType.DATE_TIME | FhirPrimitiveDataType.INSTANT:
            values = [datetime.fromisoformat(get_symbol(c)) for c in tree["values"]]
        case _:
            values = [get_symbol(c) for c in tree["values"]]
    return AttributeComponent(
        types=tree.types,
        path=tree.path,
        cardinality=aggregate_cardinality_using_element(element, profile),
        values=values,
    )


def enrich_tree_with_types_and_values(
    tree: ComponentDict,
    profile_snapshot: Snapshot,
    project: Project,
    module: PathLike[str] | str,
    _parent_path: Optional[str] = None,
) -> Component:
    """
    Uses information in the profile snapshot to replace preliminarily assigned values in all leaf nodes (e.g.
    `AttributeComponent` objects) with suitable FHIR data types and assign type information

    :param tree: Attribute component tree to enrich
    :param profile_snapshot: Profile snapshot on which the attributes are based
    :param project: Project to work with
    :param module: Module to start search for profiles in
    :param _parent_path: Parent path to the elements of the given tree. Does not have to be provided when passing full tree
    :return: Enriched profile tree
    """
    base_path = tree.path if not _parent_path else f"{_parent_path}.{tree.path}"
    modules_dir_path = project.input.cso / "modules"
    element = get_element_defining_elements(
        base_path, profile_snapshot, module, modules_dir_path
    )[-1]
    types = get_types_supported_by_element(element)
    if len(types) == 1:
        t = types[0]
        match tree:
            case {"_type": ContextGroup.__name__} as cg:
                match t.code:
                    case "Coding":
                        return _enrich_coding_typed_tree(cg, profile_snapshot, element)
                    case "Quantity":
                        return _enrich_quantity_tree(
                            cg, profile_snapshot, element, project, module
                        )
                    case "Period":
                        return _enrich_period_tree(cg, profile_snapshot, element)
                    case _:
                        return ContextGroup(
                            path=cg.path,
                            components=[
                                enrich_tree_with_types_and_values(
                                    c, profile_snapshot, base_path, module
                                )
                                for c in cg.components
                            ],
                        )
            case {"_type": AttributeComponent.__name__} as ac:
                if t.code in FhirPrimitiveDataType:
                    return _enrich_primitive_typed_tree(
                        ac, profile_snapshot, element, t.code
                    )
                elif t.code in FhirComplexDataType:
                    match t.code:
                        case "Quantity":
                            return _enrich_literal_quantity_tree(
                                ac, profile_snapshot, element
                            )
                        case "Reference":
                            return _enrich_reference_typed_attribute(
                                ac, profile_snapshot, element, modules_dir_path
                            )
                        case "Coding":
                            return _enrich_coding_typed_attribute(
                                profile_snapshot, element
                            )
                        case _:
                            raise Exception(
                                f"Unsupported complex datatype '{t.code}' of element '{element.get('id')}' represented by AttributeComponent instance"
                            )
                else:
                    raise Exception(
                        f"Unknown datatype '{t.code}' of element '{element.get('id')}' represented by AttributeComponent instance"
                    )
            case {"_type": ReferenceGroup.__name__} as rg:
                return _enrich_reference_typed_tree(
                    rg, element, project, module
                )
            case _ as x:
                raise KeyError(
                    f"Dictionary has to match either ContextGroup or AttributeComponent structure [actual={field_names(x)}]"
                )
    else:
        raise Exception(
            f"Element '{element.get('id')}' supports {'multiple' if types else 'no'} types which is currently not supported"
        )
