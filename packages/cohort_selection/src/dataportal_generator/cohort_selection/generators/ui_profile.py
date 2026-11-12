from collections.abc import Sequence
from typing import Mapping

from dataportal_generator.cohort_selection.model.concept_tree import CRITERION_VALUE_KEY, CRITERION_IDENTIFIER_KEY
from dataportal_generator.cohort_selection.model.criterion import CriterionDefinition, CriterionAttribute
from dataportal_generator.cohort_selection.model.ui import (
    ValueDefinition,
    UIProfile,
    AttributeDefinition,
    CriteriaSet,
)
from dataportal_generator.cohort_selection.util.fhir import split_canonical, extract_designation
from dataportal_generator.cohort_selection.util.io import load_criterion_mapping, load_criterion_definitions
from dataportal_generator.common.fhirpath.resolvers import FHIRPathResolver
from dataportal_generator.common.log.functions import get_logger
from dataportal_generator.common.model.fhir.nav_element_definition import NavElementDefinition
from dataportal_generator.common.model.fhir.nav_structure_definition import NavStructureDefinition
from dataportal_generator.common.model.localization import TranslationDisplayElement, Translation
from dataportal_generator.common.model.project import Project

from dataportal_generator.common.model.terminology import TermCode

_logger = get_logger(__name__)

_UCUM_SYSTEM = "http://unitsofmeasure.org"
_AGE_UNIT_VALUE_SET = "http://hl7.org/fhir/ValueSet/age-units"
_TRANSLATION_EXT_URL = "http://hl7.org/fhir/StructureDefinition/translation"
_FHIR_TYPES_TO_UI_TYPES = {
    "code": "concept",
    "Coding": "concept",
    "CodeableConcept": "concept",
    "Quantity": "quantity",
    "Reference": "reference"
}


class UIProfileGenerationError(Exception):
    pass


class MissingDisplayError(Exception):
    pass


def _is_time_restriction_allowed(
    crit_def: CriterionDefinition,
) -> bool:
    """
    Returns whether time restriction is allowed for the given criterion definition
    """
    return crit_def.time_restriction is not None


def _get_display_from_element_definition(
    elem_def: NavElementDefinition
) -> TranslationDisplayElement:
    """
    Extracts a display value from the given element definition. The display value is extracted from the following
    fields in order of preference:

    1) ``ElementDefinition.label``
    2) ``ElementDefinition.short``
    3) ``ElementDefinition.definition``
    4) Fallback to the element ID if none of the above fields are set

    For the cases 1-3 translations are extracted from the corresponding extensions

    :param elem_def: Element definition to extract the display value from
    :return: ``TranslationDisplayElement`` object containing the display value and any translations
    """
    value = elem_def.label
    value_ext = elem_def.label__ext
    if not value:
        value = elem_def.short
        value_ext = elem_def.short__ext
    if not value:
        value = elem_def.definition
        value_ext = elem_def.definition__ext
    if not value:
        # Fallback
        _logger.debug(f"Defaulting to element ID-based display value for element {elem_def.struct_def}|{elem_def.id} "
                      f"since no descriptive element was found")
        return TranslationDisplayElement(original=elem_def.rel_id)

    display = TranslationDisplayElement(original=value)
    for lang_ext in filter(lambda ext: ext.url == _TRANSLATION_EXT_URL, value_ext.extension if value_ext else []):
        lang_code = next(filter(lambda ext: ext.url == "lang", lang_ext.extension)).valueCode
        lang_value = next(filter(lambda ext: ext.url == "content", lang_ext.extension)).valueString
        display.translations.append(
            Translation(language=lang_code, value=lang_value)
        )

    return display


def _ui_attr_type_for_fhir_type(fhir_dt: str) -> str:
    try:
        return _FHIR_TYPES_TO_UI_TYPES[fhir_dt]
    except KeyError:
        raise KeyError(f"Unsupported FHIR data type {fhir_dt!r} for UI attribute type mapping")


