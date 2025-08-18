import itertools
import re
from datetime import datetime, UTC
from itertools import groupby
from typing import List, Dict, Optional, Any, Tuple

from antlr4.ParserRuleContext import ParserRuleContext
from fhir.resources.R4B.codeableconcept import CodeableConcept
from fhir.resources.R4B.coding import Coding
from fhir.resources.R4B.element import Element
from fhir.resources.R4B.elementdefinition import (
    ElementDefinition,
    ElementDefinitionType,
    ElementDefinitionSlicingDiscriminator,
)
from fhir.resources.R4B.expression import Expression
from fhir.resources.R4B.extension import Extension
from fhir.resources.R4B.measure import (
    Measure,
    MeasureGroup,
    MeasureGroupStratifier,
    MeasureGroupPopulation,
)
from fhir.resources.R4B.meta import Meta
from fhir.resources.R4B.structuredefinition import StructureDefinition

from availability.constants.fhir import MII_CDS_PACKAGE_PATTERN
from availability.constants.measure import (
    CC_IN_INITIAL_POPULATION,
    CC_MEASURE_POPULATION,
    CC_MEASURE_OBSERVATION,
)
from common.constants.fhir import EXT_DATA_ABSENT_REASON_URL
from common.exceptions import NotFoundError, UnsupportedError
from common.model.fhir.structure_definition import (
    StructureDefinitionSnapshot,
    IndexedStructureDefinition,
)
from common.util.fhir.enums import FhirPrimitiveDataType
from common.util.fhir.package.manager import FhirPackageManager
from common.util.fhir.structure_definition import get_parent_elem_id
from common.util.fhirpath import parse_expr, fhirpathParser
from common.util.fhirpath.functions import get_symbol
from common.util.log.functions import get_logger

_logger = get_logger(__file__)


_REGEX_MATCH_TRAILING_WHERE_FUNC = re.compile(r"where\((.*)\)$")
_REGEX_MATCH_TRAILING_EXISTS_FUNC = re.compile(r"exists\((.*)\)$")


def _add_data_absent_reason_clause(expr: Optional[ParserRuleContext] = None) -> str:
    """
    Adds a clause to the provided expression to check if any data-absent-reason extension is present in the element

    :param expr: Parsed FHIRPath expression to add the clause to
    :return: FHIRPath expression string with the added clause
    """
    absent_reason_clause = f"extension('{EXT_DATA_ABSENT_REASON_URL}').empty()"
    if not expr:
        return absent_reason_clause
    input_str = getattr(expr, "parser").getInputStream().getText()
    expr_str = input_str[expr.start.start : expr.stop.stop + 1]
    match expr:
        case fhirpathParser.OrExpressionContext():
            return f"({expr_str}) and " + absent_reason_clause
        case _:
            return f"{expr_str} and " + absent_reason_clause


def _ensure_trailing_existence_check(expr_str: str, is_primitive: bool = False) -> str:
    """
    Ensure that a FHIRPath expression is terminated by either a hasValue (primitive datatypes) or an exists (complex
    datatypes) function invocation. This is done by either append such an invocation pr by replacing a trailing where
    function invocation with an exists function invocation that has same parameters

    :param expr_str: FHIRPath expression string
    :param is_primitive: Whether the collection returned by the provided FHIRPath expression contains only primitively
                         typed elements
    :return: Expression string with trailing existence check
    """
    expr = parse_expr(expr_str).expression()
    fc = expr.getChild(2).getChild(0)
    if isinstance(fc, fhirpathParser.FunctionContext):
        match get_symbol(fc.identifier()):
            case "hasValue":
                if is_primitive:
                    return expr_str
                else:
                    return (
                        expr_str[: fc.start.start]
                        + f"exists({_add_data_absent_reason_clause()})"
                    )
            case "exists":
                fc_start = fc.start.start
                plc: fhirpathParser.ParamListContext = fc.paramList()
                if not plc and is_primitive:
                    return expr_str[:fc_start] + "hasValue()"
                return (
                    expr_str[:fc_start]
                    + f"exists({_add_data_absent_reason_clause(plc.getChild(0) if plc else None)})"
                )
            case "where":
                if is_primitive:
                    return expr_str + ".hasValue()"
                fc_start = fc.start.start
                plc: fhirpathParser.ParamListContext = fc.paramList()
                return (
                    expr_str[:fc_start]
                    + f"exists({_add_data_absent_reason_clause(plc.getChild(0))})"
                )
    if is_primitive:
        return expr_str + ".hasValue()"
    else:
        return expr_str + f".exists({_add_data_absent_reason_clause()})"


