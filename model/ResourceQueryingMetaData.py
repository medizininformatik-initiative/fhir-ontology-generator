import json
from typing import List

from model.helper import del_none
from model.UiDataModel import TermCode


class ResourceQueryingMetaData:
    """
    ResourceQueryingMetaData stores all necessary information to extract the queryable data from a FHIR resource.

    :param resource_type is taken from the FHIR resource type. (Required)
    :param context defines the context of the resource. (Required)
    :param term_code_defining_path defines the path to the term_code defining element. (Required)
    :param value_defining_path defines the path to the value defining element.
    :param attribute_defining_paths define the paths to the attributes defining elements.
    :param time_restriction_defining_path defines the path to the time restriction defining element.
    """
    def __init__(self, resource_type: str, context: TermCode, term_code_defining_path: str,
                 value_defining_path: str = None, attribute_defining_paths: List[str] = None,
                 time_restriction_defining_path: str = None):
        if attribute_defining_paths is None:
            attribute_defining_paths = []
        self.context = context
        self.resourceType = resource_type
        self.termCodeDefiningPath = term_code_defining_path
        self.valueDefiningPath = value_defining_path
        self.attributeDefiningPaths = attribute_defining_paths
        self.timeRestrictionDefiningPath = time_restriction_defining_path

    def to_json(self):
        """
        Convert the object to a JSON string.
        :return: JSON representation of the object, without None values.
        """
        return json.dumps(self, default=lambda o: del_none(o.__dict__), sort_keys=True, indent=4)

    @staticmethod
    def from_json(json_data):
        """
        Convert the JSON string to an ResourceQueryingMetaData object.
        :param json_data:
        :return: ResourceQueryingMetaData object.
        """
        return ResourceQueryingMetaData(**json.loads(json_data))

    def __str__(self):
        return self.to_json()

    def __repr__(self):
        return self.to_json()