class UIProfileGenerator:
    """
    This class is responsible for generating UI profiles for a given FHIR profile.
    """

    def __init__(self, project: Project):
        """
        :param project: Project to operate on
        """
        self.__project = project
        self.__term_src = self.__project.terminology_src
        self.__fp_resolver = FHIRPathResolver(self.__project.package_manager)
        self.__criterion_mapping = load_criterion_mapping(self.__project)

    def generate_ui_profile(
        self, criterion_def: CriterionDefinition
    ) -> UIProfile:
        """
        Generates a UI profile for the given criterion definition
        :param criterion_def: ``CriterionDefinition`` instance to generate a UI profile for
        :return: UI profile
        """
        struct_def = self.__project.package_manager.find_struct_def(criterion_def.definition_source.structure_definition)
        ui_profile = UIProfile(name=criterion_def.name)
        ui_profile.timeRestrictionAllowed = _is_time_restriction_allowed(criterion_def)
        if criterion_def.value:
            ui_profile.valueDefinition = self._get_value_definition(
                struct_def, criterion_def
            )
        for attr_def in criterion_def.attributes:
            ui_profile.attributeDefinitions.append(self._generate_attribute_definition(struct_def, criterion_def, attr_def))
        return ui_profile

    def _get_allowed_units_from_quantity(
        self,
        q_def_elem_def: NavElementDefinition,
    ) -> list[TermCode]:
        """
        Get allowed unit values using the given quantity defining element definition. Searches any patterns and fixed
        values on paths `Quantity` and `Quantity.code`. If no fixed value can be identified at these definition they
        are searched for value set bindings

        :param q_def_elem_def: Quantity defining element as specified in the criterion definition
        :return: List of ``TermCode`` objects representing the allowed units
        :raise ValueError: if no unique unit can be determined
        """
        val_def_struct_def = q_def_elem_def.struct_def
        if not q_def_elem_def.supports_type("Quantity"):
            raise TypeError(f"Element/slice {val_def_struct_def.name}|{q_def_elem_def.id} does not support FHIR "
                            f"data type 'Quantity'. No units can be determined")
        unit_def_elem_def = q_def_elem_def.child("code")
        # Try fixed code values
        if unit_def_elem_def:
            unit_code = unit_def_elem_def.fixedCode if unit_def_elem_def.fixedCode else unit_def_elem_def.patternCode
            if unit_code:
                unit_display = unit_code
                # The actual UCUM display value should be used instead of the code as the term code display value.
                # However, resolution via the term server is not possible ATM due to nature of the UCUM code system
                if display_def_elem_def := q_def_elem_def.child("display"):
                    unit_display = display_def_elem_def.fixedString if display_def_elem_def.fixedString else display_def_elem_def.patternString
                return [TermCode(system=_UCUM_SYSTEM, code=unit_code, display=unit_display)]
            if (binding := unit_def_elem_def.binding) and (vs_canonical := binding.valueSet):
                url, version = split_canonical(vs_canonical)
                vs = self.__project.terminology_src.expand_value_set(url, version)
                return [TermCode(system=c.system, code=c.code, version=c.version, display=c.display) for c in (vs.expansion.contains or [])]
        # Try quantity pattern
        if (fixed_q := q_def_elem_def.fixedQuantity) and fixed_q.code:
            return [TermCode(
                system=fixed_q.system or _UCUM_SYSTEM,
                code=fixed_q.code,
                display=fixed_q.unit or fixed_q.code,
            )]
        if (pattern_q := q_def_elem_def.patternQuantity) and pattern_q.code:
            return [TermCode(
                system=pattern_q.system or _UCUM_SYSTEM,
                code=pattern_q.code,
                display=pattern_q.unit or pattern_q.code,
            )]
        # Try value set binding
        binding = unit_def_elem_def.binding if unit_def_elem_def else q_def_elem_def.binding
        if binding and (vs_canonical := binding.valueSet):
            url, version = split_canonical(vs_canonical)
            vs = self.__project.terminology_src.expand_value_set(url, version)
            return [TermCode(system=c.system, code=c.code, version=c.version, display=c.display) for c in (vs.expansion.contains or [])]
        raise ValueError(f"Value defining element/slice {val_def_struct_def.name}|{q_def_elem_def.id} does not "
                         f"define any unit code. No unique unit can be determined")

    def _lookup_designations(
        self, system: str, code: str, languages: Sequence[str], version: str | None = None, fuzzy: bool = True
    ) -> Mapping[str, str]:
        """
        Looks up all available designations for the given coding matching the provided language codes.
        If the coding includes no version then all code system versions supported by the server will be retrieved and
        used to look up the designations.

        **WARNING**: This method should not be called repeatedly for a large number of codings as the requests to the
        terminology server take a relatively long time

        :param system: Code system URL
        :param code: Code string
        :param languages: Language codes to match designations with. They should represent values set in
                          `CodeSystem.concept.designation.language`
        :param version: (Optional) code system version string
        :param fuzzy: Controls whether fuzzy matching is enabled when matching the languages codes. If `True` matches
                      will be determined using the regex `^{language}(-\\S+)?$`
        :return: Map containing the language codes mapped to their designations
        """
        params = self.__term_src.lookup_code(system, code, version)
        lang_map = {}
        for lang in languages:
            if lang_val := extract_designation(params, lang, fuzzy):
                lang_map[lang] = lang_val
        return lang_map

    def _get_value_definition(
        self, struct_def: NavStructureDefinition, crit_def: CriterionDefinition
    ) -> ValueDefinition:
        """
        Returns the value definition for the given criterion definition
        :param struct_def: FHIR StructureDefinition resource defining the criterion content
        :param crit_def: ``CriterionDefinition`` instance to generate a value definition for
        :return: value definition
        :raises InvalidValueTypeException: if the value type is not supported
        """
        crit_val = crit_def.value
        val_def_struct_def, val_def_elem_def = self.__fp_resolver.resolve_leaf(struct_def, crit_val.definition.expression)
        value_type = crit_val.type
        # The only way the value_type equals "code" is if the query_meta_data sets it to "code". This might be necessary
        # for the mapping but the UI profile only supports "concept" so we have to convert it here.
        if value_type == "code":
            value_type = "concept"
        value_definition = ValueDefinition(type=value_type)
        value_definition.optional = value_definition.optional
        if value_type == "concept":
            value_definition.referencedValueSet.extend(
                self.__criterion_mapping[crit_def.module][crit_def.name][CRITERION_VALUE_KEY]
            )
        elif value_type == "quantity":
            value_definition.allowedUnits = self._get_allowed_units_from_quantity(
                val_def_elem_def
            )
        elif value_type == "age":
            value_definition.type = "quantity"
            # FIXME: Constraints should be expressed by an FDPG+-own value set
            value_definition.allowedUnits = [
                TermCode(system=_UCUM_SYSTEM, code="a", display="a"),
                TermCode(system=_UCUM_SYSTEM, code="mo", display="mo"),
            ]
        elif value_type == "integer":
            value_definition.type = "quantity"
        elif value_type == "calculated":
            pass
        elif value_type == "reference":
            raise ValueError(
                "Reference type needs to be resolved using FHIRPath 'resolve()' function invocation"
            )
        else:
            raise ValueError(
                f"Invalid value type {value_type!r} in criterion {crit_def.name!r}"
            )
        value_definition.display = _get_display_from_element_definition(val_def_elem_def)
        return value_definition

    def _generate_attribute_definition(
        self,
        crit_def_struct_def: NavStructureDefinition,
        crit_def: CriterionDefinition,
        attr_def: CriterionAttribute
    ) -> AttributeDefinition:
        """
        Returns an attribute definition for the given attribute defining element
        :param crit_def_struct_def: FHIR StructureDefinition resource defining the criterion content
        :param crit_def: CriterionDefinition defining the attribute
        :param attr_def: CriterionAttribute instance to generate an attribute definition for
        :return: Attribute definition
        """
        attr_def_struct_def, attr_def_elem_def = self.__fp_resolver.resolve_leaf(crit_def_struct_def, attr_def.definition.expression)
        if not (attr_type := attr_def.type):
            dt_codes = [t.code for t in attr_def_elem_def.type]
            if len(dt_codes) > 1:
                _logger.warning(f"Ambiguous FHIR data types {dt_codes!r} for attribute {attr_def.name!r}. Using first "
                                f"entry as attribute type")
            attr_type = attr_def.type if attr_def.type else _ui_attr_type_for_fhir_type(dt_codes[0])
        attribute_definition = AttributeDefinition(
            attributeCode=TermCode(
                system="http://hl7.org/fhir/StructureDefinition",
                code=attr_def.name,
                display=attr_def.name
            ),
            type=attr_type,
            optional=attr_def.optional
        )
        attribute_definition.display = _get_display_from_element_definition(attr_def_elem_def)
        if attr_type == "concept":
            # TODO: What if a concept tree group consists (partially) of fixed codes? Does the data model support this?
            attribute_definition.referencedValueSet = self.__criterion_mapping[crit_def.module][crit_def.name][attr_def.name]
        elif attr_type == "quantity":
            attribute_definition.allowedUnits = self._get_allowed_units_from_quantity(attr_def_elem_def)
        elif attr_type == "reference":
            attribute_definition.referencedCriteriaSet = self._get_reference_criteria_set(attr_def_elem_def)
        elif attr_type == "composite":
            raise NotImplementedError(f"Composite attribute type is not yet supported for criterion attributes")
        else:
            raise TypeError(f"Invalid attribute value type {attr_type!r}")
        return attribute_definition


    def _criteria_for_profiles(self, profile_urls: Sequence[str]) -> list[CriterionDefinition]:
        """
        Returns a list of criterion definitions for the given profile URLs
        :param profile_urls: List of FHIR profile URLs to get the criterion definitions for
        :return: List of criterion definitions
        """
        all_profiles = set()
        for p_url in profile_urls:
            all_profiles.add(p_url)
            all_profiles.update(dep.url for dep in self.__project.package_manager.dependents_of(p_url))
        matching_crit_defs = []
        for _, crit_defs in load_criterion_definitions(self.__project).items():
            for crit_def in crit_defs:
                if crit_def.definition_source.structure_definition in all_profiles:
                    matching_crit_defs.append(crit_def)
        return matching_crit_defs


    def _get_reference_criteria_set(
        self, ref_def_elem_def: NavElementDefinition
    ) -> list[CriteriaSet]:
        """
        Returns a list of criteria sets representing criteria that are eligible targets for the given reference
        defining element/slice
        :param ref_def_elem_def: ``NavElementDefinition`` instance representing the reference defining element/slice
        :return: List of criteria sets
        """
        ref_type = ref_def_elem_def.type_info_for("Reference")
        if not ref_type:
            raise ValueError(f"Reference defining element/slice '{ref_def_elem_def.struct_def.name}|"
                             f"{ref_def_elem_def.id}' does not support FHIR data type 'Reference'")
        crit_defs = self._criteria_for_profiles(ref_type.targetProfile)
        if not crit_defs:
            raise UIProfileGenerationError(f"No criteria can be the target of the reference defined in element/slice "
                                           f"'{ref_def_elem_def.struct_def.name}|{ref_def_elem_def.id}'")
        crit_sets = []
        for crit_def in crit_defs:
            crit_sets.append(CriteriaSet(
                url=CriteriaSet.UrlBase + f"/{crit_def.module}/{crit_def.name}",
                context=crit_def.context,
                tree_groups=self.__criterion_mapping[crit_def.module][crit_def.name][CRITERION_IDENTIFIER_KEY],
            ))
        return crit_sets


