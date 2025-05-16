import copy
import json
from collections.abc import Mapping
from typing import Any, Optional, Annotated, List

from common.exceptions.translation import MissingTranslationException
from common.util.log.functions import get_logger

from fhir.resources.R4B.elementdefinition import ElementDefinitionType

from common.util.fhir.enums import FhirDataType


logger = get_logger(__file__)


# TODO: Replace these type hints wit proper fhir.resource model classes
ElementDefinitionDict = Annotated[Mapping[str, Any], "Dictionary representing FHIR ElementDefinition instance"]
StructureDefinitionDict = Annotated[Mapping[str, Any], "Dictionary representing FHIR StructureDefinition instance"]
Differential = Annotated[StructureDefinitionDict, ("Dictionary representing FHIR StructureDefinition instance as a "
                                               "differential view")]
Snapshot = Annotated[StructureDefinitionDict, ("Dictionary representing FHIR StructureDefinition instance as a snapshot "
                                           "view")]


def get_element_from_snapshot(profile_snapshot, element_id) -> dict:
    """
    Returns the element from the given FHIR profile snapshot at the given element id
    :param profile_snapshot: FHIR profile snapshot
    :param element_id: element id
    :return: element
    """
    if not profile_snapshot.get("snapshot"):
        raise KeyError(f"KeyError the snapshot has no snapshot elements. The snapshot: {profile_snapshot.get('name')}")
    try:
        for element in profile_snapshot["snapshot"]["element"]:
            if "id" in element and element["id"] == element_id:
                return element
        else:
            raise KeyError(
                f"Could not find element with id: {element_id} in the snapshot: {profile_snapshot.get('name')}")
    except KeyError:
        raise KeyError(
            f"KeyError the element id: {element_id} is not in the snapshot or the snapshot has no snapshot "
            f"elements. The snapshot: {profile_snapshot.get('name')}")
    except TypeError:
        raise TypeError(f"TypeError the snapshot is not a dict {profile_snapshot}")


def is_element_in_snapshot(profile_snapshot, element_id) -> bool:
    """
    Returns true if the given element id is in the given FHIR profile snapshot
    :param profile_snapshot: FHIR profile snapshot
    :param element_id: element id
    :return: true if the given element id is in the given FHIR profile snapshot
    """
    try:
        for element in profile_snapshot["snapshot"]["element"]:
            if "id" in element and element["id"] == element_id:
                return True
        else:
            return False
    except KeyError:
        return False


def get_parent_element(element: ElementDefinitionDict, snapshot: Snapshot) -> Optional[ElementDefinitionDict]:
    element_id = element.get('id')
    if not element_id:
        raise KeyError(f"'ElementDefinition.id' is missing in element [path='{element.get('path')}']")
    # We can determine the parent elements ID using the child elements path the FHIR spec requires the ID to align close
    # to the elements path and be hierarchical
    split = element_id.split('.')
    element_name = split[-1]
    parent_id = ".".join(split[:-1])
    # Handle slices
    if ":" in element_name:
        parent_id += "." + element_name.split(":")[0]
    parents = list(filter(lambda e: e.get('id') == parent_id, snapshot.get('snapshot', {}).get('element', [])))
    match len(parents):
        case 0:
            return None
        case 1:
            return parents[0]
        case _:
            raise Exception(f"More than one parent element was identified [id='{parent_id}']")


def is_structure_definition(file: str) -> bool:
    """
    Checks if a file is a structured definition
    :param file: potential structured definition
    :return: true if the file is a structured definition else false
    """
    with open(file, encoding="UTF-8") as json_file:
        try:
            json_data = json.load(json_file)
        except json.decoder.JSONDecodeError:
            logger.warning(f"Could not decode {file}")
            return False
        if json_data.get("resourceType") == "StructureDefinition":
            return True
        return False


def get_types_supported_by_element(element: ElementDefinitionDict) -> List[ElementDefinitionType]:
    """
    Retrieves the `type` element of an `ElementDefinition` instance
    :param element: `ElementDefinition` instance to retrieve supported types for
    :return: List of `ElementDefinition.type` `BackboneElement` instances representing the supported types
    """
    return [ElementDefinitionType(**t) for t in element.get('type', [])]


def find_type_element(element: ElementDefinitionDict, fhir_type: FhirDataType) -> Optional[ElementDefinitionType]:
    """
    Searches for the `ElementDefinition.type` element matching the provided FHIR data type
    :param element: `ElementDefinition` instance through which supported types to search
    :param fhir_type: FHIR data type to search for
    :return: Matching `ElementDefinition.type` element or `None` of the type is not supported
    """
    for t in get_types_supported_by_element(element):
        if t.code == fhir_type.value:
            return t
    return None


def supports_type(element: ElementDefinitionDict, fhir_type: FhirDataType) -> bool:
    """
    Determined if the given `ElementDefinition` instance supports the provided FHIR data type
    :param element: `ElementDefinition` instance to check
    :param fhir_type: FHIR data type for which to determine whether it is support by the `ElementDefinition` instance
    :return: Boolean indicating support
    """
    return find_type_element(element, fhir_type) is not None
