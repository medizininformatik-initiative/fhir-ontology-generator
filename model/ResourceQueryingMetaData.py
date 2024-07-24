from __future__ import annotations

import json
from typing import List, Dict

from model.helper import del_none
from model.UiDataModel import TermCode, Module


class ResourceQueryingMetaData:
    """
    ResourceQueryingMetaData stores all necessary information to extract the queryable data from a FHIR resource.
    Care the combination of resource_type and context has to be unique.
    :param name: Name of the QueryingMetaData
    :param resource_type is taken from the FHIR resource type. (Required)
    :param context defines the context of the resource. (Required)
    :param term_code_defining_id defines the id that identifies the term_code element.
    :param term_codes defines the term_code elements. Prefer using term_code_defining_id. But if no id to obtain the
    term_code from is available use this parameter. I.E to define the term_code for Patient.birthdate.
    If possible use snomed codes.
    :param value_defining_id defines the id that identifies the value element.
    :param value_type defines the value type of the value element.
    Typically this will be inferred from the FHIR profile. But can be overwritten here.
    :param attribute_defining_id_type_map define the ids that identify the attribute elements. The corresponding type
    entry defines the type of the attribute element and is typically inferred from the FHIR profile. But can be
    overwritten here.
    :param time_restriction_defining_id defines the id that identifies the time restriction element.
    """
    def __init__(self, name: str, resource_type: str, module: dict, context: TermCode | dict, term_code_defining_id: str = None,
                 term_codes: List[TermCode] | List[dict] = None, value_defining_id: str = None, value_type: str = None,
                 attribute_defining_id_type_map: Dict[str, str] = None, time_restriction_defining_id: str = None):
        self.name = name
        self.value_type = value_type
        self.resource_type = resource_type
        self.context = TermCode(**context)
        self.term_codes = [TermCode(**term_code) for term_code in term_codes] if term_codes else None
        self.term_code_defining_id = term_code_defining_id
        self.value_defining_id = value_defining_id
        self.attribute_defining_id_type_map = attribute_defining_id_type_map if attribute_defining_id_type_map else {}
        self.time_restriction_defining_id = time_restriction_defining_id
        self.module = module

    def to_json(self):
        """
        Convert the object to a JSON string.
        :return: JSON representation of the object, without None values.
        """
        return json.dumps(self, default=lambda o: del_none(o.__dict__), sort_keys=True, indent=4)

    @staticmethod
    def from_json(json_data):
        """
        Convert the JSON file to an ResourceQueryingMetaData object.
        :param json_data:
        :return: ResourceQueryingMetaData object.
        """
        return ResourceQueryingMetaData(**json.load(json_data))

    def __str__(self):
        return self.to_json()

    def __repr__(self):
        return self.to_json()
