from __future__ import annotations

import json
from typing import List

from cohort_selection_ontology.model.ui_data import TermCode
from cohort_selection_ontology.model.ui_profile import VALUE_TYPE_OPTIONS
from common.util.codec.functions import del_none


# TODO: Remodel similar to CQL counterpart by incorporating abstract base classes structure
class FhirSearchAttributeSearchParameter:
    def __init__(self, criteria_type: VALUE_TYPE_OPTIONS, attribute_code: TermCode, search_parameter: str,
                 composite_code=None):
        """
        FhirSearchAttributeSearchParameter stores the information how to translate the attribute part of a criteria to a
        FHIR Search query snippet
        :param criteria_type: Defines the type of the criteria
        :param attribute_code: Defines the code of the attribute and acts as unique identifier within the ui_profile
        :param search_parameter: Defines the FHIR search parameter for the attribute
        :param composite_code: Defines the composite code for the attribute
        """
        self.attributeType = criteria_type
        self.attributeKey = attribute_code
        self.attributeSearchParameter = search_parameter
        self.compositeCode = composite_code


class FixedFHIRCriteria:
    def __init__(self, criteria_type: str, search_parameter, value=None):
        if value is None:
            value = []
        self.type = criteria_type
        self.value = value
        self.searchParameter = search_parameter


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
