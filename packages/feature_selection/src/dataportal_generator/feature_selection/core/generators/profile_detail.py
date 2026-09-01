import json
import re
from collections.abc import Mapping
from typing import Any

import cachetools
from common.constants.fhir import FHIR_PRIMITIVES
from dataportal_generator.common.exceptions.profile import MissingProfileError
from dataportal_generator.common.fhir.structure_definition import (
    get_parent_element,
    get_types_supported_by_element,
)
from dataportal_generator.common.fhirpath.resolvers import FHIRPathResolver
from dataportal_generator.common.log.functions import get_logger
from dataportal_generator.common.model.fhir.nav_element_definition import (
    NavElementDefinition,
)
from dataportal_generator.common.model.fhir.nav_structure_definition import (
    NavStructureDefinition,
)
from dataportal_generator.common.model.project import Project
from dataportal_generator.feature_selection.core.exceptions import (
    ProfileDetailFieldGenerationException,
    ProfileDetailGenerationException,
)
from dataportal_generator.feature_selection.util.fhir.profile import (
    extract_module_string,
)
from fhir.resources.R4B.elementdefinition import (
    ElementDefinition,
    ElementDefinitionBinding,
)

from cohort_selection_ontology.model.ui_data import (
    BulkTranslationDisplayElement,
    Translation,
    TranslationDisplayElement,
)
from data_selection_extraction.config.profile_detail import FieldsConfig
from data_selection_extraction.model.detail import (
    FieldDetail,
    Filter,
    ProfileDetail,
    ProfileReference,
    ReferenceDetail,
)
from data_selection_extraction.model.profile_tree import ProfileTreeNode

_logger = get_logger(__file__)

_EXT_ELEM_PATTERN = re.compile(
    r".*extension(:(?P<slice_name>[a-zA-Z0-9\/\\\-_\[\]\@]+))?"
)

SEARCH_FILTER_MAPPING_FILE_NAME = "search_filter_mapping.json"


_BINDING_STRENGTH_LEVELS = {
    "example": 0,
    "extensible": 1,
    "preferred": 2,
    "required": 3,
}


def _get_name_from_id(element_id: str) -> str:
    name = element_id.split(".")[-1]
    name = name.split(":")[-1]
    name = name.replace("[x]", "")
    return name


def _get_value_for_lang_code(data: ElementDefinition, lang_code: str) -> str | None:
    if data is None:
        return None
    for ext in data.extension:
        if any(e.url == "lang" and e.valueCode == lang_code for e in ext.extension):
            return next(e.valueString for e in ext.extension if e.url == "content")
    return None


def _get_element_by_content_ref(
    content_ref: str, struct_def: NavStructureDefinition
) -> NavElementDefinition | None:
    return struct_def.get_element_by_id(content_ref[1:])


def _get_coded_elem_def_bindings(
    elem_def: NavElementDefinition,
) -> list[ElementDefinitionBinding]:
    type_info = elem_def.type[0]
    eligible_children = elem_def.slices
    match type_info.code:
        case "CodeableConcept":
            if coding_elem_def := elem_def.element("coding"):
                eligible_children.append(coding_elem_def)
        case "Coding":
            if code_elem_def := elem_def.element("code"):
                eligible_children.append(code_elem_def)
        case "code":
            pass
        case _ as v:
            raise TypeError(
                f"Unsupported FHIR data type '{v}' of element definition '{elem_def.id}' for code "
                f"filter"
            )
    descendant_bindings = [
        b for ed in eligible_children for b in _get_coded_elem_def_bindings(ed)
    ]
    binding = elem_def.binding
    if binding and not binding.valueSet:
        binding = None
    if descendant_bindings:
        if binding and all(
            _BINDING_STRENGTH_LEVELS[binding.strength]
            <= _BINDING_STRENGTH_LEVELS[b.strength]
            for b in descendant_bindings
        ):
            return descendant_bindings
        else:
            return [binding, *descendant_bindings]
    else:
        return [binding] if binding else []


