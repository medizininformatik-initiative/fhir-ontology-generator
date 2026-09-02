import itertools
import re
from collections.abc import Iterator
from datetime import UTC, datetime

from antlr4.ParserRuleContext import ParserRuleContext
from dataportal_generator.common.constants.fhir import EXT_DATA_ABSENT_REASON_URL
from dataportal_generator.common.fhir.package_manager import FhirPackageManager
from dataportal_generator.common.fhirpath import fhirpathParser, parse_expr
from dataportal_generator.common.fhirpath.functions import (
    fhirpath_filter_for_slice,
    get_symbol,
)
from dataportal_generator.common.log.functions import get_logger
from dataportal_generator.common.model.fhir.functions import get_reference_fields
from dataportal_generator.common.model.fhir.nav_element_definition import (
    NavElementDefinition,
)
from dataportal_generator.common.model.fhir.nav_structure_definition import (
    NavStructureDefinition,
    ensure_struct_def_is_navigable,
)
from dataportal_generator.common.model.project import Project
from dataportal_generator.common.util.collections import first
from fhir.resources.R4B import get_fhir_model_class
from fhir.resources.R4B.codeableconcept import CodeableConcept
from fhir.resources.R4B.coding import Coding
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

from dataportal_generator.availability.constants.measure import (
    CC_IN_INITIAL_POPULATION,
    CC_MEASURE_OBSERVATION,
    CC_MEASURE_POPULATION,
)
from dataportal_generator.availability.core.exceptions import MissingSubjectRefError

_logger = get_logger(__file__)

# 'ElementDefinition.base.path' excluding an element definition from having a stratifier generated for it. Note that
# this does not apply to special/dedicated type handling (e.g. Extension, Reference, etc.) which is handled separately
# in the code
_BASE_PATHS_EXCLUDED_FROM_STRATIFIER_GEN = {
    "Element.id",
    "Extension.url",
    "Reference.referenceReference.type",
    "Reference.identifierReference.display",
}


_EXT_ELEM_BASE_PATHS = {
    "Element.extension",
    "DomainResource.extension",
    "DomainResource.modifierExtension",
}


def _supports_only_primitive_types(elem_def: NavElementDefinition) -> bool:
    if not elem_def.type:
        return False
    return not any(t.code and t.code[0].isupper() for t in elem_def.type)


def _could_be_complex_typed(elem_def: NavElementDefinition) -> bool:
    """
    Checks if the given element definition could appear with a complex data type in instance data. This check is
    relevant since we assume no strict profile adherence. If the base definition of an element allows complex data
    types then ``True`` is returned no matter what type constrains are defined by derived profiles

    :param elem_def: ``NavElementDefinition`` object
    :return: ``True`` if the element could have a complex data type, ``False`` otherwise
    """
    if elem_def.id.endswith("[x]"):
        return True
    return not _supports_only_primitive_types(elem_def)


def _resolve_polymorphism_in_expr(expr: str, fhir_type: str | None = None) -> str:
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


def _selector_sub_expr_for_elem_def(
    elem_def: NavElementDefinition, criteria_only: bool = False
) -> str:
    """
    Generates a FHIRPath expression for the given element definition that can be used to select the element from a
    resource

    :param elem_def: Element definition to generate the expression for
    :param criteria_only: Whether to generate only the criteria part of the expression if it is a ``where`` function
                          invocation
    :return: FHIRPath expression string
    """
    if elem_def.is_slice:
        return fhirpath_filter_for_slice(elem_def, criteria_only)
    else:
        return elem_def.rel_path


def _add_data_absent_reason_clause(expr: ParserRuleContext | None = None) -> str:
    """
    Adds a clause to the provided expression to check if any data-absent-reason extension is present in the element

    :param expr: Parsed FHIRPath expression to add the clause to
    :return: FHIRPath expression string with the added clause
    """
    absent_reason_clause = f"extension('{EXT_DATA_ABSENT_REASON_URL}').empty()"
    if not expr:
        return absent_reason_clause
    input_str = expr.parser.getInputStream().getText()
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


def _update_strat_identity(
    strat: MeasureGroupStratifier, old: str, new: str
) -> MeasureGroupStratifier:
    """
    Updates the ``MeasureGroupStratifier`` instances ID value FDE code by replacing any appearances of the old snippet
    with the new one

    :param strat: ``MeasureGroupStratifier`` object
    :param old: Substring to replace
    :param new: Substring to replace with
    :return: Updated ``MeasureGroupStratifier`` object
    """
    strat.id = strat.id.replace(old, new)
    if fde_coding := next(
        filter(
            lambda c: c.system == "http://fhir-data-evaluator/strat/system",
            strat.code.coding,
        )
    ):
        fde_coding.code = fde_coding.code.replace(old, new)
    return strat


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