def _add_populations(
    group: MeasureGroup, resource_type: str, profile_url: str, id_num: int
) -> MeasureGroup:
    """
    Populates the given measure group with initial populations required by the
    `http://hl7.org/fhir/us/cqfmeasures/StructureDefinition/cv-measure-cqfm` profile

    :param group: `MeasureGroup` instance to update
    :param resource_type: Targeted FHIR resource type
    :param profile_url: URL of the constraining profile
    :param id_num: Sequential ID number to generate unique set of ID values for each population entry
    :return: Passed `MeasureGroup` instance
    """
    group.population = []
    group.population.append(
        MeasureGroupPopulation(
            code=CC_IN_INITIAL_POPULATION,
            criteria=Expression(
                language="text/x-fhir-query",
                expression=f"{resource_type}?_profile:below={profile_url}",
            ),
            id=f"initial-population-identifier-{id_num}",
        )
    )
    group.population.append(
        MeasureGroupPopulation(
            code=CC_MEASURE_POPULATION,
            criteria=Expression(language="text/fhirpath", expression=resource_type),
            id=f"measure-population-identifier-{id_num}",
        )
    )
    group.population.append(
        MeasureGroupPopulation(
            code=CC_MEASURE_OBSERVATION,
            criteria=Expression(
                language="text/fhirpath", expression=f"{resource_type}.id.value"
            ),
            extension=[
                Extension(
                    url="http://hl7.org/fhir/us/cqfmeasures/StructureDefinition/cqfm-aggregateMethod",
                    valueCode="unique-count",
                ),
                Extension(
                    url="http://hl7.org/fhir/us/cqfmeasures/StructureDefinition/cqfm-criteriaReference",
                    valueString=f"measure-population-identifier-{id_num}",
                ),
            ],
            id=f"measure-observation-identifier-{id_num}",
        )
    )
    return group


def _find_polymorphic_value(data: Element, element_name: str) -> Optional[Any]:
    """
    Attempts to find the value of a polymorphic element by iterating over all possible data type-specific names

    :param data: FHIR structure to find the value of a contained polymorphic element in
    :param element_name: (Typeless) name of the polymorphic element in the structure
    :return: Value of the contained element or `None` if no such element exists/it has no value
    """
    for field_name in data.__class__.model_fields.keys():
        if field_name.startswith(element_name):
            v = getattr(data, field_name)
            if v:
                return v
    return None


def _find_value_for_discriminator_pattern_or_value(
    elem: ElementDefinition,
) -> Optional[Tuple[str, Any]]:
    """
    Attempts to find the discriminator value of a slice-defining FHIR element definition for pattern or value
    discriminated slicings, e.g. looks for a values ib the `fixed[x]`, `pattern[x]`, or `binding` sub-element

    :param elem: `ElementDefinition` instance containing the discriminator value
    :return: Tuple of the sub-element name and its value ir `None` if no fitting sub-element could be found
    """
    if fixed := _find_polymorphic_value(elem, "fixed"):
        return "fixed", fixed
    if pattern := _find_polymorphic_value(elem, "pattern"):
        return "pattern", pattern
    if elem.binding:
        return "binding", elem.binding
    return None


def _element_data_to_fhirpath_filter(key: str = "$this", data: Any = None) -> List[str]:
    """
    Recursively traverses a FHIR element data and depending on its basic structure (e.g. it being a simple value, list,
    or key-value-mapping) translates its content into a FHIRPath expression filter in the form of a 'where' function
    invocation. Used internally by the `_element_to_fhirpath_filter` function

    :param key: Name of the element in its parent structure
    :param data: FHIR element data to transform
    :return: FHIRPath filter string
    """
    exprs = []
    match data:
        case dict():
            sub_exprs = [
                e
                for k, v in data.items()
                for e in _element_data_to_fhirpath_filter(k, v)
            ]
            match len(sub_exprs):
                case 0:
                    pass
                case 1:
                    expr = sub_exprs[0]
                    if key == "$this":
                        exprs.append(expr)
                    else:
                        if _REGEX_MATCH_TRAILING_EXISTS_FUNC.search(expr):
                            exprs.append(f"{key}.{expr}")
                        else:
                            exprs.append(f"{key}.exists({expr})")
                case _:
                    if key == "$this":
                        exprs.append(" and ".join(sub_exprs))
                    else:
                        exprs.append(f"{key}.exists({' and '.join(sub_exprs)})")
        case list():
            sub_exprs = [
                e for v in data for e in _element_data_to_fhirpath_filter(data=v)
            ]
            match len(sub_exprs):
                case 0:
                    pass
                case 1:
                    expr = sub_exprs[0]
                    exprs.append(f"{key}.exists({expr})" if key != "$this" else expr)
                case _:
                    clause = " and ".join([f"exists({se})" for se in sub_exprs])
                    clause = f"{key}.exists({clause})" if key != "$this" else clause
                    exprs.append(clause)
        case _:
            # TODO: Add handling for other simple FHIR data types
            exprs.append(f"{key} = '{str(data)}'")
    return exprs


