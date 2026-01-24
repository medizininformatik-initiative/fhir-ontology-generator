import json
from typing import Dict, List, Optional, Set, Literal

from fhir.resources.R4B.elementdefinition import ElementDefinition
from fhir.resources.R4B.structuredefinition import StructureDefinition
from pydantic import BaseModel, Field

from availability.constants.fhir import MII_CDS_PACKAGE_PATTERN
from common.model.structure_definition import (
    StructureDefinitionSnapshot,
)
from common.util.fhir.package.manager import FhirPackageManager
from common.util.http.terminology.client import FhirTerminologyClient
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
    resource_type: str
    elements: Dict[str, FlatteningLookupElement] = Field(default={})


def id_to_column_name(element) -> str:
    el_id: str = element.id
    # ':' and '.' are not allowed by pathling in column names, using '#' and '_' instead
    el_id = el_id.replace(":", "")
    el_id = el_id.replace(".", "_")
    el_id = el_id.replace("-", "")
    el_id = el_id.replace("[x]", "_X_")
    return el_id


def get_element_type(
    element,
) -> (
    Literal[
        "CodeableConcept",
        "Coding",
        "BackboneElement",
        "dateTime",
        "Period",
        "Reference",
        "Polymorphic",
    ]
    | None
):

    if element.type is not None and "[x]" in element.id and len(element.type) > 1:
        return "Polymorphic"

    if element.type is not None and len(element.type) == 1:
        type = element.type[0].code
        if type == "Meta":
            return "BackboneElement"
        return type

    _logger.warning(f"No type found for element {element.id} => Skipping")
    return None


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
    client: FhirTerminologyClient,
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

    # Handling of parent codings | not a slice
    if element.sliceName is None:
        parent = get_parent_element(profile, element)

        # Case 1: Coding inside CodeableConcept.coding → ignore
        if parent and get_element_type(parent) == "CodeableConcept":
            _logger.warning("Is CodeableConcept.coding parent => Ignoring")
            return None

        # Case 2: Standalone Coding (e.g. meta.security) → flatten normally
        # if element.binding is None:
        _logger.warning("Standalone Coding => creating columns")
        fle = FlatteningLookupElement(parent=get_parent_element_id(element))
        fle.viewDefinition = {
            "forEachOrNull": element.id.split(".")[-1],
            "column": [
                {"name": f"{id_to_column_name(element)}_system", "path": "system"},
                {"name": f"{id_to_column_name(element)}_code", "path": "code"},
            ],
        }
        return fle
        # else: TODO: diskus if this is even necessary, or smart (extract codesystems from valueSet)
        #     systems = set()
        #     valueSet = client.expand_value_set(element.binding.valueSet)
        #     if valueSet:
        #         for entry in valueSet.get("expansion").get("parameter"):
        #             if entry.get("name") == "used-codesystem":
        #                 uri = entry.get("valueUri")
        #                 if uri:
        #                     system = uri.split("|", 1)[0]
        #                     systems.add(system)
        #     _logger.info(f"found following codesystems for binding of {element.id}: \n "
        #                  f"{systems.__str__()}")

        # for generate all codesystem posibilities

    # parent CodeableConcept is used as parent for slices. Its two levels above
    # example: Condition.code.coding:sct -> Condition.code
    parent_codeableConcept: ElementDefinition = get_parent_element(
        profile, get_parent_element(profile, element)
    )
    if get_element_type(parent_codeableConcept) != "CodeableConcept":
        _logger.warning(
            "Undefined behaviour: Slice.parent reference does not point to a codeableConcept"
        )
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
            "forEachOrNull": f"{element.path.split(".")[-1]}.where(system = '{code_system_url}')",
            "column": [{"name": id_to_column_name(element), "path": "code"}],
        }

    # TODO: check binding
    # if "binding" in element.__dict__.keys():
    #     value_set_url = element.binding.valueSet

    # TODO: check fixed

    return fle


