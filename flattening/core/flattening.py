import json
from typing import Dict, List, Optional

from fhir.resources.R4B.elementdefinition import ElementDefinition
from fhir.resources.R4B.structuredefinition import StructureDefinition
from pydantic import BaseModel, Field

from availability.constants.fhir import MII_CDS_PACKAGE_PATTERN
from common.model.structure_definition import (
    StructureDefinitionSnapshot,
)
from common.util.fhir.package.manager import FhirPackageManager
from common.util.log.functions import get_logger
from common.util.structure_definition.functions import (
    get_parent_element_id,
    get_available_slices,
)

_logger = get_logger(__file__)


class FlatteningLookupElement(BaseModel):
    parent: str
    viewDefinition: Optional[Dict] = None
    children: Optional[List[str]] = None


class FlatteningLookup(BaseModel):
    url: str
    elements: Dict[str, FlatteningLookupElement] = Field(default={})


class ProfileFlattener:
    def __init__(self, profile: StructureDefinitionSnapshot):
        self.elements = [el.id for el in profile.snapshot.element]


def id_to_column_name(element) -> str:
    id: str = element.id
    # ':' and '.' are not allowed by pathling in column names, using '#' and '_' instead
    id = id.replace(":", "#")
    id = id.replace(".", "_")
    return id


def flatten_Coding(
    element: ElementDefinition,
    profile: StructureDefinitionSnapshot,
    elements_to_flatten: List[str],
) -> FlatteningLookupElement | None:
    code_system_url: str
    # value_set_url: str

    fle = FlatteningLookupElement(parent=get_parent_element_id(element))

    # TODO: use elements_to_flatten to delete all children of codings from queue

    # check pattern
    code_system_el = profile.get_element_by_id(f"{element.id}.system")
    if element.patternCoding or (code_system_el and code_system_el.patternUri):

        code_system_url = (
            code_system_el.patternUri
            if code_system_el.patternUri
            else element.patternCoding.system
        )
        fle.viewDefinition = {
            "forEachOrNull": f"{element.path}.where(system = '{code_system_url}')",
            "column": [{"name": id_to_column_name(element), "path": "code"}],
        }

    # check binding
    # if "binding" in element.__dict__.keys():
    #     value_set_url = element.binding.valueSet

    # check fixed

    # or if parent coding, check if it has coding children (slices). If no => create 2 columns
    if fle.viewDefinition is None or element.sliceName is None:
        _logger.warning("found coding without a slice name")

        # get all slices of type Codings
        list_of_children_codings = [
            slice
            for slice in get_available_slices(element.id, profile)
            if (slice_el := profile.get_element_by_id(f"{element.id}:{slice}"))
               and len(slice_el.type) > 0
               and "Coding" in slice_el.type[0].code
        ]
        if len(list_of_children_codings) > 0:
            _logger.warning("found coding without a slice name => skipping")
            # TODO: maybe do children mode? if needed
            return None

        _logger.error(f"creating two columns for {element.id}. Make sure this is right")
        fle.viewDefinition = {
            "forEachOrNull": f"{element.path}",
            "column": [
                {"name": f"{id_to_column_name(element)}_system", "path": "system"},
                {"name": f"{id_to_column_name(element)}_code", "path": "code"},
            ],
        }

    return fle


def flatten_BackboneElement(
    element: ElementDefinition, profile: StructureDefinitionSnapshot
) -> FlatteningLookupElement | None:

    fle = FlatteningLookupElement(parent=get_parent_element_id(element))
    # determine children, base.path
    fle.children = [
        el.id
        for el in profile.snapshot.element
        if get_parent_element_id(el) == element.id
    ]
    fle.viewDefinition = {"forEach": element.id.split(".")[-1], "select": []}

    print([el for el in fle.children])
    return fle


def flatten_element(
    element: ElementDefinition,
    profile: StructureDefinitionSnapshot,
    elements_to_flatten: List[str],
) -> FlatteningLookupElement | None:

    if element.type is None or len(element.type) < 1:
        _logger.warning(f"No type found for element {element.id}")
        return None

    types = [element_type.code for element_type in element.type]
    match types[0]:
        case "Coding":
            _logger.warning("Found coding ^^")
            return flatten_Coding(element, profile, elements_to_flatten)
        case "BackboneElement":
            _logger.warning("Found backbone ^^")
            return flatten_BackboneElement(element, profile)

    return None


def generate_flattening_lookup_for_profile(
    profile: StructureDefinitionSnapshot,
) -> FlatteningLookup:
    _logger.info(f"Generating flattening lookup for {profile.name}")

    fl = FlatteningLookup(url=profile.url)

    elements_to_flatten = [el.id for el in profile.snapshot.element]

    for element_id in elements_to_flatten:
        element: ElementDefinition = profile.get_element_by_id(element_id)
        _logger.info(f"{element.id}")

        if (fle := flatten_element(element, profile, elements_to_flatten)) is not None:
            fl.elements[id_to_column_name(element)] = fle

    return fl


def generate_flattening_lookup(manager: FhirPackageManager):

    # read all profiles from DSE
    _logger.info("Generating flattening lookup files")
    content_pattern = {
        "resourceType": "StructureDefinition",
        "kind": "resource",
    }
    for profile in manager.iterate_cache(
        MII_CDS_PACKAGE_PATTERN, content_pattern, skip_on_fail=True
    ):
        if profile.type in ["SearchParameter"]:
            continue
        if not isinstance(profile, StructureDefinition) and not profile.snapshot:
            _logger.debug(
                f"Profile '{profile.url}' is not in snapshot form => Skipping"
            )
            continue

        if profile.id != "mii-pr-diagnose-condition":
            continue

        profile: StructureDefinitionSnapshot
        lookup = generate_flattening_lookup_for_profile(profile)
        print(lookup.model_dump_json(exclude_none=True, indent=4))