def _iter_resource_top_level_elem_defs(
    struct_def: NavStructureDefinition,
) -> Iterator[NavElementDefinition]:
    """
    Returns an iterator of the relevant top level elements of a resource definition, excluding the top level subject
    reference element
    """
    if subject_ref_elem_def := _find_subject_reference_elem_def(struct_def):
        subject_ref_elem_def_id = subject_ref_elem_def.id
    else:
        subject_ref_elem_def_id = None
    for elem_def in struct_def.root.children:
        if (
            elem_def.base.path.startswith("Resource")
            or elem_def.id == subject_ref_elem_def_id
        ):
            continue
        yield elem_def


def _iter_extension_top_level_elem_defs(
    struct_def: NavStructureDefinition,
) -> Iterator[NavElementDefinition]:
    """
    Returns an iterator of the relevant top level elements of an extension definition. If it defines a simple extension
    then the ``Element.value[x]`` is included, otherwise the slice definitions of ``Extension.extension`` are included
    """
    value_elem_def = struct_def.get_element_by_id("Extension.value[x]")
    assert value_elem_def is not None
    if value_elem_def.max == "0":
        # Complex extension definition
        ext_elem_def = struct_def.get_element_by_id("Extension.extension")
        assert ext_elem_def is not None
        yield from ext_elem_def.slices
    else:
        # Simple extension definition
        yield value_elem_def


def _iter_relevant_top_level_elem_defs(
    struct_def: NavStructureDefinition,
) -> Iterator[NavElementDefinition]:
    """
    Using the provided structure definition the function provides an iterator over the relevant top level elements
    (e.g. their element definitions) based on the type and kind of the structure it defines

    :param struct_def: ``NavStructureDefinition`` object to iterate over the relevant top level element definitions for
    :return: Iterator over the relevant top level element definitions
    """
    match struct_def.kind:
        case "resource":
            return _iter_resource_top_level_elem_defs(struct_def)
        case "complex-type":
            match struct_def.type:
                case "Extension":
                    return _iter_extension_top_level_elem_defs(struct_def)
                case _:
                    raise NotImplementedError(
                        "Only 'complex-type' kinded structure definitions profiling type "
                        "'Extension' are supported"
                    )
        case _ as v:
            raise NotImplementedError(f"Unsupported structure definition kind '{v}'")