def _get_profile_title_display(
    profile_snapshot: NavStructureDefinition,
) -> TranslationDisplayElement | None:
    title = profile_snapshot.title
    if title is None:
        return None
    else:
        _title = profile_snapshot.title__ext
        return TranslationDisplayElement(
            original=title,
            translations=[
                Translation(
                    language="de-DE", value=_get_value_for_lang_code(_title, "de-DE")
                ),
                Translation(
                    language="en-US", value=_get_value_for_lang_code(_title, "en-US")
                ),
            ],
        )


class ProfileDetailGenerator:
    blacklisted_values_sets: list[str]
    profiles: Mapping[str, Mapping[str, Mapping[str, Any]]]
    mapping_type_code: Mapping[str, dict]
    fields_config: FieldsConfig
    reference_base_url: str

    def __init__(
        self,
        project: Project,
        profiles,
        mapping_type_code,
        blacklisted_value_sets,
        fields_config: FieldsConfig,
        reference_base_url,
        module_translation,
    ):
        """
        Generate details for all given profiles
        :param project: project for which the details should be generated
        :param profiles: list of profiles for which the details should be generated.
            It should receive tree_generator.profiles
        :param mapping_type_code: Mapping of FHIR resource types to their code FHIRPath filters
        :param blacklisted_value_sets: list of valueSet-urls which should not be used
        :param fields_config: `FieldsConfig` object describing what fields
        :param reference_base_url: base url for resolving references for non fhir packages
        :param module_translation: mapping containing translation of module names
        """
        self.__project = project
        self.blacklisted_value_sets = blacklisted_value_sets
        self.profiles = profiles
        # Prevents having to generate the mapping over and over again
        self.__all_profiles = self.__get_profiles()
        self.mapping_type_code = mapping_type_code
        self.fields_config = fields_config
        self.reference_base_url = reference_base_url
        self.module_translation = module_translation

        self.__included_struct_defs = {
            sd.url: sd for sd in self.__project.included_profiles(latest_only=True)
        }
        self.__fp_resolver = FHIRPathResolver(self.__project.package_manager)

        self.__is_included_cache = {}
        self.__is_required_cache = {}
        self.__is_recommended_cache = {}

        if (path := project.input.dse / SEARCH_FILTER_MAPPING_FILE_NAME).exists():
            _logger.info(f"Found search filter mapping @ {path!r}")
            with path.open(mode="r", encoding="utf-8") as f:
                self.__search_filter_mapping = json.load(f)
        else:
            _logger.warning(
                f"Found no search filter mapping @ {path!r} => Defaults will be used"
            )
            self.__search_filter_mapping = {}

    @cachetools.cachedmethod(
        cache=lambda self: self.__is_included_cache,
        key=lambda _, ed, pr: pr.url + "#" + ed.id,
    )
    def is_field_included(
        self, elem_def: ElementDefinition, profile: NavStructureDefinition
    ) -> bool:
        if profile.get_aggregated_max_cardinality(elem_def.id) == 0:
            return False
        is_included = self.fields_config.is_included(
            elem_def, profile, self.__project.package_manager
        )
        if is_included is None:
            return not self.filter_element(elem_def, profile)
        else:
            return is_included

    @cachetools.cachedmethod(
        cache=lambda self: self.__is_required_cache,
        key=lambda _, ed, pr: pr.url + "#" + ed.id,
    )
    def is_field_required(
        self, elem_def: ElementDefinition, profile: NavStructureDefinition
    ) -> bool:
        if profile.get_aggregated_max_cardinality(elem_def.id) == 0:
            return False
        is_required = self.fields_config.is_required(
            elem_def, profile, self.__project.package_manager
        )
        if is_required is None:
            return False
        else:
            return is_required

    @cachetools.cachedmethod(
        cache=lambda self: self.__is_recommended_cache,
        key=lambda _, ed, pr: pr.url + "#" + ed.id,
    )
    def is_field_recommended(
        self, elem_def: ElementDefinition, profile: NavStructureDefinition
    ) -> bool:
        if profile.get_aggregated_max_cardinality(elem_def.id) == 0:
            return False
        is_recommended = self.fields_config.is_recommended(
            elem_def, profile, self.__project.package_manager
        )
        if is_recommended is None:
            # Field is only recommended if it is required and its parent element definition is recommended as well
            if parent_elem_def := get_parent_element(profile, elem_def):
                parent_recommended = self.is_field_recommended(parent_elem_def, profile)
            else:
                parent_recommended = True
            return parent_recommended and elem_def.min == 1
        else:
            return is_recommended

    def __get_value_sets_for_code_filter(
        self, struct_def: NavStructureDefinition, fhir_path: str
    ) -> list[str]:
        """
        Using a FHIR StructureDefinition and a FHIRPath expression, find the target element definition starting from the
        StructureDefinition and find the bound value sets to use for a code filter

        :param struct_def: ``NavStructureDefinition`` object representing the starting context of the FHIRPath
                           expression
        :param fhir_path: FHIRPath expression string to resolve against the StructureDefinition
        :return: List of URLs of bound value sets
        """
        struct_def, elem_def = self.__fp_resolver.resolve_leaf(struct_def, fhir_path)
        if not elem_def:
            raise ValueError(
                f"FHIRPath expression '{fhir_path}' cannot be resolved to an element definition against "
                f"structure definition '{struct_def}'"
            )
        bindings = _get_coded_elem_def_bindings(elem_def)
        if not bindings:
            raise ValueError(
                f"Element definition '{elem_def.id}' of structure definition '{struct_def.url}' cannot be "
                f"used as a code filter since it or its descendants define no value set bindings"
            )
        return [b.valueSet for b in bindings]

    def __insert_field_into_profile_detail(
        self,
        profile_detail: ProfileDetail,
        field: FieldDetail | ReferenceDetail,
        elem_def: NavElementDefinition,
    ):
        # TODO: This is a temporary workaround to allow both the postal code and the country information to be selected
        #       during data selection. To preserve context, selecting elements with simple data types which are not on
        #       the top level of a resource is disabled (e.g. to forbid selecting just Coding.code without
        #       Coding.system etc.).
        #       In the future we should switch to a more dynamic solution were the selectable elements can be defined in
        #       externalized config files using a well-defined syntax to prevent such hard-coded solutions.
        if (
            field.type in FHIR_PRIMITIVES
            and elem_def.parent.parent is not None
            and field.id
            not in {
                "Patient.address:Strassenanschrift.postalCode",
                "Patient.address:Strassenanschrift.country",
            }
        ):
            return

        parent_recommended = False
        match field.type:
            case "Reference":
                fields = profile_detail.references
            case _:
                fields = profile_detail.fields
        while True:
            if current_field := next(
                (f for f in fields if field.id.startswith(f.id)), None
            ):
                fields = current_field.children
                if not parent_recommended:
                    parent_recommended = current_field.recommended
                if parent_recommended:
                    field.recommended = False
            else:
                fields.append(field)
                break

    def __filter_element(
        self, elem_def: NavElementDefinition, struct_def: NavStructureDefinition
    ) -> bool:
        # TODO: This is a temporary workaround to allow both the postal code and the country information to be selected
        #       during data selection. To preserve context, selecting elements with simple data types which are not on
        #       the top level of a resource is disabled (e.g. to forbid selecting just Coding.code without
        #       Coding.system etc.).
        #       In the future we should switch to a more dynamic solution were the selectable elements can be defined in
        #       externalized config files using a well-defined syntax to prevent such hard-coded solutions.
        if elem_def.id in {
            "Patient.address:Strassenanschrift.postalCode",
            "Patient.address:Strassenanschrift.country",
        }:
            return False

        if (
            getattr(elem_def, "subject", None) is not None
            or getattr(elem_def, "patient", None) is not None
        ):
            _logger.info(f"Excluding: '{elem_def.id}' as having references to patients")
            return True

        # attributes_true_level_two = ["mustSupport", "isModifier"]

        if len(elem_def.id.split(".")) > 2 and all(
            t.code in FHIR_PRIMITIVES for t in get_types_supported_by_element(elem_def)
        ):
            _logger.debug(
                f"Excluding: '{elem_def.id}' as primitively-typed on level > 2"
            )
            return True

        parent_elem = elem_def.parent
        # Exclude all sub-elements of primitive FHIR data types
        if (
            not elem_def.supports_type("Extension")
            and parent_elem.types
            and all(t.code in FHIR_PRIMITIVES for t in parent_elem.types)
        ):
            return True

        if matches := [*_EXT_ELEM_PATTERN.finditer(elem_def.id)]:
            # If the element is itself or a child of an unsliced 'extension' element it will be excluded
            for m in matches:
                if not m.group("slice_name"):
                    return True
            # All but the sliced extension element itself will be excluded
            return (m := matches[-1]).group("slice_name") and m.end("slice_name") < len(
                elem_def.id
            )

        # Do not allow sub elements (that are not a reference) of BackboneElement or Identifier typed elements to be
        # selected
        elem_id_split = elem_def.id.rsplit(".", maxsplit=1)
        if len(elem_id_split) == 1:
            return False
        parent_elem = struct_def.get_element_by_id(elem_id_split[0])
        elem = struct_def.get_element_by_id(elem_def.id)
        supports_ref = elem.supports_type("Reference")
        while parent_elem is not None:
            if (
                parent_elem.supports_type("BackboneElement")
                or parent_elem.supports_type("Identifier")
            ) and not supports_ref:
                return True
            elem_id_split = parent_elem.id.rsplit(".", maxsplit=1)
            if len(elem_id_split) == 1:
                return False
            parent_elem = struct_def.get_element_by_id(elem_id_split[0])

        return False

    def resource_type_to_date_param(self, resource_type: str) -> str | None:
        if resource_type in self.__search_filter_mapping:
            # NOTE: Having an explicit null value in the mapping indicates that there is no applicable search parameter
            return self.__search_filter_mapping[resource_type]
        else:
            _logger.warning(
                "No search parameter defined for resource type '%s' => No such filter will be supported",
                resource_type,
            )
            return None

    def __get_referenced_struct_defs_that_are_included(
        self, elem_def: NavElementDefinition
    ) -> list[NavStructureDefinition]:
        """
        Aggregates a list of URLs of structure definitions that can be referenced by instances of this element
        definition that are included via the project config

        :param elem_def: NavElementDefinition instance for which to find MII profiles it supports
        :return: List of structure definitions supported by the reference element definition
        """
        referenced_struct_defs = []
        target_profiles = elem_def.type_info_for("Reference").targetProfile
        for profile_url in target_profiles:
            if profile_url in self.__included_struct_defs:
                referenced_struct_defs.append(profile_url)
            for dep in self.__project.package_manager.dependents_of(profile_url):
                if dep.url in self.__included_struct_defs:
                    referenced_struct_defs.append(dep)
        return referenced_struct_defs

    def __get_ext_ref_value_elem_def(
        self, elem_def: NavElementDefinition
    ) -> NavElementDefinition | None:
        """
        Returns the ``Extension.value[x]/:valueReference`` element if it exists
        """
        type_info = elem_def.type_info_for("Extension")
        if not type_info:
            raise ValueError(
                f"Element '{elem_def.id}' does not support FHIR data type 'Extension'"
            )
        if extension_profiles := type_info.profile:
            # Type element does contain Extension profile references
            ref_struct_def = self.__project.package_manager.find_struct_def(
                extension_profiles[0]
            )
            if not ref_struct_def:
                _logger.warning(
                    f"Extension '{extension_profiles[0]}' was not found => Ignoring potential references"
                )
                return None
            else:
                val_elem_def = ref_struct_def.get_element_by_id("Extension.value[x]")
                if ref_slice_elem_def := val_elem_def.slice("valueReference"):
                    val_elem_def = ref_slice_elem_def
                if (
                    not val_elem_def
                    or val_elem_def.max == "0"
                    or not val_elem_def.supports_type("Reference")
                ):
                    return None
                else:
                    return val_elem_def
        elif value_elem_def := elem_def.element("value[x]"):
            # Type element does not contain any Extension profile references
            return value_elem_def if value_elem_def.supports_type("Reference") else None
        else:
            return None

    def generate_detail_for_elem_def(
        self, elem_def: NavElementDefinition
    ) -> FieldDetail | None:
        field_id = elem_def.id

        if content_reference := elem_def.contentReference:
            elem_def = _get_element_by_content_ref(
                content_reference, elem_def.struct_def
            )

        supported_types = get_types_supported_by_element(elem_def)
        field_type = None
        # TODO: Add support for polymorphic elements
        if len(supported_types) > 1:
            _logger.debug(
                f"Element '{elem_def.id}' supports multiple types but only fixed typed "
                f"elements can be represented faithfully at this point => Proceeding with "
                f"first type listed"
            )
            field_type = supported_types[0].code
        elif len(supported_types) == 0:
            field_type = None

        if elem_def.supports_type("Reference"):
            supports_reference = True
        elif elem_def.supports_type("Extension") and (
            ext_val_elem_def := self.__get_ext_ref_value_elem_def(elem_def)
        ):
            supports_reference = True
            elem_def = ext_val_elem_def
        else:
            supports_reference = False

        # FIXME: Temporary fix to make elements of type 'Reference' not recommended due to issues in the UI
        #        except for references to the MII Medication profile
        if supports_reference:
            field_type = "Reference"
        #   if not ".medication" in field_id:
        #        is_recommended_field = False

        is_required_field = self.is_field_required(elem_def, elem_def.struct_def)

        # FIXME: Temporary fix to make elements of type 'Reference' not recommended due to issues in the UI
        #        except for references to the MII Medication profile
        # if field_type == "Reference" and not ".medication" in field_id:
        #    is_recommended_field = False

        is_recommended_field = self.is_field_recommended(elem_def, elem_def.struct_def)

        name = _get_name_from_id(elem_def.id)

        if supports_reference:
            try:
                included_referenced_profiles = (
                    self.__get_referenced_struct_defs_that_are_included(elem_def)
                )
                included_referenced_profile_refs = [
                    ProfileReference(
                        url=struct_def.url,
                        display=_get_profile_title_display(struct_def),
                        fields=BulkTranslationDisplayElement(),  # self.__get_fields_for_profile(url, profile_tree),
                    )
                    for struct_def in included_referenced_profiles
                ]
            except MissingProfileError as exc:
                raise ProfileDetailFieldGenerationException(
                    f"Could not resolve referenced profiles of element definition '{elem_def.id}']. Reason: {exc}"
                ) from exc

            if len(included_referenced_profile_refs) == 0:
                _logger.debug(
                    f"Element definition '{elem_def.id}' references only profiles that are not included => Discarding"
                )
                return None

            field = ReferenceDetail(
                id=field_id, referencedProfiles=included_referenced_profile_refs
            )
        else:
            field = FieldDetail(id=field_id)
            field.type = field_type

        field.display = TranslationDisplayElement(
            original=name,
            translations=[
                Translation(
                    language="de-DE",
                    value=_get_value_for_lang_code(elem_def.short__ext, "de-DE"),
                ),
                Translation(
                    language="en-US",
                    value=_get_value_for_lang_code(elem_def.short__ext, "en-US"),
                ),
            ],
        )
        field.description = TranslationDisplayElement(
            original=str(elem_def.definition),
            translations=[
                Translation(
                    language="de-DE",
                    value=_get_value_for_lang_code(elem_def.definition__ext, "de-DE"),
                ),
                Translation(
                    language="en-US",
                    value=_get_value_for_lang_code(elem_def.definition__ext, "en-US"),
                ),
            ],
        )
        field.recommended = is_recommended_field
        field.required = is_required_field
        return field

    def generate_detail_for_profile_tree_node(
        self, profile_tree_node: ProfileTreeNode
    ) -> ProfileDetail:
        profile_url = profile_tree_node.url
        _logger.info(f"Generating profile detail [url='{profile_url}']")

        try:
            struct_def: NavStructureDefinition = (
                self.__project.package_manager.find_struct_def(profile_url)
            )
            if not struct_def:
                raise KeyError(
                    f"No such structure definition '{struct_def}' exists in cache"
                )
            date_param = self.resource_type_to_date_param(struct_def.type)

            struct_def_module = extract_module_string()
            profile_detail = ProfileDetail(
                url=profile_url,
                display=TranslationDisplayElement(
                    original=(
                        struct_def.title
                        if struct_def.title is not None
                        else struct_def.name
                    ),
                    translations=[
                        Translation(
                            language="de-DE",
                            value=_get_value_for_lang_code(
                                struct_def.title__ext, "de-DE"
                            ),
                        ),
                        Translation(
                            language="en-US",
                            value=_get_value_for_lang_code(
                                struct_def.title__ext, "en-US"
                            ),
                        ),
                    ],
                ),
                module=TranslationDisplayElement(
                    original=struct_def_module if struct_def_module else struct_def.url,
                    translations=[
                        Translation(
                            language="de-DE",
                            value=self.module_translation["de-DE"].get(
                                struct_def_module, struct_def_module
                            ),
                        ),
                        Translation(
                            language="en-US",
                            value=self.module_translation["en-US"].get(
                                struct_def_module, struct_def_module
                            ),
                        ),
                    ],
                ),
                filters=(
                    [
                        Filter(
                            type="date",
                            name=date_param,
                            ui_type="timeRestriction",
                        )
                    ]
                    if date_param
                    else []
                ),
            )

            profile_type = struct_def.type
            code_search_param = (
                result := self.mapping_type_code.get(profile_type, None)
            ) and result.get("search_param", None)
            fhir_path = (
                result := self.mapping_type_code.get(profile_type, None)
            ) and result.get("fhir_path", None)
            value_set_urls = None

            if fhir_path is not None:
                value_set_urls = self.__get_value_sets_for_code_filter(
                    struct_def, fhir_path
                )

            if value_set_urls:
                profile_detail.filters.append(
                    Filter(
                        type="token",
                        name=code_search_param,
                        ui_type="code",
                        valueSetUrls=value_set_urls,
                    )
                )

            for elem_def in struct_def.root.children:
                if not self.is_field_included(elem_def, struct_def):
                    continue
                field_detail = self.generate_detail_for_elem_def(elem_def)
                self.__insert_field_into_profile_detail(profile_detail, field_detail)

            return profile_detail
        except Exception as exc:
            raise ProfileDetailGenerationException(
                f"Failed to generate profile details for profile '{profile_url}#"
            ) from exc

    def __generate_profile_details_for_subtree(
        self, root: ProfileTreeNode
    ) -> list[ProfileDetail]:
        details = [self.generate_detail_for_profile_tree_node(root)]
        for child in root.children:
            details.extend(self.__generate_profile_details_for_subtree(child))
        return details

    def generate_profile_details_for_profile_tree(
        self,
        profile_tree: list[ProfileTreeNode],
    ) -> list[ProfileDetail]:
        """
        Generate profile details for all profiles within the given scope
        :return: List of profile details for the given scope
        """
        profile_details = []
        for sub_tree in profile_tree:
            profile_details.extend(
                self.__generate_profile_details_for_subtree(sub_tree)
            )
        return profile_details
