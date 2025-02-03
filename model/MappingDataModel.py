from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import List, Optional

from sortedcontainers import SortedSet

from model.UIProfileModel import VALUE_TYPE_OPTIONS
from model.UiDataModel import TermCode
from model.helper import del_none


class FixedFHIRCriteria:
    def __init__(self, criteria_type, search_parameter, value=None):
        if value is None:
            value = []
        self.type = criteria_type
        self.value = value
        self.searchParameter = search_parameter


class FixedCQLCriteria:
    def __init__(self, criteria_type, fhir_path, value=None):
        if value is None:
            value = []
        self.type = criteria_type
        self.value = value
        self.fhirPath = fhir_path


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
    def __init__(self, criteria_type: VALUE_TYPE_OPTIONS, attribute_code: TermCode, search_parameter: str,
                 composite_code=None):
        """
        FhirSearchAttributeSearchParameter stores the information how to translate the attribute part of a criteria to a
        FHIR Search query snippet
        :param criteria_type defines the type of the criteria
        :param attribute_code defines the code of the attribute and acts as unique identifier within the ui_profile
        :param search_parameter defines the FHIR search parameter for the attribute
        :param composite_code defines the composite code for the attribute
        """
        super().__init__(criteria_type, attribute_code)
        self.attributeSearchParameter = search_parameter
        self.compositeCode = composite_code


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
        self.attributePath = fhir_path


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
        self.fhirResourceType: str | None = None
        # only required for version 1 support / json representation
        self.key = None
        self.context = None
        self.fixedCriteria: List[FixedFHIRCriteria] = []

    def to_json(self):
        return json.dumps(self, default=lambda o: del_none(o.__dict__), sort_keys=True, indent=4)

    def add_attribute(self, attribute_type, attribute_key, attribute_search_parameter, composite_code=None):
        self.attributeSearchParameters.append(
            FhirSearchAttributeSearchParameter(attribute_type, attribute_key, attribute_search_parameter, composite_code))

    #  only required for version 1 support
    def __eq__(self, other):
        return self.key == other.key

    def __ne__(self, other):
        return not self.__eq__(other)

    def __lt__(self, other):
        return self.key < other.key

    def __hash__(self):
        return hash(self.key)


@dataclass
class CQLTimeRestrictionParameter:
    """
    Holds information about an element within a FHIR resources that a filter targets
    :param fhirPath: Path to the targeted element as a FHIRPath expression
    :param types: List of types supported by this element which can be multiple if the element is polymorphic
    """
    fhirPath: str
    types: List[str]


@dataclass
class CQLMapping:
    """
    CQLMapping stores all necessary information to translate a structured query to a CQL query.
    :param name: name of the mapping acting as primary key
    """
    name: str
    resourceType: str | None = None
    termCodeFhirPath: Optional[str] = None
    valueFhirPath: Optional[str] = None
    valueType = None
    timeRestriction: Optional[CQLTimeRestrictionParameter] = None
    attributeFhirPaths: List[CQLAttributeSearchParameter] = field(default_factory=list)
    # only required for version 1 support
    key: Optional[str] = None


    def add_attribute(self, attribute_search_parameter: CQLAttributeSearchParameter):
        self.attributeFhirPaths.append(attribute_search_parameter)

    @classmethod
    def from_json(cls, json_dict):
        return cls(**json_dict)

    def to_json(self):
        return json.dumps(self, default=lambda o: del_none(o.__dict__), sort_keys=True, indent=4)

    # only required for version 1 support
    def __eq__(self, other):
        return self.key == other.key

    def __ne__(self, other):
        return not self.__eq__(other)

    def __lt__(self, other):
        return self.key < other.key

    def __hash__(self):
        return hash(self.key)


class PathlingAttributeSearchParameter(AttributeSearchParameter):
    def __init__(self, criteria_type, attribute_code: TermCode, fhir_path: str):
        """
        PathlingAttributeSearchParameter stores the information how to translate the attribute part of a criteria to a
        Pathling query snippet
        :param criteria_type:
        :param attribute_code:
        :param fhir_path:
        """
        super().__init__(criteria_type, attribute_code)
        self.attributePath = fhir_path


@dataclass
class PathlingMapping:
    """
    PathlingMapping stores all necessary information to translate a structured query to a Pathling query.
    :param name: name of the mapping acting as primary key
    """
    name: str
    termCodeFhirPath: Optional[str] = None
    valueFhirPath: Optional[str] = None
    valueType = None
    timeRestrictionFhirPath: Optional[str] = None
    attributeFhirPaths: List[PathlingAttributeSearchParameter] = field(default_factory=list)
    # only required for version 1 support
    key: Optional[str] = None

    def add_attribute(self, attribute_search_parameter: PathlingAttributeSearchParameter):
        self.attributeFhirPaths.append(attribute_search_parameter)

    @classmethod
    def from_json(cls, json_dict):
        return cls(**json_dict)

    def to_json(self):
        return json.dumps(self, default=lambda o: del_none(o.__dict__), sort_keys=True, indent=4)

    # only required for version 1 support
    def __eq__(self, other):
        return self.key == other.key

    def __ne__(self, other):
        return not self.__eq__(other)

    def __lt__(self, other):
        return self.key < other.key

    def __hash__(self):
        return hash(self.key)


class MapEntryList:
    def __init__(self):
        self.entries = []

    def to_json(self):
        self.entries = list(self.entries)
        return json.dumps(self.entries, default=lambda o: del_none(o.__dict__), sort_keys=True, indent=4)

    def get_code_systems(self):
        code_systems = SortedSet()
        for entry in self.entries:
            code_systems.add(entry.key.system)
            for fixed_criteria in entry.fixedCriteria:
                if fixed_criteria.type == "Coding":
                    for value in fixed_criteria.value:
                        code_systems.add(value.system)
        return code_systems
