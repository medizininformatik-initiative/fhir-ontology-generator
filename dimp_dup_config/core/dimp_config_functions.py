from typing import List

from fhir.resources.R4B.elementdefinition import ElementDefinition
from fhir.resources.R4B.structuredefinition import StructureDefinition
from pydantic import BaseModel, Field
from ruamel.yaml import CommentedSeq

from common.model.fhir.structure_definition import StructureDefinitionSnapshot
from common.util.fhir.enums import FhirComplexDataType, FhirPrimitiveDataType
from common.util.fhir.package.manager import FhirPackageManager
from common.util.http.exceptions import ClientError
from common.util.http.terminology.client import FhirTerminologyClient
from common.util.log.functions import get_logger
from common.util.structure_definition.functions import (
    get_available_slice_names,
    get_element_type,
)
from dimp_dup_config.constants.fhir import DIMP_CONFIG_PACKAGE_PATTERN
from flattening.core.flattening import get_direct_children_ids

_logger = get_logger(__name__)
_SERVER_VALUE_SET_SYSTEMS_CACHE: dict[str, List[str] | None] = {}


class ElementDimpConfig(BaseModel):
    path: str = Field(default=None)
    method: str = Field(default="keep")


class ProfileDimpConfig(BaseModel):
    url: str = Field(default=None)
    elements: List[ElementDimpConfig] = Field(default_factory=list)


class DimpConfig(BaseModel):
    profiles_configs: List[ProfileDimpConfig] = Field(default_factory=list)

    def to_dimp_format(self) -> CommentedSeq:
        """
        Converts profile-scoped DIMP config models into the flat list format expected by the pseudonymizer.
        :return: YAML-compatible sequence of DIMP rules with profile comments
        """
        dimp_config_list = CommentedSeq()
        dimp_config_list.yaml_set_comment_before_after_key(
            0, before="FHIR DIMP Configuration - Automatically Generated"
        )
        index = 0

        for profile_dimp in self.profiles_configs:
            dimp_config_list.extend([el.model_dump() for el in profile_dimp.elements])
            if len(profile_dimp.elements) > 0:
                comment_text = f"\nProfile: {profile_dimp.url}"
                dimp_config_list.yaml_set_comment_before_after_key(
                    index, before=comment_text
                )
            index += len(profile_dimp.elements)

        return dimp_config_list


def is_must_support(element: ElementDefinition) -> bool:
    """
    Checks if the given element is explicitly marked as mustSupport.
    :param element: ElementDefinition to inspect
    :return: True if mustSupport is set, otherwise False
    """
    if element is None or element.mustSupport is None:
        return False
    return element.mustSupport


def to_dimp_path(element_id: str) -> str:
    """
    Converts an ElementDefinition id into a DIMP FHIRPath-compatible path.
    :param element_id: ElementDefinition id, possibly polymorphic
    :return: normalized DIMP path
    """
    return element_id.replace("[x]", "")


def get_extension_profile_url(element: ElementDefinition) -> str | None:
    """
    Extracts the canonical extension profile URL from an Extension element.
    :param element: Extension ElementDefinition
    :return: extension profile URL or None if none is defined
    """
    if not element.type or not element.type[0].profile:
        return None
    return element.type[0].profile[0]


