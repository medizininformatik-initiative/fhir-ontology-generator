import itertools
import re
from datetime import UTC, datetime
from itertools import groupby
from typing import List, Optional

from antlr4.ParserRuleContext import ParserRuleContext
from fhir.resources.R4B import get_fhir_model_class
from fhir.resources.R4B.codeableconcept import CodeableConcept
from fhir.resources.R4B.coding import Coding
from fhir.resources.R4B.elementdefinition import (
    ElementDefinitionType,
    ElementDefinition,
)
from fhir.resources.R4B.expression import Expression
from fhir.resources.R4B.extension import Extension
from fhir.resources.R4B.measure import (
    Measure,
    MeasureGroup,
    MeasureGroupPopulation,
    MeasureGroupStratifier,
)
from fhir.resources.R4B.meta import Meta
from fhir.resources.R4B.structuredefinition import StructureDefinition

from dataportal_generator.common.model.fhir.nav_structure_definition import ensure_struct_def_is_navigable
from dataportal_generator.availability.constants.fhir import MII_CDS_PACKAGE_PATTERN
from dataportal_generator.availability.constants.measure import (
    CC_IN_INITIAL_POPULATION,
    CC_MEASURE_OBSERVATION,
    CC_MEASURE_POPULATION,
)
from dataportal_generator.availability.core.exceptions import MissingSubjectRefError
from dataportal_generator.common.constants.fhir import EXT_DATA_ABSENT_REASON_URL
from dataportal_generator.common.exceptions import NotFoundError
from dataportal_generator.common.model.fhir.functions import get_reference_fields
from dataportal_generator.common.util.collections import first
from dataportal_generator.common.fhir.enums import FhirPrimitiveDataType
from dataportal_generator.common.fhir.package_manager import FhirPackageManager
from dataportal_generator.common.fhirpath import fhirpathParser, parse_expr
from dataportal_generator.common.fhirpath.functions import filter_for_slice, get_symbol
from dataportal_generator.common.log.functions import get_logger
from dataportal_generator.common.fhir.structure_definition import get_parent_element
from dataportal_generator.common.model.fhir.nav_structure_definition import NavStructureDefinition
from dataportal_generator.common.model.fhir.nav_element_definition import NavElementDefinition


_logger = get_logger(__file__)


_EXCLUDED_BASE_PATHS = {"Extension.id", "Extension.url", "Resource.id", "Element.id"}


def _filter_elem_def(elem_def: ElementDefinition) -> bool:
    if base := elem_def.base:
        if base.path in _EXCLUDED_BASE_PATHS:
            return False
    return True


def _find_subject_reference_elem_def(
    profile: NavStructureDefinition,
) -> Optional[NavElementDefinition]:
    """
    Tries to find the first-level element holding the reference to the Patient resource (that represent the patient to
    which this type of clinical data applies)

    :param profile: `StructureDefinition` constraining a resource type
    :return: `NavElementDefinition` defining a suitable element or `None` if no such element could be identified
    """
    res_type = profile.type
    if model_cls := get_fhir_model_class(res_type):
        ref_fields = get_reference_fields(model_cls, {"Patient"})
        match ref_fields:
            case []:
                return None
            case [f]:
                elem_path = f"{res_type}.{f.alias}"
            case _:
                # Try common names for such an element if there are multiple candidates
                f_names = [f.alias for f in ref_fields]
                if "subject" in f_names:
                    elem_path = f"{res_type}.subject"
                elif "patient" in f_names:
                    elem_path = f"{res_type}.patient"
                else:
                    return None
        return profile.get_element_by_id(elem_path)
    else:
        raise ValueError(
            f"Unknown FHIR resource type '{res_type}' constrained by profile '{profile}'"
        )


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
    group: MeasureGroup,
    resource_type: str,
    profile_url: str,
    subject_ref_elem_name: str,
    id_num: int,
) -> MeasureGroup:
    """
    Populates the given measure group with initial populations required by the
    `http://hl7.org/fhir/us/cqfmeasures/StructureDefinition/cv-measure-cqfm` profile

    :param group: `MeasureGroup` instance to update
    :param resource_type: Targeted FHIR resource type
    :param profile_url: URL of the constraining profile
    :param subject_ref_elem_name: Name of the element holding a reference to the subject
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
                language="text/fhirpath",
                expression=f"{resource_type}.{subject_ref_elem_name}.reference",
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


def _generate_stratifier(expr: str, full_elem_id: str) -> MeasureGroupStratifier:
    """
    Generates a stratifier for a `Measure` group

    :param expr: Stratifying FHIRPath expression
    :param full_elem_id: Full ID of the element the stratifier is based on
    :return: Stratifier
    """
    return MeasureGroupStratifier(
        id=full_elem_id,
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
    chained_elem_id: List[str],
    type_code: Optional[str] = None,
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
        field_name = con.join(field_name.rsplit("[x]", 1))
    return field_name


def _resolve_polymorphism_in_expr(expr: str, fhir_type: Optional[str] = None) -> str:
    """
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