def _element_to_fhirpath_filter(key: str = "$this", elem: Any = None) -> str:
    """
    Recursively traverses a FHIR element and depending on its basic structure (e.g. it being a simple value, list, or
    key-value-mapping) translates its content into a FHIRPath expression filter in the form of a 'where' function
    invocation

    :param key: Name of the element in its parent structure
    :param elem: FHIR element to transform
    :return: FHIRPath filter string
    """
    if isinstance(elem, Element):
        elem_data = elem.model_dump(exclude_none=True, exclude_unset=True)
    else:
        elem_data = elem
    clause = " and ".join(_element_data_to_fhirpath_filter(key, elem_data))
    return f"where({clause})"


def _append_filter_from_profile_discriminated_elem(
    base_expr: str,
    elem: ElementDefinition,
    discr: ElementDefinitionSlicingDiscriminator,
    snapshot: StructureDefinitionSnapshot,
    manager: FhirPackageManager,
) -> str:
    """
    Appends a FHIRPath filter based on the constraints of a profile discriminated slice to the given FHIRPath
    expression. ATM, only elements of type `canonical`, `Reference`, or `Extension` are supported

    :param base_expr: FHIRPath expression to add the slice-based filter to
    :param elem: `ElementDefinition` representing element targeted by discriminator
    :param discr: Slicing discriminator
    :param snapshot: Structure Definition snapshot containing the discriminated element
    :param manager: FHIR package manager providing access to package cache
    :return: Extended FHIRPath expression
    """
    types = elem.type
    if len(types) > 1:
        raise ValueError(
            f"Profile discriminated element '{elem.id} in snapshot '{snapshot.url}' "
            f"supports more than one type"
        )
    t = types[0]
    match t.code:
        case "Reference" | "canonical":
            target_profile_urls = t.targetProfile
            clause = " or ".join(
                [
                    f"$this = '{url}'"
                    for target_profile_url in target_profile_urls
                    for url in [
                        target_profile_url,
                        *manager.dependents_of(
                            target_profile_url, MII_CDS_PACKAGE_PATTERN
                        ),
                    ]
                ]
            )
            # Make path relative to discriminated element (apparently absolute resource paths are allowed as
            # discriminator paths)
            path = discr.path.removeprefix(f"{base_expr}.")
            # Remove (possible) trailing resolve function call
            path = re.sub(r"\.?resolve\(\)$", "", path)
            return f"{base_expr}.where({path}.resolve().meta.profile.exists({clause}))"
        case "Extension":
            if len(t.profile) == 1:
                return f"{base_expr}('{t.profile[0]}')"
            clause = " or ".join([f"url = '{url}'" for url in t.profile])
            # expr = clause if discr.path == "$this" else f"{discr.path}.exists({clause})"
            return f"{base_expr}.where({clause})"
        case _:
            raise UnsupportedError(
                f"Type '{t.code}' is currently not supported in profile discriminated "
                f"elements [element_id='{elem.id}', snapshot_url='{snapshot.url}']"
            )


def _get_filter_from_pattern_or_value_discriminated_elem(
    elem_def: ElementDefinition, discr_path: str, snapshot: StructureDefinitionSnapshot
) -> str:
    """
    Follows the discriminator path and at each node check for the discriminator value in the element at the current
    sub path. The discriminator value can be defined in any element definition whos path is a sub path of the
    discriminator path. For instance, given the discriminator defined on element with path 'a.b.c' and discriminator
    path `d.e.f`, we have to check elements 'a.b.c', `a.b.c.d`, ..., and `a.b.c.d.e.f`. If the path is not exhausted, we
    expect the value of an element to be complex and the rest of the path being represented in the structure of its
    value

    :param elem_def: `ElementDefinition` instance where a slice is defined
    :param discr_path: (Relative) path to the discriminator value
    :param snapshot: Snapshot containing the element definition
    :return: FHIRPath filter selecting elements matching the slice
    """

    def get_val(path: List[str], data: Any) -> Optional[Any]:
        try:
            v = data
            for name in path:
                v = getattr(data, name)
            return v
        except AttributeError:
            return None

    if discr_path != "$this":
        chain = discr_path.removeprefix("$this.").split(".")
        while len(chain) > 0:
            ret = _find_value_for_discriminator_pattern_or_value(elem_def)
            if ret is not None:
                _, val = ret
                if get_val(chain, val) is not None:
                    break
            elem_def = snapshot.get_element_by_id(f"{elem_def.id}.{chain.pop(0)}")
    val_type, value = _find_value_for_discriminator_pattern_or_value(elem_def)
    match val_type:
        case "binding":
            path = f"{discr_path}." if discr_path != "$this" else ""
            return f"where({path}memberOf('{value.valueSet}'))"
        case _:
            return _element_to_fhirpath_filter(discr_path, value)