class DimpConfigGenerator:
    """
    Generates a whitelist DIMP config from supported FHIR profile elements.
    """

    package_manager: FhirPackageManager
    client: FhirTerminologyClient

    def __init__(self, project):
        """
        :param project: Project for which the DIMP config should be generated
        """
        self.package_manager = project.package_manager
        self.client = FhirTerminologyClient.from_project(project)

    def get_system_where_clause_from_value_set(
        self, element: ElementDefinition
    ) -> str | None:
        """
        Builds a system-level FHIRPath where clause from the element binding ValueSet.
        :param element: ElementDefinition containing a ValueSet binding
        :return: where clause selecting allowed systems or None if no systems can be resolved
        """
        if not element.binding or not element.binding.valueSet:
            return None

        if systems := self.get_systems_from_server_value_set(element.binding.valueSet):
            return " or ".join(f"system = '{system}'" for system in systems)

        if systems := self.get_systems_from_package_value_set(element.binding.valueSet):
            return " or ".join(f"system = '{system}'" for system in systems)

        return None

    def get_systems_from_server_value_set(self, value_set_url: str) -> List[str]:
        """
        Expands a ValueSet on the terminology server and extracts distinct coding systems.
        :param value_set_url: canonical URL of the ValueSet to expand
        :return: sorted list of distinct systems from the server expansion
        """
        if value_set_url in _SERVER_VALUE_SET_SYSTEMS_CACHE:
            return _SERVER_VALUE_SET_SYSTEMS_CACHE[value_set_url] or []

        try:
            value_set = self.client.expand_value_set(url=value_set_url)
        except ClientError as exc:
            _logger.warning(
                f"Could not expand valueSet from terminology server: {value_set_url}\n{exc}"
            )
            _SERVER_VALUE_SET_SYSTEMS_CACHE[value_set_url] = None
            return []

        systems = sorted(
            {
                contains.get("system")
                for contains in value_set.get("expansion", {}).get("contains", [])
                if contains.get("system")
            }
        )
        _SERVER_VALUE_SET_SYSTEMS_CACHE[value_set_url] = systems
        return systems

    def get_systems_from_package_value_set(self, value_set_url: str) -> List[str]:
        """
        Reads a local packaged ValueSet and extracts distinct coding systems.
        :param value_set_url: canonical URL of the ValueSet to read from the package cache
        :return: sorted list of distinct systems from compose or expansion
        """
        try:
            value_set = self.package_manager.find(
                {"resourceType": "ValueSet", "url": value_set_url.split("|", 1)[0]}
            )
        except Exception as exc:
            _logger.warning(
                f"Could not read valueSet from package cache: {value_set_url}\n{exc}"
            )
            return []

        if not value_set:
            return []

        systems = set()
        if value_set.compose and value_set.compose.include:
            systems.update(
                include.system for include in value_set.compose.include if include.system
            )
        if value_set.expansion and value_set.expansion.contains:
            systems.update(
                contains.system
                for contains in value_set.expansion.contains
                if contains.system
            )

        return sorted(systems)

    def get_system_where_clause_from_codeable_concept_pattern(
        self, element: ElementDefinition
    ) -> str | None:
        """
        Builds a system-level where clause from a CodeableConcept pattern or fixed value.
        :param element: CodeableConcept ElementDefinition
        :return: where clause selecting pattern/fixed systems or None if none are defined
        """
        codeable_concept = element.patternCodeableConcept or getattr(
            element, "fixedCodeableConcept", None
        )
        if not codeable_concept or not codeable_concept.coding:
            return None

        systems = sorted(
            {coding.system for coding in codeable_concept.coding if coding.system}
        )
        if not systems:
            return None

        return " or ".join(f"system = '{system}'" for system in systems)

    def get_codeable_concept_coding_where_clause(
        self, element: ElementDefinition, profile: StructureDefinitionSnapshot
    ) -> str | None:
        """
        Resolves the most specific coding-level where clause for a CodeableConcept element.
        :param element: CodeableConcept ElementDefinition
        :param profile: profile containing the element
        :return: where clause selecting allowed coding systems or None
        """
        if where_clause := self.get_system_where_clause_from_codeable_concept_pattern(
            element
        ):
            return where_clause

        if coding_element := profile.get_element_by_id(f"{element.id}.coding"):
            return self.get_coding_system_where_clause(coding_element, profile)

        return self.get_system_where_clause_from_value_set(element)

    def get_coding_system_where_clause(
        self, element: ElementDefinition, profile: StructureDefinitionSnapshot
    ) -> str | None:
        """
        Resolves the system-level where clause for a Coding element.
        :param element: Coding ElementDefinition
        :param profile: profile containing the element
        :return: where clause selecting allowed systems or None
        """
        code_system_el = profile.get_element_by_id(f"{element.id}.system")
        if code_system_el and code_system_el.patternUri:
            return f"system = '{code_system_el.patternUri}'"
        if code_system_el and code_system_el.fixedUri:
            return f"system = '{code_system_el.fixedUri}'"
        if element.patternCoding and element.patternCoding.system:
            return f"system = '{element.patternCoding.system}'"
        if fixed_coding := getattr(element, "fixedCoding", None):
            if fixed_coding.system:
                return f"system = '{fixed_coding.system}'"

        return self.get_system_where_clause_from_value_set(element)

    def get_slice_keep_path(
        self, element: ElementDefinition, profile: StructureDefinitionSnapshot
    ) -> str | None:
        """
        Generates a DIMP keep path for a sliced element using its discriminator constraints.
        :param element: slice ElementDefinition
        :param profile: profile containing the slice
        :return: DIMP keep path for the slice or None if no selector can be built
        """
        element_type = get_element_type(element)
        slice_base_path = to_dimp_path(element.id.rsplit(":", 1)[0])

        if element_type == FhirComplexDataType.EXTENSION:
            if ext_profile_url := get_extension_profile_url(element):
                return f"{slice_base_path}.where(url = '{ext_profile_url}')"
            return None

        if element_type == FhirComplexDataType.CODING:
            if where_clause := self.get_coding_system_where_clause(element, profile):
                return f"{slice_base_path}.where({where_clause})"

        if where_clause := self.get_where_clause_for_slice(element, profile):
            return f"{slice_base_path}.where({where_clause})"

        return None

    def get_where_clause_for_slice(
        self, element: ElementDefinition, profile: StructureDefinitionSnapshot
    ) -> str | None:
        """
        Extracts a generic FHIRPath where clause for a sliced element.
        :param element: slice ElementDefinition
        :param profile: profile containing the slice
        :return: where clause for selecting the slice or None
        """
        code_system_el = profile.get_element_by_id(f"{element.id}.system")
        if code_system_el and code_system_el.patternUri:
            return f"system = '{code_system_el.patternUri}'"
        if code_system_el and code_system_el.fixedUri:
            return f"system = '{code_system_el.fixedUri}'"

        if element.patternCoding and element.patternCoding.system:
            return f"system = '{element.patternCoding.system}'"
        if fixed_coding := getattr(element, "fixedCoding", None):
            if fixed_coding.system:
                return f"system = '{fixed_coding.system}'"

        if element.patternIdentifier:
            if element.patternIdentifier.system:
                return f"system = '{element.patternIdentifier.system}'"
            if (
                element.patternIdentifier.type
                and element.patternIdentifier.type.coding
                and element.patternIdentifier.type.coding[0].system
            ):
                return (
                    "type.coding.system = "
                    f"'{element.patternIdentifier.type.coding[0].system}'"
                )

        return self.get_system_where_clause_from_value_set(element)

    def generate_dimp_config_for_slice_base(
        self, element: ElementDefinition, profile: StructureDefinitionSnapshot
    ) -> List[ElementDimpConfig]:
        """
        Generates keep rules for all mustSupport slices of a sliced base element.
        :param element: sliced base ElementDefinition
        :param profile: profile containing the slicing definition
        :return: list of DIMP config elements for mustSupport slices
        """
        dimp_config_elements: List[ElementDimpConfig] = []

        for slice_name in get_available_slice_names(element.id, profile):
            slice_el = profile.get_element_by_id(f"{element.id}:{slice_name}")
            if not slice_el or not is_must_support(slice_el):
                continue
            if path := self.get_slice_keep_path(slice_el, profile):
                dimp_config_elements.append(ElementDimpConfig(path=path))

        return dimp_config_elements

    def generate_dimp_config_for_element(
        self, element: ElementDefinition | None, profile: StructureDefinitionSnapshot
    ) -> List[ElementDimpConfig]:
        """
        Generates DIMP keep rules for a single ElementDefinition.
        :param element: ElementDefinition to generate for
        :param profile: profile containing the element
        :return: list of generated DIMP config elements
        """
        if element is None:
            return []

        _logger.debug(f"Generating dimp config for element: {element.id}")

        dimp_config_elements: List[ElementDimpConfig] = []

        if not element.type:
            for child in get_direct_children_ids(element.id, profile):
                dimp_config_elements.extend(
                    self.generate_dimp_config_for_element(
                        profile.get_element_by_id(child), profile
                    )
                )
            return dimp_config_elements

        if len(element.type) > 1:
            if not is_must_support(element):
                for child in get_direct_children_ids(element.id, profile):
                    dimp_config_elements.extend(
                        self.generate_dimp_config_for_element(
                            profile.get_element_by_id(child), profile
                        )
                    )
                return dimp_config_elements

            dimp_config_elements.append(ElementDimpConfig(path=to_dimp_path(element.id)))
            return dimp_config_elements

        element_type = get_element_type(element)

        if element.slicing is not None:
            dimp_config_elements.extend(
                self.generate_dimp_config_for_slice_base(element, profile)
            )
            if len(dimp_config_elements) > 0:
                return dimp_config_elements

        if not is_must_support(element):
            for child in get_direct_children_ids(element.id, profile):
                dimp_config_elements.extend(
                    self.generate_dimp_config_for_element(
                        profile.get_element_by_id(child), profile
                    )
                )
            return dimp_config_elements

        if element_type == FhirComplexDataType.CODEABLE_CONCEPT:
            for child_codings in get_direct_children_ids(element.id, profile):
                dimp_config_elements.extend(
                    self.generate_dimp_config_for_element(
                        profile.get_element_by_id(child_codings), profile
                    )
                )

            if len(dimp_config_elements) > 0:
                return dimp_config_elements

            if where_clause := self.get_codeable_concept_coding_where_clause(
                element, profile
            ):
                dimp_config_elements.append(
                    ElementDimpConfig(
                        path=f"{to_dimp_path(element.id)}.coding.where({where_clause})"
                    )
                )

            return dimp_config_elements

        if element_type == FhirComplexDataType.CODING:
            if element.slicing is not None:
                return dimp_config_elements

            if where_clause_binding := self.get_coding_system_where_clause(
                element, profile
            ):
                dimp_config_elements.append(
                    ElementDimpConfig(
                        path=f"{to_dimp_path(element.id)}.where({where_clause_binding})"
                    )
                )
                return dimp_config_elements

        if element_type == FhirComplexDataType.EXTENSION:
            if (
                not element.slicing
                and element.sliceName
                and (ext_profile_url := get_extension_profile_url(element))
            ):
                dimp_config_elements.append(
                    ElementDimpConfig(
                        path=f"{to_dimp_path(element.id.rsplit(':', 1)[0])}.where(url = '{ext_profile_url}')"
                    )
                )

            return dimp_config_elements

        if element_type in FhirComplexDataType:
            dimp_config_elements.append(ElementDimpConfig(path=to_dimp_path(element.id)))
            return dimp_config_elements

        if element_type in FhirPrimitiveDataType:
            dimp_config_elements.append(ElementDimpConfig(path=to_dimp_path(element.id)))
            return dimp_config_elements

        return dimp_config_elements

    def generate_dimp_config_for_profile(
        self, profile: StructureDefinitionSnapshot
    ) -> ProfileDimpConfig:
        """
        Generates and post-processes DIMP keep rules for one profile.
        :param profile: StructureDefinition snapshot to generate for
        :return: profile-scoped DIMP config
        """
        dimp_config_elements: List[ElementDimpConfig] = []

        for lvl1_element in get_direct_children_ids(profile.type, profile):
            dimp_config_elements.extend(
                self.generate_dimp_config_for_element(
                    profile.get_element_by_id(lvl1_element), profile
                )
            )

        return post_process_profile_dimp_config(
            ProfileDimpConfig(url=profile.url, elements=dimp_config_elements)
        )

    def generate_dimp_config(self) -> DimpConfig:
        """
        Generates DIMP keep rules for all configured resource profiles.
        :return: complete DIMP config including the final Resource redact rule
        """
        _logger.info("Generating dimp config file")
        content_pattern = {"resourceType": "StructureDefinition", "kind": "resource"}
        dimp_config: DimpConfig = DimpConfig()

        for profile in self.package_manager.iterate_cache(
            DIMP_CONFIG_PACKAGE_PATTERN, content_pattern, skip_on_fail=False
        ):
            if profile.type in ["SearchParameter"]:
                continue
            if not isinstance(profile, StructureDefinition) and not profile.snapshot:
                _logger.warning(
                    f"Profile '{profile.url}' is not in snapshot form => Skipping"
                )
                continue

            _logger.info(
                f"Generating dimp config for {profile.name}: {profile.id}  |  {profile.url}"
            )

            profile: StructureDefinitionSnapshot
            dimp_config.profiles_configs.append(
                self.generate_dimp_config_for_profile(profile)
            )
        dimp_config.profiles_configs = sorted(
            dimp_config.profiles_configs,
            key=lambda profile_config: profile_config.url or "",
        )

        dimp_config.profiles_configs.append(
            ProfileDimpConfig(
                url="",
                elements=[ElementDimpConfig(path="Resource", method="redact")],
            )
        )

        return dimp_config