class MeasureGroupGenerator:
    def __init__(self, package_manager: FhirPackageManager):
        self._package_manager = package_manager
        self._elem_expr_cache = dict()

    def _generate_stratifier_for_reference(
        self,
        ref_struct_def: NavStructureDefinition,
        base_expr: str,
        chained_elem_id: List[str],
    ) -> List[MeasureGroupStratifier]:
        """
        Generates stratifiers from a reference

        :param ref_struct_def: Referenced profile
        :param base_expr: FHIRPath expression for navigating to the reference-containing element
        :param chained_elem_id: Chain of IDs of elements from previous resource contexts leading to the element
        :return: List of stratifiers
        """
        # We sort the list by the profiles URLs such that the order is the same between runs and to improve readability
        resolved_profiles = sorted(
            [
                ref_struct_def,
                *self._package_manager.dependents_of(
                    ref_struct_def.url, MII_CDS_PACKAGE_PATTERN
                ),
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
                    _get_full_element_id(
                        chained_elem_id,
                        "Reference",
                    )
                    + "->"
                    + ref_struct_def.type,
                )
            )
        return strats

    def _generate_stratifiers_for_extension_elements(
        self,
        ext_struct_def: NavStructureDefinition,
        base_ext_expr: str,
        chained_elem_id: List[str],
    ) -> List[MeasureGroupStratifier]:
        """
        Generates stratifiers from the given extension defining structure definition by recursing over its value element or
        the value element of the extension it contains. Note that this function only generates stratifiers for the "value"
        carrying elements of the extension

        :param ext_struct_def: `StructureDefinition` instance defining the extension
        :param base_ext_expr: FHIRPath expression serving as the base for the FHIRPath expression for the generated stratifiers
        :param chained_elem_id: Chain of IDs of elements from previous resource contexts leading to the extension
        :return: List of stratifiers checking for the existence of the extensions sub-elements
        """
        stratifiers = []
        # There is no need to define a stratifier for this element since its value will be used to filter for matching
        # Extension instances already
        relevant_elem_defs = sorted(
            filter(
                lambda e: (
                    e.max != "0"
                    and e.id != "Extension"
                    and (e.id != "Extension.extension" or not e.slicing)
                    and not e.id.endswith(".id")
                    and not e.id.endswith(".url")
                ),
                ext_struct_def.snapshot.element,
            ),
            key=lambda e: e.id,
        )
        self._elem_expr_cache["Extension"] = base_ext_expr
        self._elem_expr_cache["Extension.extension"] = f"{base_ext_expr}.extension"
        for elem_def in relevant_elem_defs:
            stratifiers.extend(
                self._generate_stratifiers_for_elem_def(
                    elem_def, ext_struct_def, chained_elem_id
                )
            )
        return stratifiers

    def _generate_stratifiers_from_extension_definitions(
        self,
        elem_def: NavElementDefinition,
        parent_expr: str,
        chained_elem_id: List[str],
    ) -> List[MeasureGroupStratifier]:
        """
        Generates stratifiers from the referenced extension structure definitions supported by the given element definition

        :param elem_def: ``NavElementDefinition`` instance supporting data type ``Extension``
        :param parent_expr: FHIRPath expression for navigating to the parent element
        :param chained_elem_id: Chain of IDs of elements from previous resource contexts leading to the extension
        :return: List of stratifiers based on the referenced extension structure definitions
        """
        if not (ext_type := first(lambda e: e.code == "Extension", elem_def.type)):
            raise ValueError(
                f"Element definition {elem_def.id} does not support data type 'Extension'"
            )
        stratifiers = []
        ext_profiles = ext_type.profile if ext_type.profile is not None else []
        for url in ext_profiles:
            struct_def = self._package_manager.find_struct_def(url)
            if not struct_def or not isinstance(struct_def, StructureDefinition):
                raise NotFoundError(
                    f"Could not find StructureDefinition resource defining extension structure '{url}'"
                )
            stratifiers.extend(
                self._generate_stratifiers_for_extension_elements(
                    struct_def,
                    parent_expr,
                    chained_elem_id,
                )
            )
        return stratifiers

    def _generate_stratifiers_for_reference(
        self, parent_expr: str, chained_elem_id: List[str]
    ) -> List[MeasureGroupStratifier]:
        """
        Generates stratifiers for ``Reference`` typed element. Generated stratifiers check for the existence of a
        technical reference (``Reference.reference``) and a logical one (``Reference.identifier``)

        :param parent_expr: FHIRPath expression for navigating to the parent element
        :param chained_elem_id: Chain of IDs of preceding elements resulting from context switches (reference resolution
                                etc.)
        :return: List of generated stratifiers
        """
        return [
            _generate_stratifier(
                _ensure_trailing_existence_check(
                    parent_expr + ".reference.hasValue()", is_primitive=True
                ),
                _get_full_element_id(
                    [*chained_elem_id[:-1], chained_elem_id[-1] + ".reference"]
                ),
            ),
            _generate_stratifier(
                _ensure_trailing_existence_check(
                    parent_expr + ".identifier", is_primitive=True
                ),
                _get_full_element_id(
                    [*chained_elem_id[:-1], chained_elem_id[-1] + ".identifier"]
                ),
            ),
        ]

    def _generate_stratifiers_for_typed_elem(
        self,
        elem_type: ElementDefinitionType,
        parent_expr: str,
        parent_elem_id: str,
        chained_elem_id: List[str],
    ) -> List[MeasureGroupStratifier]:
        """
        Generates stratifiers for the given element definition and FHIR data type

        :param elem_type: FHIR data type supported by the element
        :param parent_expr: FHIRPath expression for navigating to the parent element
        :param parent_elem_id: Element ID of the parent element
        :param chained_elem_id: Chain of IDs of preceding elements resulting from context switches (reference resolution
                                etc.)
        :return: List of stratifiers
        """
        match elem_type.code:
            case "Reference":
                # profile_urls = elem_type.targetProfile if elem_type.targetProfile else []
                #stratifiers = [
                #    _generate_stratifier(
                #        _ensure_trailing_existence_check(
                #            f"{parent_expr}.reference.hasValue()", is_primitive=True
                #        ),
                #        # _get_full_element_id(chained_elem_id, "Reference"),
                #        _get_full_element_id(chained_elem_id),
                #    )
                #]
                stratifiers = self._generate_stratifiers_for_reference(parent_expr, chained_elem_id)
                # FIXME: Disabled for now since reference resolution in the FHIR Data Evaluator requires referenced resources
                #        inclusion in the initial population which has to be done by either including all referenced
                #        resources or by selecting all relevant ones via specific search parameters. The former option is
                #        currently not supported by all FHIR server (e.g. blaze) and the later requires resolving search
                #        parameters using the FHIRPath expression they use to select elements which is far from trivial (it
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
        self,
        elem_def: NavElementDefinition,
        struct_def: NavStructureDefinition,
    ) -> List[ElementDefinitionType]:
        """
        Resolves the types of the given element definition by returning the range of supported types listed in its
        ``type`` element or by following any content references in the ``contentReference`` element to resolve their
        types

        :param elem_def: ``NavElementDefinition`` instance to resolve types of
        :param struct_def: ``StructureDefinition`` containing the element definition
        :return: List of ``NavElementDefinition.type`` instances representing supported types
        """
        if elem_def.type:
            return elem_def.type
        elif elem_def.contentReference:
            content_ref_profile_url, content_ref_elem_id = (
                elem_def.contentReference.split("#")
            )
            if content_ref_profile_url and len(content_ref_profile_url) > 0:
                content_ref_struct_def = self._package_manager.find_struct_def(content_ref_profile_url)
                content_ref_elem = content_ref_struct_def.get_element_by_id(
                    content_ref_elem_id
                )
            else:
                content_ref_elem = struct_def.get_element_by_id(content_ref_elem_id)
            if not content_ref_elem:
                raise Exception(
                    f"Cannot resolve content reference '{elem_def.contentReference}'"
                )
            return self._resolve_supported_types(content_ref_elem, struct_def)
        else:
            return []

    def _supports_extension_type(
        self, elem_def: NavElementDefinition, struct_def: NavStructureDefinition
    ) -> bool:
        return any(
            t.code == "Extension"
            for t in self._resolve_supported_types(elem_def, struct_def)
        )

    def _generate_stratifiers_for_elem_def(
        self,
        elem_def: NavElementDefinition,
        struct_def: NavStructureDefinition,
        chained_elem_id: Optional[List[str]] = None,
    ) -> List[MeasureGroupStratifier]:
        """
        Generates stratifiers for the given element definition

        :param elem_def: `NavElementDefinition` instance to generate stratifiers for
        :param struct_def: Structure definition snapshot containing the element definition
        :param chained_elem_id: (Optional) Chain of IDs of preceding elements resulting from context switches (reference
                                resolution etc.)
        :return: List of stratifiers
        """
        if not chained_elem_id:
            chained_elem_id = []
        stratifiers = []
        # Generate base stratifier
        parent_elem_id = get_parent_element(struct_def, elem_def).id
        base_expr = self._elem_expr_cache.get(parent_elem_id)
        if not base_expr:
            raise KeyError(
                f"Missing expression entry for parent element '{parent_elem_id}' obtained from child element "
                f"'{elem_def.id}'. This can be the result of a wrong element ID, the element not having been "
                f"processed yet, or the element missing entirely"
            )
        # Handle slice presence
        if elem_def.sliceName:
            expr = filter_for_slice(
                base_expr, elem_def, struct_def, MII_CDS_PACKAGE_PATTERN
            )
        else:
            expr = base_expr + "." + elem_def.path.split(".")[-1]
        # Do not generate stratifiers if the element does (or rather should) not occur in instance data
        if elem_def.max == "0":
            _logger.debug(
                f"Skipping element '{elem_def.id}' since it has max cardinality '0'"
            )
            self._elem_expr_cache[elem_def.id] = expr
            return stratifiers
        # TODO: Add support for slices of reference typed elements. ATM this cannot be supported since the FHIRPath filter
        #  generated from the discriminator cannot be processed by the FDE
        if (
            first(
                lambda t: t.code == "Reference",
                self._resolve_supported_types(elem_def, struct_def),
            )
            and elem_def.sliceName
        ):
            _logger.debug(
                f"Skipping element definition {repr(elem_def.id)} since slices of Reference typed elements are currently not supported"
            )
            self._elem_expr_cache[elem_def.id] = expr
            return stratifiers
        # Handle type range
        supported_types = self._resolve_supported_types(elem_def, struct_def)
        match supported_types:
            case []:
                _logger.warning(
                    f"Element '{elem_def.id}' supports no types => Skipping"
                )
                expr = _resolve_polymorphism_in_expr(expr, "")
                self._elem_expr_cache[elem_def.id] = expr
            case [t]:
                if expr.endswith("[x]"):
                    expr = _resolve_polymorphism_in_expr(expr, t.code)
                else:
                    expr = _resolve_polymorphism_in_expr(expr, "")
                self._elem_expr_cache[elem_def.id] = expr
                stratifiers.extend(
                    strat
                    for strat in self._generate_stratifiers_for_typed_elem(
                        t, expr, elem_def.id, [*chained_elem_id, elem_def.id]
                    )
                )
            case _:
                expr = _resolve_polymorphism_in_expr(expr, "")
                self._elem_expr_cache[elem_def.id] = expr
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
                        for strat in self._generate_stratifiers_for_typed_elem(
                            t,
                            expr,
                            elem_def.id,
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

    def generate(self, struct_def: NavStructureDefinition, id_num: int) -> MeasureGroup:
        """
        Generates a measure group for the given structure definition

        :param struct_def: Structure definition snapshot to generated measure group for
        :param id_num: Unique ID for the measure group
        :return: `MeasureGroup` instance representing the profile
        """
        subject_ref_elem_def = _find_subject_reference_elem_def(struct_def)
        if not subject_ref_elem_def:
            raise MissingSubjectRefError(
                f"Profile '{struct_def.url}' has no suitable subject reference element and thus no measure group can be "
                f"generated"
            )
        subject_ref_name = subject_ref_elem_def.path.split(".")[-1]
        measure_group = MeasureGroup(
            extension=[
                Extension(
                    url="http://hl7.org/fhir/StructureDefinition/elementSource",
                    valueUri=struct_def.url
                    + (("#" + struct_def.version) if struct_def.version else ""),
                )
            ],
            stratifier=[],
            id=f"grp_{struct_def.name.replace('-', '_').lower()}",
        )
        _add_populations(
            measure_group, struct_def.type, struct_def.url, subject_ref_name, id_num
        )
        # Used to store expression for every element ID encountered such that known expressions can be used to generate
        # expressions for new element IDs due to the hierarchical nature of the FHIR data model
        self._elem_expr_cache = dict()
        # Store element definitions support data type `Extension` for additional processing after all element defintions
        # contained within the snapshot are already processed. The reason for this is that we want to prioritize using
        # element definitions within the snapshot (possibly containing constrains) over those defined externally in the
        # referenced structure definition
        extension_postprocessing = list()
        # We sort the list of element definitions by their ID (in ascending order) to encounter elements in a descending
        # hierarchical order regarding there appearance in the resource
        for elem_def in sorted(struct_def.snapshot.element, key=lambda ed: ed.id):
            if elem_def.id == struct_def.type or not _filter_elem_def(elem_def):
                # Skip root and ID element processing
                _logger.debug(f"Skipping element definition {repr(elem_def.id)}")
                self._elem_expr_cache[elem_def.id] = elem_def.path
                continue
            _logger.debug(f"Generating stratifiers for element '{elem_def.id}'")
            try:
                elem_stratifiers = self._generate_stratifiers_for_elem_def(
                    elem_def, struct_def
                )
                if self._supports_extension_type(elem_def, struct_def):
                    extension_postprocessing.append(elem_def)
            except Exception as exc:
                _logger.warning(
                    f"Failed to generate stratifiers for element '{elem_def.id}' in profile '{struct_def.url}' => Skipping"
                )
                _logger.debug("Details:", exc_info=exc)
                continue
            measure_group.stratifier.extend(elem_stratifiers)
        # Extension postprocessing
        strat_ids = set(s.id for s in measure_group.stratifier)
        for elem_def in extension_postprocessing:
            ext_strats = self._generate_stratifiers_from_extension_definitions(
                elem_def, self._elem_expr_cache[elem_def.id], [elem_def.id]
            )
            measure_group.stratifier.extend(
                filter(lambda s: s.id not in strat_ids, ext_strats)
            )
        return measure_group


def make_stratifier_codes_fde_compatible(
    package_manager: FhirPackageManager, measure: Measure
) -> Measure:
    """
    Updates ``Measure`` resource's stratifier FDE codes in-place by replacing the resource type with the profile name to
    ensure every stratifier has a measure-wide unique FDE code

    :param package_manager: ``FhirPackageManager`` object to resolve FHIR ``StructureDefinition``s in context
    :param measure: ``Measure`` resource instance to update
    :return: Passed ``Measure`` resource instance with updated stratifier IDs
    """
    for group in measure.group:
        source_ext = first(
            lambda ext: (
                ext.url == "http://hl7.org/fhir/StructureDefinition/elementSource"
            ),
            group.extension,
        )
        source_profile_url = (
            None if not source_ext else source_ext.valueUri.split("#")[0]
        )
        if not source_profile_url:
            _logger.warning(
                f"Failed to determine FHIR profile from which the measure group was generated [group_id='{group.id}'] => Dropping group from measure"
            )
            continue
        profile = package_manager.find(index_pattern={"url": source_profile_url})
        profile_name = profile.name.replace(" ", "_")
        for strat in group.stratifier:
            strat_coding = first(
                lambda c: c.system == "http://fhir-data-evaluator/strat/system",
                strat.code.coding,
            )
            # Update stratifier codes with profile name
            _, *path = strat_coding.code.split(".", maxsplit=1)
            strat_coding.code = ".".join([profile_name, *path])
    return measure


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
    for struct_def in manager.iterate_cache(
        MII_CDS_PACKAGE_PATTERN, content_pattern, skip_on_fail=True
    ):
        if struct_def.type in ["SearchParameter"]:
            continue
        _logger.debug(f"Generating measure group for profile '{struct_def.url}'")
        try:
            if (
                not isinstance(struct_def, StructureDefinition)
                and not struct_def.snapshot
            ):
                _logger.debug(
                    f"Profile '{struct_def.url}' is not in snapshot form => Skipping"
                )
                continue
            group_id_num = next(counter)
            struct_def = ensure_struct_def_is_navigable(struct_def)
            measure_groups.append(
                MeasureGroupGenerator(manager).generate(struct_def, group_id_num)
            )
        except Exception as exc:
            match exc:
                case MissingSubjectRefError():
                    _logger.info(
                        f"No eligible subject reference can be identified in profile '{struct_def.url}' => Excluding"
                    )
                case _:
                    _logger.error(
                        f"Failed to generate measure group for profile '{struct_def.url}' => Skipping",
                    )
            _logger.debug("Details:", exc_info=exc)
    return update_stratifier_ids(measure)