def _append_filter_for_slice(
    base_expr: str,
    slice_elem_def: ElementDefinition,
    snapshot: StructureDefinitionSnapshot,
    manager: FhirPackageManager,
) -> str:
    """
    Appends a slice-based filter part to the given FHIRPath expression

    :param base_expr: FHIRPath expression to base extended expression on
    :param slice_elem_def: Slice-defining `ElementDefinition`
    :param snapshot: Structure definition snapshot contain the sliced element
    :param manager: FHIR package manager
    :return: Extended version of the given FHIRPath expression
    """
    parent_elem = snapshot.get_element_by_id(get_parent_elem_id(slice_elem_def))
    discriminators = parent_elem.slicing.discriminator
    if len(discriminators) == 0:
        raise Exception(
            f"Cannot get filter for element '{slice_elem_def.id}'. Parent element '{parent_elem.id}' "
            f"defines no discriminator"
        )
    for discr in discriminators:
        discr_path = discr.path.replace("$this.", "")
        match discr.type:
            case "value" | "pattern":
                # FIXME: The value discriminator type is pretty much treated like the pattern discriminator type,
                #        though this might not be accurate
                # Both discriminator types support all of these options
                t = slice_elem_def.type[0]
                if t.code == "Extension":
                    # NOTE: There are potentially other ways by which an extension could be discriminated
                    if discr_path != "url":
                        raise UnsupportedError(
                            f"Only pattern or value discriminators targeting an extensions 'url' "
                            f"element are supported to discriminate Extension typed elements "
                            f"[element_id='{slice_elem_def.id}', snapshot_url='{snapshot.url}']"
                        )
                    if t.profile:
                        checks = []
                        if len(t.profile) == 1:
                            return f"{base_expr}('{t.profile[0]}')"
                        for url in t.profile:
                            index_pattern = {"url": url}
                            ext_snapshot = manager.find(index_pattern)
                            url_elem_def = ext_snapshot.get_element_by_id(
                                "Extension.url"
                            )
                            checks.append(f"url = '{url_elem_def.fixedUri}'")
                        return f"{base_expr}.where({' or '.join(checks)})"
                    else:
                        where_filter = (
                            _get_filter_from_pattern_or_value_discriminated_elem(
                                slice_elem_def, discr_path, snapshot
                            )
                        )
                        matches = re.findall(r"\'(\S+)\'", where_filter)
                        if len(matches) == 1:
                            return f"{base_expr}('{matches[0]}')"
                        return base_expr + "." + where_filter
                return (
                    base_expr
                    + "."
                    + _get_filter_from_pattern_or_value_discriminated_elem(
                        slice_elem_def, discr_path, snapshot
                    )
                )
            case "exists":
                return f"where({discr_path}.exists())"
            case "type":
                if len(slice_elem_def.type) == 1:
                    expr = f"ofType({slice_elem_def.type[0].code})"
                    type_expr = (
                        expr if discr_path == "$this" else f"{discr.path}.{expr}"
                    )
                    return base_expr + "." + type_expr
                else:
                    clause = " or ".join(
                        [f"$this is {t.code}" for t in slice_elem_def.type]
                    )
                    type_expr = (
                        clause
                        if discr_path == "$this"
                        else f"{discr.path}.exists({clause})"
                    )
                    return f"{base_expr}.where({type_expr})"
            case "profile":
                if discr_path == "$this":
                    target_elem = slice_elem_def
                else:
                    # Make path relative to discriminated element (apparently absolute resource paths are allowed as
                    # discriminator paths)
                    path = discr_path.removeprefix(f"{slice_elem_def.path}.")
                    # Remove (possible) leading $this selector
                    path = path.removeprefix("$this.")
                    # Remove (possible) trailing resolve function call
                    path = re.sub(r"\.?resolve\(\)$", "", path)
                    target_elem = snapshot.get_element_by_id(
                        f"{slice_elem_def.id}.{path}"
                    )
                if not target_elem:
                    raise NotFoundError(
                        f"Could not find element definition '{slice_elem_def.id}.{discr_path}' in snapshot "
                        f"'{snapshot.url}' representing profile discriminated element"
                    )
                return _append_filter_from_profile_discriminated_elem(
                    base_expr, target_elem, discr, snapshot, manager
                )
            case _ as t:
                raise Exception(
                    f"Unknown discriminator type '{t}' in slicing definition"
                )