class StratifierGenerator:
    """
    Given a structure definition instances of this class generate stratifiers for its elements (their definitions).
    Instances are single-use and should be discarded after calling the ``generate`` method
    """
    def __init__(
        self,
        struct_def: NavStructureDefinition,
        package_manager: FhirPackageManager,
        root_exprs: str | dict[str, str] | None = None,
    ):
        self._struct_def = struct_def
        self._package_manager = package_manager
        if isinstance(root_exprs, str):
            self._elem_expr_cache = {
                struct_def.type: root_exprs if root_exprs else struct_def.type
            }
        elif isinstance(root_exprs, dict):
            self._elem_expr_cache = root_exprs
        else:
            self._elem_expr_cache = {
                struct_def.type: struct_def.type
            }

    def _generate_stratifiers_for_extension_elem_def(
        self, elem_def: NavElementDefinition
    ):
        # Base extension element definition stratifier
        rel_expr = _selector_sub_expr_for_elem_def(elem_def, criteria_only=True)
        parent_expr = self._elem_expr_cache[elem_def.parent.id]
        if elem_def.is_slice:
            self._elem_expr_cache[elem_def.id] = (
                parent_expr + ".where(" + rel_expr + ")"
            )
            expr = parent_expr + ".exists(" + rel_expr + ")"
        else:
            expr = parent_expr + "." + rel_expr
            self._elem_expr_cache[elem_def.id] = expr
            expr = expr + ".exists()"
        strats = [_generate_stratifier(expr, elem_def.id)]

        type_info = elem_def.type[0]
        ext_profiles = type_info.profile
        if ext_profiles:
            # When the extension content is defined externally, resolve its structure definition and process its
            # element definition
            root_expr = self._elem_expr_cache[elem_def.id]
            for url in ext_profiles:
                struct_def = self._package_manager.find_struct_def(url)
                if not struct_def:
                    raise FileNotFoundError(
                        f"Could not find StructureDefinition resource defining extension structure '{url}'"
                    )
                strats.extend(
                    _update_strat_identity(
                        strat,
                        "Extension",
                        elem_def.id,
                    )
                    for strat in StratifierGenerator(
                        struct_def,
                        self._package_manager,
                        {"Extension": root_expr, "Extension.extension": f"{root_expr}.extension"},
                    ).generate()
                )
        else:
            # When the extension content is defined inline, process its element definitions normally
            strats.extend(
                strat
                for ed in elem_def.children
                for strat in self._generate_stratifiers_for_elem_def(ed)
            )
        return strats

    def _generate_stratifier_for_reference_elem_def(
        self, elem_def: NavElementDefinition
    ) -> MeasureGroupStratifier:
        rel_expr = (
            _selector_sub_expr_for_elem_def(elem_def)
            + (".ofType(Reference)" if elem_def.id.endswith("[x]") else "")
            + ".reference.hasValue()"
        )
        expr = self._elem_expr_cache[elem_def.parent.id] + "." + rel_expr
        self._elem_expr_cache[elem_def.id] = expr
        return _generate_stratifier(expr, elem_def.id)

    def _generate_stratifiers_for_single_typed_elem_def(
        self, elem_def: NavElementDefinition
    ) -> list[MeasureGroupStratifier]:
        stratifiers = []
        type_info = elem_def.type[0]
        match type_info.code:
            case "Reference":
                stratifiers.append(
                    self._generate_stratifier_for_reference_elem_def(elem_def)
                )
            case _ as type_code:
                rel_expr = _selector_sub_expr_for_elem_def(elem_def)
                if elem_def.id.endswith("[x]"):
                    rel_expr = f"{rel_expr}.ofType({type_code})"
                expr = self._elem_expr_cache[elem_def.parent.id] + "." + rel_expr
                self._elem_expr_cache[elem_def.id] = expr
                stratifiers.append(
                    _generate_stratifier(
                        _ensure_trailing_existence_check(expr, type_code[0].islower()),
                        elem_def.id,
                    )
                )
        return stratifiers

    def _generate_stratifiers_for_elem_def(
        self, elem_def: NavElementDefinition
    ) -> list[MeasureGroupStratifier]:
        stratifiers = []
        if elem_def.max != "0":
            # Dedicated (modifier) extension element definition handling
            if elem_def.base.path in _EXT_ELEM_BASE_PATHS:
                stratifiers.extend(
                    self._generate_stratifiers_for_extension_elem_def(elem_def)
                )
            # All other element definitions
            else:
                if (
                    elem_def.is_slice
                    or elem_def.base.path
                    not in _BASE_PATHS_EXCLUDED_FROM_STRATIFIER_GEN
                ):
                    if elem_def.type and len(elem_def.type) == 1:
                        stratifiers.extend(
                            self._generate_stratifiers_for_single_typed_elem_def(
                                elem_def
                            )
                        )
                    else:
                        expr = (
                            self._elem_expr_cache[elem_def.parent.id]
                            + "."
                            + _selector_sub_expr_for_elem_def(elem_def)
                        )
                        self._elem_expr_cache[elem_def.id] = expr
                        stratifiers.append(
                            _generate_stratifier(
                                _ensure_trailing_existence_check(
                                    expr, not _could_be_complex_typed(elem_def)
                                ),
                                elem_def.id,
                            )
                        )
                for child_elem_def in elem_def.children:
                    stratifiers.extend(
                        self._generate_stratifiers_for_elem_def(child_elem_def)
                    )
        return stratifiers

    def generate(self) -> list[MeasureGroupStratifier]:
        """
        Generates a list of stratifiers for the given structure definition
        :return: List of stratifiers
        """
        stratifiers = []
        for elem_def in _iter_relevant_top_level_elem_defs(self._struct_def):
            stratifiers.extend(self._generate_stratifiers_for_elem_def(elem_def))
        return stratifiers


def _find_subject_reference_elem_def(
    profile: NavStructureDefinition,
) -> NavElementDefinition | None:
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


def generate_measure_group_for_struct_def(
    struct_def: NavStructureDefinition, package_manager: FhirPackageManager, id_num: int
) -> MeasureGroup:
    """
    Generates a `MeasureGroup` resource for the given `StructureDefinition` resource

    :param struct_def: StructureDefinition resource to generate the measure group for
    :param package_manager: FHIR package manager to use for resolving references to other structure definitions
    :param id_num: Unique number for the measure group
    :return: MeasureGroup resource
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

    stratifier_generator = StratifierGenerator(struct_def, package_manager)
    grp_strats = stratifier_generator.generate()
    measure_group.stratifier.extend(grp_strats)
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


def generate_element_availability_measure(project: Project, **elements) -> Measure:
    """
    Generates the Element Availability Measure resource

    :param project: Project to generate the measure for. The included profiles are determined using the
                    ``profiles.include`` section
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
    for struct_def in project.included_profiles(latest_only=True):
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
                generate_measure_group_for_struct_def(
                    struct_def, project.package_manager, group_id_num
                )
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
    measure = make_stratifier_codes_fde_compatible(project.package_manager, measure)
    return update_stratifier_ids(measure)