def is_more_specific_keep(parent: ElementDimpConfig, child: ElementDimpConfig) -> bool:
    """
    Checks whether one keep rule is made redundant by a more specific keep rule.
    :param parent: potential parent keep rule
    :param child: potential more specific child keep rule
    :return: True if the child keep is more specific than the parent keep
    """
    if parent.method != "keep" or child.method != "keep":
        return False
    return child.path.startswith(f"{parent.path}.") or child.path.startswith(
        f"{parent.path}.where("
    )


def post_process_profile_dimp_config(
    profile_config: ProfileDimpConfig,
) -> ProfileDimpConfig:
    """
    Deduplicates, sorts and removes redundant parent keep rules from a profile config.
    :param profile_config: generated profile DIMP config
    :return: post-processed profile DIMP config
    """
    deduplicated_elements: List[ElementDimpConfig] = []
    seen = set()
    for element in profile_config.elements:
        key = (element.path, element.method)
        if key in seen:
            continue
        seen.add(key)
        deduplicated_elements.append(element)

    filtered_elements = [
        element
        for element in deduplicated_elements
        if not any(
            other is not element and is_more_specific_keep(element, other)
            for other in deduplicated_elements
        )
    ]

    return ProfileDimpConfig(
        url=profile_config.url,
        elements=sorted(
            filtered_elements, key=lambda element: (element.path, element.method)
        ),
    )