def _generate_stratifier(expr: str, full_elem_id: str) -> MeasureGroupStratifier:
    """
    Generates a stratifier for a `Measure` group

    :param expr: Stratifying FHIRPath expression
    :param full_elem_id: Full ID of the element the stratifier is based on
    :return: Stratifier
    """
    return MeasureGroupStratifier(
        criteria=Expression(language="text/fhirpath", expression=expr),
        code=CodeableConcept(
            coding=[
                Coding(
                    system="http://fhir-data-evaluator/strat/system",
                    code=full_elem_id,
                )
            ]
        ),
    )


def _get_full_element_id(
    chained_elem_id: List[str], type_code: Optional[str] = None
) -> str:
    """
    Builds the full element ID from the list of element IDs used to navigate to it along instance/structure boundaries

    :param chained_elem_id: List of element IDs to be combined
    :param type_code: (Optional) element type for resolving polymorphic element name placeholders
    :return: Full element ID
    """
    field_name = ".".join(
        [chained_elem_id[0], *[i.split(".", 1)[1] for i in chained_elem_id[1:]]]
    )
    if type_code:
        con = type_code[:1].upper() + type_code[1:]
        return con.join(field_name.rsplit("[x]", 1))
    return field_name


def _resolve_polymorphism_in_expr(expr: str, fhir_type: Optional[str] = None) -> str:
    """ "
    Resolves polymorphic element names with the given FHIRPath expression using the given FHIR type

    :param expr: FHIRPath expression string
    :param fhir_type: Optional FHIR type string to generate a type filter expression from that will be used to replace
                      the '[x]' part of element names. If this is `None` then the polymorphic part will just be removed
    :return: Cleansed FHIRPath expression string
    """
    if fhir_type:
        return re.sub(r"\[x]", f".ofType({fhir_type})", expr)
    else:
        return re.sub(r"\[x]", "", expr)


def _generate_stratifier_for_reference(
    ref_profile: StructureDefinition,
    base_expr: str,
    chained_elem_id: List[str],
    manager: FhirPackageManager,
) -> List[MeasureGroupStratifier]:
    """
    Generates stratifiers from a reference

    :param ref_profile: Referenced profile
    :param base_expr: FHIRPath expression for navigating to the reference-containing element
    :param chained_elem_id: Chain of IDs of elements from previous resource contexts leading to the element
    :param manager: FHIR package manager
    :return: List of stratifiers
    """
    # We sort the list by the profiles URLs such that the order is the same between runs and to improve readability
    resolved_profiles = sorted(
        [
            ref_profile,
            *manager.dependents_of(ref_profile.url, MII_CDS_PACKAGE_PATTERN),
        ],
        key=lambda p: p.url,
    )
    strats = []
    for t, ps in groupby(resolved_profiles, lambda p: p.type):
        ps = list(ps)
        expr = f"{base_expr}.resolve().ofType({ps[0].type}).meta.profile"
        match len(ps):
            case 1:
                expr = f"{expr} contains '{ps[0].url}'"
            case _:
                clause = " or ".join([f"$this = '{p.url}'" for p in ps])
                expr = f"{expr}.exists({clause})"
        strats.append(
            _generate_stratifier(
                expr,
                _get_full_element_id(chained_elem_id, "Reference")
                + "->"
                + ref_profile.type,
            )
        )
    return strats


def _generate_stratifiers_for_extension_elements(
    ext_snapshot: StructureDefinitionSnapshot,
    base_ext_expr: str,
    manager: FhirPackageManager,
    chained_elem_id: List[str],
) -> List[MeasureGroupStratifier]:
    """
    Generates stratifiers from the given extension defining structure definition by recursing over its value element or
    the value element of the extension it contains. Note that this function only generates stratifiers for the "value"
    carrying elements of the extension

    :param ext_snapshot: `StructureDefinition` instance defining the extension
    :param base_ext_expr: FHIRPath expression serving as the base for the FHIRPath expression for the generated stratifiers
    :param manager: FHIR package manager providing the package scope to work with
    :param chained_elem_id: Chain of IDs of elements from previous resource contexts leading to the extension
    :return: List of stratifiers checking for the existence of the extensions sub-elements
    """
    stratifiers = []
    # There is no need to define a stratifier for this element since its value will be used to filter for matching
    # Extension instances already
    relevant_elem_defs = sorted(
        filter(
            lambda e: e.max != "0"
            and e.id != "Extension"
            and (e.id != "Extension.extension" or not e.slicing)
            and not e.id.endswith(".id")
            and not e.id.endswith(".url"),
            ext_snapshot.snapshot.element,
        ),
        key=lambda e: e.id,
    )
    expr_cache = {
        "Extension": base_ext_expr,
        "Extension.extension": f"{base_ext_expr}.extension",
    }
    for elem_def in relevant_elem_defs:
        stratifiers.extend(
            _generate_stratifiers_for_elem_def(
                elem_def, ext_snapshot, manager, expr_cache, chained_elem_id
            )
        )
    return stratifiers


