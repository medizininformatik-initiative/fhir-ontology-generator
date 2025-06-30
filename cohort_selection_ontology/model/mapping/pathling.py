from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional, List

from cohort_selection_ontology.model.mapping import AttributeSearchParameter
from cohort_selection_ontology.model.ui_data import TermCode
from common.util.codec.json import JSONFhirOntoEncoder


class PathlingAttributeSearchParameter(AttributeSearchParameter):
    def __init__(self, types, attribute_code: TermCode, fhir_path: str):
        """
        PathlingAttributeSearchParameter stores the information how to translate the attribute part of a criteria to a
        Pathling query snippet
        :param types:
        :param attribute_code:
        :param fhir_path:
        """
        super().__init__(types, attribute_code)
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
        return json.dumps(self, cls=JSONFhirOntoEncoder, sort_keys=True, indent=4)

    # only required for version 1 support
    def __eq__(self, other):
        return self.key == other.key

    def __ne__(self, other):
        return not self.__eq__(other)

    def __lt__(self, other):
        return self.key < other.key

    def __hash__(self):
        return hash(self.key)
