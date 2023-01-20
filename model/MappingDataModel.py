from __future__ import annotations

import json
from typing import List

from sortedcontainers import SortedSet

from model.UIProfileModel import VALUE_TYPE_OPTIONS
from model.UiDataModel import TermCode
from model.helper import del_none


class FixedCriteria:
    def __init__(self, criteria_type, search_parameter, fhir_path, value=None):
        if value is None:
            value = []
        self.type = criteria_type
        self.value = value
        self.fhirPath = fhir_path
        self.searchParameter = search_parameter


class AttributeSearchParameter:
    """
    AttributeSearchParameter the information how to translate the attribute part of a criteria to a FHIR query snippet
    :param attribute_code defines the code of the attribute and acts as unique identifier within the ui_profile
    (Required)
    """

    def __init__(self, criteria_type, attribute_code: TermCode):
        self.attributeKey = attribute_code
        self.attributeType = criteria_type


class FhirSearchAttributeSearchParameter(AttributeSearchParameter):
    def __init__(self, criteria_type: VALUE_TYPE_OPTIONS, attribute_code: TermCode, search_parameter: str):
        """
        FhirSearchAttributeSearchParameter stores the information how to translate the attribute part of a criteria to a
        FHIR Search query snippet
        :param criteria_type defines the type of the criteria
        :param attribute_code defines the code of the attribute and acts as unique identifier within the ui_profile
        :param search_parameter defines the FHIR search parameter for the attribute
        """
        super().__init__(criteria_type, attribute_code)
        self.searchParameter = search_parameter


class CQLAttributeSearchParameter(AttributeSearchParameter):
    def __init__(self, criteria_type, attribute_code: TermCode, fhir_path: str):
        """
        CQLAttributeSearchParameter stores the information how to translate the attribute part of a criteria to a CQL
        query snippet
        :param criteria_type:
        :param attribute_code:
        :param fhir_path:
        """
        super().__init__(criteria_type, attribute_code)
        self.fhirPath = fhir_path


class FhirMapping:
    def __init__(self, name: str, term_code_search_parameter: str = None):
        """
        FhirMapping stores all necessary information to translate a structured query to a FHIR query.
        :param name: name of the mapping acting as primary key
        :param term_code_search_parameter: FHIR search parameter that is used to identify the criteria in the structured
        """
        self.name = name
        self.termCodeSearchParameter: str | None = term_code_search_parameter
        self.valueSearchParameter: str | None = None
        self.valueType: str | None = None
        self.timeRestrictionParameter: str | None = None
        self.attributeSearchParameters: List[FhirSearchAttributeSearchParameter] = []

    def to_json(self):
        return json.dumps(self, default=lambda o: del_none(o.__dict__), sort_keys=True, indent=4)

    def add_attribute(self, attribute_type, attribute_key, attribute_search_parameter):
        self.attributeSearchParameters.append(
            FhirSearchAttributeSearchParameter(attribute_type, attribute_key, attribute_search_parameter))


class CQLMapping:
    def __init__(self, name: str):
        """
        CQLMapping stores all necessary information to translate a structured query to a CQL query.
        :param name: name of the mapping acting as primary key
        """
        self.name = name
        self.termCodeFhirPath: str | None = None
        self.valueFhirPath: str | None = None
        self.timeRestrictionPath: str | None = None
        self.attributeFhirPath: List[CQLAttributeSearchParameter] = []

    def add_attribute(self, attribute_type, attribute_key, attribute_fhir_path):
        self.attributeFhirPath.append(
            CQLAttributeSearchParameter(attribute_type, attribute_key, attribute_fhir_path))

    def to_json(self):
        return json.dumps(self, default=lambda o: del_none(o.__dict__), sort_keys=True, indent=4)


class MapEntryList:
    def __init__(self):
        self.entries = SortedSet()

    def to_json(self):
        self.entries = list(self.entries)
        return json.dumps(self.entries, default=lambda o: del_none(o.__dict__), sort_keys=True, indent=4)

    def get_code_systems(self):
        code_systems = SortedSet()
        for entry in self.entries:
            code_systems.add(entry.key.system)
            for fixed_criteria in entry.fixedCriteria:
                if fixed_criteria.type == "coding":
                    for value in fixed_criteria.value:
                        code_systems.add(value.system)
        return code_systems