def _generate_stratifiers_for_typed_elem(
    elem_type: ElementDefinitionType,
    parent_expr: str,
    parent_elem_id: str,
    manager: FhirPackageManager,
    chained_elem_id: List[str],
) -> List[MeasureGroupStratifier]:
    """
    Generates stratifiers for the given element definition and FHIR data type

    :param elem_type: FHIR data type supported by the element
    :param parent_expr: FHIRPath expression for navigating to the parent element
    :param parent_elem_id: Element ID of the parent element
    :param manager: FHIR package manager
    :param chained_elem_id: Chain of IDs of preceding elements resulting from context switches (reference resolution
                            etc.)
    :return: List of stratifiers
    """
    match elem_type.code:
        case "Extension":
            stratifiers = [
                _generate_stratifier(
                    _ensure_trailing_existence_check(parent_expr),
                    _get_full_element_id(chained_elem_id, "Extension"),
                )
            ]
            if elem_type.profile:
                profile_urls = elem_type.profile
                for url in profile_urls:
                    index_pattern = {"url": url}
                    snapshot = manager.find(index_pattern)
                    if not snapshot or not isinstance(snapshot, StructureDefinition):
                        raise NotFoundError(
                            f"Could not find StructureDefinition resource defining extension structure '{url}'"
                        )
                    snapshot = StructureDefinitionSnapshot.model_validate(snapshot)
                    stratifiers.extend(
                        _generate_stratifiers_for_extension_elements(
                            snapshot,
                            parent_expr,
                            manager,
                            chained_elem_id,
                        )
                    )
            else:
                # Extension elements can be defined inside the resource snapshot itself in which case its sub-elements
                # will already be processed like other elements definitions in the snapshot
                pass
            return stratifiers
        case "Reference":
            # profile_urls = elem_type.targetProfile if elem_type.targetProfile else []
            stratifiers = [
                _generate_stratifier(
                    _ensure_trailing_existence_check(
                        f"{parent_expr}.reference.hasValue()", is_primitive=True
                    ),
                    # _get_full_element_id(chained_elem_id, "Reference"),
                    _get_full_element_id(chained_elem_id),
                )
            ]
            # FIXME: Disabled for now since reference resolution in the FHIR Data Evaluator requires referenced resources
            #        inclusion in the initial population which has to be done by either including all referenced
            #        resources or by selecting all relevant ones via specific search parameters. The former option is
            #        currently not supported by all FHIR server (e.g. blaze) and the later requires resolving search
            #        parameters using the FHIRPath expression they use to select elements which is fasr from trivial (it
            #        would require determining expression equivalence)
            # for url in profile_urls:
            #     index_pattern = {"url": url}
            #     snapshot = manager.find(index_pattern)
            #     if not snapshot or not isinstance(snapshot, StructureDefinition):
            #         raise NotFoundError(
            #             f"Could not find StructureDefinition resource defining structure '{url}'"
            #         )
            #     snapshot = StructureDefinitionSnapshot.model_validate(snapshot)
            #     stratifiers.extend(
            #         _generate_stratifier_for_reference(
            #             snapshot,
            #             _resolve_polymorphism_in_expr(parent_expr, "Reference"),
            #             chained_elem_id,
            #             manager,
            #         )
            #     )
            return stratifiers
        case _ as type_code:
            expr = (
                _resolve_polymorphism_in_expr(
                    (
                        parent_expr
                        if parent_expr.endswith("[x]")
                        else (parent_expr + "[x]")
                    ),
                    type_code,
                )
                if parent_elem_id.endswith("[x]")
                and not re.search(r"ofType\([a-zA-Z]+\)$", parent_expr)
                else parent_expr
            )
            return [
                _generate_stratifier(
                    _ensure_trailing_existence_check(
                        expr, type_code in FhirPrimitiveDataType
                    ),
                    _get_full_element_id(chained_elem_id),
                )
            ]