def flatten_CodeableConcept(
    element: ElementDefinition, profile: StructureDefinitionSnapshot
) -> FlatteningLookupElement | None:
    """
    This function flattens a element of type CodeableConcept. If the child coding has any slices defined their ids saved as children.
        The children slices will be processed in the flatten_Coding function.
        Else this function creates two columns: el_system, el_code. When evaluating the viewDefinition all code which are found, will
        be listed in rows.
    :param element: codeableConcept to be flattened
    :param profile: snapshot of codeableConcept
    :return:
    """

    # part of polymorphic element
    if element.sliceName is not None or "[x]" in element.path.split(".")[-1]:
        _logger.warning("Child of polymorphic element. Not yet implemented => Skipping")
        # TODO: implement later
        return None

    # I'm pretty sure that this is the 'parent' of the slices. Future tests will tell
    fle = FlatteningLookupElement(parent=get_parent_element_id(element))
    fle.viewDefinition = {"forEachOrNull": element.id.split(".")[-1], "select": []}

    # check if a conding is defined and the defined coding has any defined slices -> else col_sys + col_code
    child_coding_element = profile.get_element_by_id(f"{element.id}.coding")
    if child_coding_element is not None:
        list_of_children_slices = [
            slice.id
            for slice in get_available_slices(child_coding_element.id, profile)
            if len(slice.type) > 0 and "Coding" in slice.type[0].code
        ]
        if len(list_of_children_slices) > 0:
            _logger.warning(f"found slices: {list_of_children_slices.__str__()}")
            fle.children = list_of_children_slices
            return fle

    _logger.warning(
        f"creating two columns for {element.id} "
        f"through coding: {child_coding_element.id if child_coding_element else ''}. "
        f"Make sure this is right"
    )
    fle.viewDefinition = {
        # TODO: check this
        "forEachOrNull": f"{element.id.split('.')[-1]}.coding",
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
    fle.viewDefinition = {"forEachOrNull": element.id.split(".")[-1], "select": []}

    print([el for el in fle.children])
    return fle


def flatten_Reference(
    element: ElementDefinition, profile: StructureDefinitionSnapshot
) -> FlatteningLookupElement | None:

    fle = FlatteningLookupElement(parent=get_parent_element(profile, element).id)
    fle.viewDefinition = {
        "column": [
            {
                "name": f"{id_to_column_name(element)}",
                "path": f"{element.id.split('.')[-1]}.reference",
            }
        ]
    }

    return fle


def flatten_dateTime(
    element: ElementDefinition, profile: StructureDefinitionSnapshot
) -> FlatteningLookupElement | None:

    # is it part of polymorphic element
    if element.sliceName is not None and "[x]" in element.path.split(".")[-1]:
        # Condition.onset[x]:onsetDateTime -> grandparent: Condition
        parent_element = get_parent_element(profile, element)
        grand_parent_element = get_parent_element(profile, parent_element)
        fle = FlatteningLookupElement(parent=grand_parent_element.id)
        fle.viewDefinition = {
            "forEachOrNull": f"{element.sliceName.replace('DateTime','')}.ofType(dateTime)",
            "column": [
                {
                    "name": f"{id_to_column_name(element)}",
                    "path": f"$this",
                }
            ],
        }
        return fle

    fle = FlatteningLookupElement(parent=get_parent_element(profile, element).id)
    fle.viewDefinition = {
        "column": [
            {
                "name": f"{id_to_column_name(element)}",
                "path": f"{element.id.split('.')[-1]}",
            }
        ]
    }

    return fle


def flatten_Period(
    element: ElementDefinition, profile: StructureDefinitionSnapshot
) -> FlatteningLookupElement | None:

    # is it part of polymorphic element
    if element.sliceName is not None and "[x]" in element.path.split(".")[-1]:
        # Condition.onset[x]:onsetPeriod -> grandparent: Condition
        parent_element = get_parent_element(profile, element)
        grand_parent_element = get_parent_element(profile, parent_element)
        fle = FlatteningLookupElement(parent=grand_parent_element.id)
        fle.viewDefinition = {
            "forEachOrNull": f"{element.sliceName.replace('Period','')}.ofType(Period)"
        }
        fle.children = [
            el.id for el in profile.snapshot.element if element.id in el.id and get_parent_element(profile,el).id == element.id
        ]
        _logger.info(f"found children for Period: {fle.children.__str__()}")
        return fle

    # TODO: handle simple case
    # fle = FlatteningLookupElement(parent=get_parent_element(profile, element).id)
    # fle.viewDefinition = {"forEachOrNull": element.id.split(".")[-1], "select": []}
    #
    # fle.children = [
    #     el.id for el in profile.snapshot.element if element.id in el.id and get_parent_element(profile,el).id == element.id
    # ]

    return None


def flatten_polymorphic_element(
    element: ElementDefinition, profile: StructureDefinitionSnapshot
) -> FlatteningLookupElement | None:

    pass


def flatten_element(
    element: ElementDefinition,
    profile: StructureDefinitionSnapshot,
    client: FhirTerminologyClient,
) -> FlatteningLookupElement | None:

    match get_element_type(element):
        case "Coding":
            _logger.warning("Found coding ^^")
            return flatten_Coding(element, profile, client)
        case "CodeableConcept":
            _logger.warning("Found codeableConcept ^^")
            return flatten_CodeableConcept(element, profile)
        case "BackboneElement":
            _logger.warning("Found backbone ^^")
            return flatten_BackboneElement(element, profile)
        case "Reference":
            _logger.warning("Found reference ^^")
            return flatten_Reference(element, profile)
        case "dateTime":
            _logger.warning("Found dateTime ^^")
            return flatten_dateTime(element, profile)
        case "Period":
            _logger.warning("Found Period ^^")
            return flatten_Period(element, profile)
        case "Polymorphic":
            _logger.warning("Found dateTime ^^")
            return flatten_polymorphic_element(element, profile)

    return None


def generate_flattening_lookup_for_profile(
    profile: StructureDefinitionSnapshot, client: FhirTerminologyClient
) -> FlatteningLookup:
    _logger.info(f"Generating flattening lookup for {profile.name}")

    fl = FlatteningLookup(url=profile.url, resource_type=profile.type)
    for element in profile.snapshot.element:
        _logger.info(f"{element.id}")
        if (fle := flatten_element(element, profile, client)) is not None:
            fl.elements[element.id] = fle

    return fl


def generate_flattening_lookup(
    manager: FhirPackageManager, client: FhirTerminologyClient
):

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
        lookup = generate_flattening_lookup_for_profile(profile, client)
        print(lookup.model_dump_json(exclude_none=True, indent=4))
