from collections.abc import Mapping
from typing import Any, Optional, Annotated


# TODO: Replace these type hints wit proper fhir.resource model classes
ElementDefinition = Annotated[Mapping[str, Any], "Dictionary representing FHIR ElementDefinition instance"]
StructureDefinition = Annotated[Mapping[str, Any], "Dictionary representing FHIR StructureDefinition instance"]
Differential = Annotated[StructureDefinition, ("Dictionary representing FHIR StructureDefinition instance as a "
                                               "differential view")]
Snapshot = Annotated[StructureDefinition, ("Dictionary representing FHIR StructureDefinition instance as a snapshot "
                                           "view")]


def get_parent_element(element: ElementDefinition, snapshot: Snapshot) -> Optional[ElementDefinition]:
    element_path = element.get('id')
    if not element_path:
        raise KeyError(f"'ElementDefinition.id' is missing in element [path='{element.get('path')}']")
    # We can determine the parent elements ID using the child elements path the FHIR spec requires the ID to align close
    # to the elements path and be hierarchical
    parent_id = ".".join(element_path.split('.')[:-1])
    parents = list(filter(lambda e: e.get('id') == parent_id, snapshot.get('snapshot', {}).get('element', [])))
    match len(parents):
        case 0:
            return None
        case 1:
            return parents[0]
        case _:
            raise Exception(f"More than one parent element was identified [id='{parent_id}']")