def _resolve_supported_types(
    elem_def: ElementDefinition,
    snapshot: IndexedStructureDefinition,
    manager: FhirPackageManager,
) -> List[ElementDefinitionType]:
    """
    Resolves the types of the given element definition by returning the range of supported types listed in its `type`
    element or by following any content references in the `contentReference` element to resolve their types

    :param elem_def: `ElementDefinition` instance to resolve types of
    :param snapshot: Snapshot containing the element definition
    :param manager: FHIR package manager for loading referenced structures
    :return: List of `ElementDefinition.type` instances representing supported types
    """
    if elem_def.type:
        return elem_def.type
    elif elem_def.contentReference:
        content_ref_profile_url, content_ref_elem_id = elem_def.contentReference.split(
            "#"
        )
        if content_ref_profile_url and len(content_ref_profile_url) > 0:
            index_pattern = {"url": content_ref_profile_url}
            content_ref_profile = manager.find(index_pattern)
            content_ref_elem = content_ref_profile.get_element_by_id(
                content_ref_elem_id
            )
        else:
            content_ref_elem = snapshot.get_element_by_id(content_ref_elem_id)
        if not content_ref_elem:
            raise Exception(
                f"Cannot resolve content reference '{elem_def.contentReference}'"
            )
        return _resolve_supported_types(content_ref_elem, snapshot, manager)
    else:
        return []


def _generate_stratifiers_for_elem_def(
    elem_def: ElementDefinition,
    snapshot: StructureDefinitionSnapshot,
    manager: FhirPackageManager,
    elem_expr_cache: Dict[str, str],
    chained_elem_id: List[str] = None,
) -> List[MeasureGroupStratifier]:
    """
    Generates stratifiers for the given element definition

    :param elem_def: `ElementDefinition` instance to generate stratifiers for
    :param snapshot: Structure definition snapshot containing the element definition
    :param manager: FHIR package manager
    :param elem_expr_cache: Mapping of element IDs to already generated FHIRPath expressions
    :param chained_elem_id: Chain of IDs of preceding elements resulting from context switches (reference resolution
                            etc.)
    :return: List of stratifiers
    """
    if not chained_elem_id:
        chained_elem_id = []
    stratifiers = []
    # Generate base stratifier
    parent_elem_id = get_parent_elem_id(elem_def)
    base_expr = elem_expr_cache.get(parent_elem_id)
    if not base_expr:
        raise KeyError(
            f"Missing expression entry for parent element '{parent_elem_id}' obtained from child element "
            f"'{elem_def.id}'. This can be the result of a wrong element ID, the element not having been "
            f"processed yet, or the element missing entirely"
        )
    # Handle slice presence
    if elem_def.sliceName:
        expr = _append_filter_for_slice(base_expr, elem_def, snapshot, manager)
    else:
        expr = base_expr + "." + elem_def.path.split(".")[-1]
    # Do not generate stratifiers if the element does (or rather should) not occur in instance data
    if elem_def.max == "0":
        _logger.debug(
            f"Skipping element '{elem_def.id}' since it has max cardinality '0'"
        )
        elem_expr_cache[elem_def.id] = expr
        return stratifiers
    # Handle type range
    supported_types = _resolve_supported_types(elem_def, snapshot, manager)
    match supported_types:
        case []:
            _logger.warning(f"Element '{elem_def.id}' supports no types => Skipping")
            expr = _resolve_polymorphism_in_expr(expr, "")
            elem_expr_cache[elem_def.id] = expr
        case [t]:
            if expr.endswith("[x]"):
                expr = _resolve_polymorphism_in_expr(expr, t.code)
            else:
                expr = _resolve_polymorphism_in_expr(expr, "")
            elem_expr_cache[elem_def.id] = expr
            stratifiers.extend(
                strat
                for strat in _generate_stratifiers_for_typed_elem(
                    t, expr, elem_def.id, manager, [*chained_elem_id, elem_def.id]
                )
            )
        case _:
            expr = _resolve_polymorphism_in_expr(expr, "")
            elem_expr_cache[elem_def.id] = expr
            stratifiers.append(
                _generate_stratifier(
                    _ensure_trailing_existence_check(expr),
                    _get_full_element_id([*chained_elem_id, elem_def.id]),
                )
            )
            stratifiers.extend(
                [
                    strat
                    for t in supported_types
                    for strat in _generate_stratifiers_for_typed_elem(
                        t,
                        expr,
                        elem_def.id,
                        manager,
                        [
                            *chained_elem_id,
                            (
                                _get_full_element_id([elem_def.id], t.code)
                                if elem_def.id.endswith("[x]")
                                else elem_def.id
                            ),
                        ],
                    )
                ]
            )
    return stratifiers


