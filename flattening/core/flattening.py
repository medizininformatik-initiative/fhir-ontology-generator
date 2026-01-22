import json
from typing import Dict, List, Optional, Set

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
    get_slice_name,
    get_parent_slice_id,
    get_parent_element,
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


def get_child_coding_slices(
    element: ElementDefinition, profile: StructureDefinitionSnapshot
) -> List[ElementDefinition]:
    found_codings_slices: Set[ElementDefinition] = set()

    for el in profile.snapshot.element:
        if ":" in el.id and element.id in get_parent_slice_id(el.id):
            found_codings_slices.add(el)

    return list(found_codings_slices)


def flatten_Coding(
    element: ElementDefinition,
    profile: StructureDefinitionSnapshot,
    elements_to_flatten: List[str],
) -> FlatteningLookupElement | None:
    """
    This function creates the lookup for coding elements. There are two types of codings:
        1. **codings without a sliceName** : These elements will be ignored
        2. **codings with a sliceName** : These are children of the codings of type 1.
            When these are processed the ``path`` of the ``ForEachOrNull`` should include the
            parent ``coding`` (See example below). This is done to ensure that the resulting
            viewDefinition has the right interation scope.

            **Important**: skipping the parent coding (type 1) means no parent viewDefinition to insert into
             => Use the ``codeableConcept`` these codings are wrapped in:
                Example: parent for (Condition.code.coding:sct) -> "Condition.code" (codeableConcept)
            **Note**: Keep in mind that these, when selected by CRTDL, need to be inserted into the element the parent attribute
            points to. This will cause these lookups to not work when inserted into to viewDefinition plainly.
    Example lookup for coding-children (type 2)::

        "Condition.code.coding:sct": {
          "parent": "Condition.code",
          "viewDefinition": {
            "forEachOrNull": "coding.where(system = 'http://snomed.info/sct')",
            -------------------^^^
            "select": [
              {
                "column": [
                  {
                    "name": "sct",
                    "path": "code"
                  }
                ]
              }
            ]
          },
          "children": []
        },

    :param element:
    :param profile:
    :param elements_to_flatten:
    :return:
    """
    code_system_url: str
    # value_set_url: str

    # parent codings are handled implicitly by the flatten_CodeableConcept
    if element.sliceName is None:
        return None

    # parent CodeableConcept is used as parent for slices. Its two levels above
    # example: Condition.code.coding:sct -> Condition.code
    parent_codeableConcept: ElementDefinition = get_parent_element(profile,get_parent_element(profile,element))
    if len(parent_codeableConcept.type) == 0 or "CodeableConcept" not in parent_codeableConcept.type[0].code:
        _logger.warning("Undefined behaviour: Slice.parent reference does not point to a codeableConcept")
        return None
    fle = FlatteningLookupElement(parent=parent_codeableConcept.id)

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

    # TODO: check binding
    # if "binding" in element.__dict__.keys():
    #     value_set_url = element.binding.valueSet

    # TODO: check fixed

    return fle

def flatten_CodeableConcept(element: ElementDefinition, profile: StructureDefinitionSnapshot)->FlatteningLookupElement|None:
    """
    This function flattens a element of type CodeableConcept. If the child coding has any slices defined their ids saved as children.
        The children slices will be processed in the flatten_Coding function.
        Else this function creates two columns: el_system, el_code. When evaluating the viewDefinition all code which are found, will
        be listed in rows.
    :param element: codeableConcept to be flattened
    :param profile: snapshot of codeableConcept
    :return:
    """

    # check if the defined coding has any defined slices -> else col_sys + col_code
    child_coding_element = profile.get_element_by_id(f"{element.id}.coding")

    # I'm pretty sure that this is the 'parent' of the slices. Future tests will tell
    _logger.info("found CodeableConcept")

    fle = FlatteningLookupElement(parent=get_parent_element_id(element))
    fle.viewDefinition = {"forEach": element.id.split(".")[-1], "select": []}

    # get all slices of type Codings
    list_of_children_slices = [
        slice.id
        for slice in get_available_slices(child_coding_element.id, profile)
        if len(slice.type) > 0 and "Coding" in slice.type[0].code
    ]
    if len(list_of_children_slices) > 0:
        _logger.warning("found coding without a slice name => skipping")
        fle.children = list_of_children_slices
        return fle

    _logger.warning(f"creating two columns for {element.id} through coding: {child_coding_element.id}. Make sure this is right")
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
            fl.elements[element.id] = fle

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