def generate_ui_profiles(project: Project, modules: list[str] | None = None) -> None:
    """
    Generates UI profiles for all modules defined in the given project. Generated UI profiles are written to
    ``<project_dir>/output/cohort_selection/ui/ui_profiles.json``
    :param project: Project to generate the mapping for
    :param modules: List of module names to generate UI profiles for. If ``None`` then all modules are considered
    """
    try:
        generator = UIProfileGenerator(project)
        output_file = project.output.cohort_selection / "ui" / "ui_profiles.json"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with output_file.open(mode="wb") as out_fd:
            out_fd.write(b"[")
            first = True
            for mod, crit_defs in load_criterion_definitions(project).items():
                if not modules or mod in modules:
                    _logger.info(f"Generating UI profiles for module '{mod}'")
                    for crit_def in crit_defs:
                        _logger.info(f"Generating UI profile for criterion {crit_def.name!r}")
                        ui_profile = generator.generate_ui_profile(crit_def)
                        if not first:
                            out_fd.write(b",")
                        else:
                            first = False
                        out_fd.write(ui_profile.model_dump_json(by_alias=True, exclude_none=True).encode("utf-8"))
            out_fd.write(b"]")
    except Exception as x:
        _logger.error(f"Failed to generate UI profiles: {x}")
        raise UIProfileGenerationError("Failed to generate UI profiles") from x