def _generate_measure_group_for_profile(
    snapshot: StructureDefinitionSnapshot,
    manager: FhirPackageManager,
    id_num: int,
) -> MeasureGroup:
    """
    Generates a measure group for the given structure definition

    :param snapshot: Structure definition snapshot to generated measure group for
    :param manager: FHIR package manager
    :param id_num: Unique ID for the measure group
    :return: `MeasureGroup` instance representing the profile
    """
    measure_group = MeasureGroup(
        extension=[
            Extension(
                url="http://hl7.org/fhir/StructureDefinition/elementSource",
                valueUri=snapshot.url
                + (("#" + snapshot.version) if snapshot.version else ""),
            )
        ],
        stratifier=[],
        id=f"grp_{snapshot.name.replace('-', '_').lower()}",
    )
    _add_populations(measure_group, snapshot.type, snapshot.url, id_num)
    # Used to store expression for every element ID encountered such that known expressions can be used to generate
    # expressions for new element IDs due to the hierarchical nature of the FHIR data model
    elem_id_expr_map = dict()
    # We sort the list of element definitions by their ID (in ascending order) to encounter elements in a descending
    # hierarchical order regarding there appearance in the resource
    for elem_def in sorted(snapshot.snapshot.element, key=lambda ed: ed.id):
        if elem_def.id == snapshot.type or elem_def.id.endswith(".id"):
            # Skip root and ID element processing
            elem_id_expr_map[elem_def.id] = elem_def.path
            continue
        _logger.debug(f"Generating stratifiers for element '{elem_def.id}'")
        try:
            elem_stratifiers = _generate_stratifiers_for_elem_def(
                elem_def, snapshot, manager, elem_id_expr_map
            )
        except Exception as exc:
            _logger.warning(
                f"Failed to generate stratifiers for element '{elem_def.id}' in snapshot '{snapshot.url}' => Skipping"
            )
            _logger.debug("Details:", exc_info=exc)
            continue
        measure_group.stratifier.extend(elem_stratifiers)
    return measure_group


def update_stratifier_ids(measure: Measure) -> Measure:
    """
    Generates and assigns ascending IDs per group to all stratifiers in the measure

    :param measure: `Measure` instance that will be modified
    :return: Passed `Measure` instance
    """
    for group in measure.group:
        for idx, stratifier in enumerate(group.stratifier, 1):
            stratifier.id = f"strat_{group.id}_{idx}"
    return measure


def generate_measure(manager: FhirPackageManager, **elements) -> Measure:
    """
    Generates the Element Availability Measure resource

    :param manager: FHIR package manager
    :param elements: key value pairs for assigning element values of the generated `Measure` resource
    :return: `Measure` resource instance
    """
    measure = Measure(
        id=elements.get("id", "ElementAvailabilityMeasure"),
        meta=elements.get(
            "meta",
            Meta(
                profile=[
                    "http://hl7.org/fhir/us/cqfmeasures/StructureDefinition/cv-measure-cqfm"
                ]
            ),
        ),
        url=elements.get(
            "url", "https://example.org/fhir/Measure/ElementAvailabilityMeasure"
        ),
        name=elements.get("name", "ElementAvailabilityMeasure"),
        title=elements.get("title", "Element Availability Measure"),
        status=elements.get("status", "active"),
        experimental=elements.get("experimental", False),
        date=elements.get("date", datetime.now(UTC)),
        publisher=elements.get("publisher", "example"),
        description=elements.get(
            "description",
            "Measure for analyzing the availability and variance of elements of data in a FHIR server",
        ),
    )
    measure.group = []
    measure_groups = measure.group

    counter = itertools.count()
    content_pattern = {
        "resourceType": "StructureDefinition",
        "kind": "resource",
    }
    for profile in manager.iterate_cache(
        MII_CDS_PACKAGE_PATTERN, content_pattern, skip_on_fail=True
    ):
        if profile.type in ["SearchParameter"]:
            continue
        _logger.debug(f"Generating measure group for profile '{profile.url}'")
        try:
            if not isinstance(profile, StructureDefinition) and not profile.snapshot:
                _logger.debug(
                    f"Profile '{profile.url}' is not in snapshot form => Skipping"
                )
                continue
            group_id_num = next(counter)
            profile = StructureDefinitionSnapshot.model_validate(profile)
            measure_groups.append(
                _generate_measure_group_for_profile(profile, manager, group_id_num)
            )
        except Exception as exc:
            _logger.error(
                f"Failed to generate measure group for profile '{profile.url}' => Skipping",
            )
            _logger.debug("Details:", exc_info=exc)
    return update_stratifier_ids(measure)
