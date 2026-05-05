from typing import List

from fhir.resources.R4B.elementdefinition import ElementDefinition
from fhir.resources.R4B.structuredefinition import StructureDefinition
from pydantic import BaseModel
from pydantic import Field

from common.model.fhir.structure_definition import StructureDefinitionSnapshot
from common.util.fhir.enums import FhirComplexDataType
from common.util.fhir.package.manager import FhirPackageManager
from common.util.http.terminology.client import FhirTerminologyClient
from common.util.log.functions import get_logger
from common.util.structure_definition.functions import (
    get_parent_element,
    get_element_type,
    get_available_slices,
    get_available_slice_names,
)
from dimp_dup_config.constants.fhir import DIMP_CONFIG_PACKAGE_PATTERN
from flattening.core.flattening import (
    extract_where_clause_for_slice,
    get_direct_children_ids,
)
 
_logger = get_logger(__name__)


class ElementDimpConfig(BaseModel):
    path: str = Field(default=None)
    method: str = Field(default="keep")


class ProfileDimpConfig(BaseModel):
    url: str = Field(default=None)
    elements: List[ElementDimpConfig] = Field(default_factory=list)


class DimpConfig(BaseModel):
    profiles_configs: List[ProfileDimpConfig] = Field(default_factory=list)

    def to_dimp_format(self):
        dimp_config_dict = []
        for profile_dimp in self.profiles_configs:
            dimp_config_dict.extend([el.model_dump() for el in profile_dimp.elements])
        return dimp_config_dict

def is_must_support(element: ElementDefinition)-> bool:
    if element is None or element.mustSupport is None:
        return False
    return element.mustSupport


def generate_dimp_config_for_element(
    element: ElementDefinition | None,
    profile: StructureDefinitionSnapshot,
    client: FhirTerminologyClient,
) -> List[ElementDimpConfig]:

    if element is None or not is_must_support(element):
        return []

    _logger.info(f"Genereting dimp config for element: {element.id}")

    element_type = get_element_type(element)
    dimp_config_elements: List[ElementDimpConfig] = []

    # go deeper only if mustSupp + not complex type
    if element_type == FhirComplexDataType.CODEABLE_CONCEPT:
        for child_codings in get_direct_children_ids(element.id, profile):
            dimp_config_elements.extend(
                generate_dimp_config_for_element(
                    profile.get_element_by_id(child_codings), profile, client
                )
            )
        return dimp_config_elements

    if element_type == FhirComplexDataType.CODING:
        # check available slices and filter for mustSupp
        if element.slicing is not None:
            available_slices_with_must_supp = [
                f"{element.id}.where({extract_where_clause_for_slice(profile.get_element_by_id(f'{element.id}:{sliceName}'), profile)})"
                for sliceName in get_available_slice_names(element.id, profile)
                    if (slice_el := profile.get_element_by_id(f"{element.id}:{sliceName}"))
                    and is_must_support(slice_el)
            ]
            for slice_must_support in available_slices_with_must_supp:
                dimp_config_elements.append(ElementDimpConfig(path=f"{slice_must_support} DEBUG: from coding slice"))

            return dimp_config_elements

    if element_type in FhirComplexDataType:
        dimp_config_elements.append(ElementDimpConfig(path=f"{element.id} DEBUG: from complex type"))

    return dimp_config_elements


def generate_dimp_config_for_profile(
    profile: StructureDefinitionSnapshot, client: FhirTerminologyClient
) -> ProfileDimpConfig:
    dimp_config_elements: List[ElementDimpConfig] = []

    for lvl1_element in get_direct_children_ids(profile.type, profile):
        dimp_config_elements.extend(
            generate_dimp_config_for_element(
                profile.get_element_by_id(lvl1_element), profile, client
            )
        )

    return ProfileDimpConfig(url=profile.url, elements=dimp_config_elements)


def generate_dimp_config(
    manager: FhirPackageManager, client: FhirTerminologyClient
) -> DimpConfig:

    # read all profiles from DSE
    _logger.info("Generating dimp config file")
    content_pattern = {"resourceType": "StructureDefinition", "kind": "resource"}
    dimp_config: DimpConfig = DimpConfig()

    for profile in manager.iterate_cache(
        DIMP_CONFIG_PACKAGE_PATTERN, content_pattern, skip_on_fail=False
    ):
        if profile.type in ["SearchParameter"]:
            continue
        if not isinstance(profile, StructureDefinition) and not profile.snapshot:
            _logger.warning(
                f"Profile '{profile.url}' is not in snapshot form => Skipping"
            )
            continue

        if not profile.id == "mii-pr-diagnose-condition":
            continue

        _logger.info(
            f"Generating dimp config for {profile.name}: {profile.id}  |  {profile.url}"
        )

        profile: StructureDefinitionSnapshot
        dimp_config.profiles_configs.append(
            generate_dimp_config_for_profile(profile, client)
        )

    return dimp_config
