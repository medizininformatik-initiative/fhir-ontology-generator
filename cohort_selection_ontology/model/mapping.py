from __future__ import annotations

import json
from abc import ABC
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Set, Union, Any

from pydantic import BaseModel, model_validator
from sortedcontainers import SortedSet

from cohort_selection_ontology.model.ui_profile import VALUE_TYPE_OPTIONS
from cohort_selection_ontology.model.ui_data import TermCode
from common.util.codec.functions import del_none
from common.util.codec.json import JSONFhirOntoEncoder
from common.typing.fhir import FHIRPath


class AttributeSearchParameter(BaseModel):
    """
    AttributeSearchParameter the information how to translate the attribute part of a criteria to a FHIR query snippet
    :param key: Defines the code of the attribute and acts as unique identifier within the ui_profile
                           (Required)
    :param types: Set of types the attribute supports
    """
    key: TermCode
    types: Set[str]


# TODO: Remodel similar to CQL counterpart by incorporating abstract base classes structure
class FhirSearchAttributeSearchParameter(BaseModel):
    """
    FhirSearchAttributeSearchParameter stores the information how to translate the attribute part of a criteria to a
    FHIR Search query snippet::
        :param attributeType: VALUE_TYPE_OPTIONS Defines the type of the criteria
        :param attributeKey: Defines the code of the attribute and acts as unique identifier within the ui_profile
        :param attributeSearchParameter: Defines the FHIR search parameter for the attribute
        :param compositeCode: Defines the composite code for the attribute
    """
    attributeType: VALUE_TYPE_OPTIONS
    attributeKey: TermCode
    attributeSearchParameter: str
    compositeCode: TermCode | None = None

    @model_validator(mode='after')
    def validate(self, value: Any):
        if self.attributeType == 'composite' and self.compositeCode is None:
            raise ValueError("Attributes of type 'composite' must have compositeCode not None")

        return self


class SimpleCardinality(str, Enum):
    SINGLE = "single"
    MANY = "many"

    def __mul__(self, other: SimpleCardinality) -> SimpleCardinality:
        if self == SimpleCardinality.MANY or other == SimpleCardinality.MANY:
            return SimpleCardinality.MANY
        else:
            return SimpleCardinality.SINGLE

    @staticmethod
    def from_fhir_cardinality(fhir_card: Union[int, str]) -> SimpleCardinality:
        """
        Maps the cardinality value of an ElementDefinition instance in a FHIR StructureDefinition resource instance to a
        member of this enum. Note that the value '0' will be mapped to 'SINGLE'
        :param fhir_card: Cardinality value (either of 'min' or 'max' element) to map
        :return: Member of this enum class corresponding to the provided cardinality value
        """
        match fhir_card:
            case 0 | 1 | "0" | "1":
                return SimpleCardinality.SINGLE
            case _:
                return SimpleCardinality.MANY


class FixedFHIRCriteria(BaseModel):
    value: List[TermCode]
    type: str
    searchParameter: str


class FixedCQLCriteria(BaseModel):
    types: Set[str]
    value: List[TermCode]
    path: FHIRPath
    cardinality: SimpleCardinality


class CQLAttributeSearchParameter(AttributeSearchParameter):
    """
    CQLAttributeSearchParameter stores the information how to translate the attribute part of a criteria to a CQL
    query snippet::
        :param types: Set of types the attribute supports
        :param attribute_code: Coding identifying the attribute
        :param path: FHIRPath expression used in CQL to address the location the value
        :param cardinality: Aggregated cardinality of the target element
    """
    path: FHIRPath
    referenceTargetType: str | None = None
    cardinality: SimpleCardinality


class FhirMapping(BaseModel):
    """
    FhirMapping stores all necessary information to translate a structured query to a FHIR query::

        :param name: name of the mapping acting as primary key
        :param termCodeSearchParameter: FHIR search parameter that is used to identify the criteria in the structured
    """
    name: str
    termCodeSearchParameter: Optional[str] = None
    valueSearchParameter: Optional[str] = None
    valueType: Optional[str] = None
    timeRestrictionParameter: Optional[str] = None
    attributeSearchParameters: List[FhirSearchAttributeSearchParameter] = []
    fhirResourceType: Optional[str] = None
    # only required for version 1 support / json representation
    key: TermCode = None
    context: TermCode = None
    fixedCriteria: List[FixedFHIRCriteria] = []

    def to_json(self):
        return json.dumps(self, default=lambda o: del_none(o.__dict__), sort_keys=True, indent=4)

    def add_attribute(self, attribute_type, attribute_key: TermCode, attribute_search_parameter: str, composite_code=None):
        self.attributeSearchParameters.append(
            FhirSearchAttributeSearchParameter(
                attributeType = attribute_type,
                attributeKey = attribute_key,
                attributeSearchParameter = attribute_search_parameter,
                compositeCode = composite_code
            )
        )

    #  only required for version 1 support
    def __eq__(self, other):
        return self.key == other.key

    def __ne__(self, other):
        return not self.__eq__(other)

    def __lt__(self, other):
        return self.key < other.key

    def __hash__(self):
        return hash(self.key)


class CQLTypeParameter(BaseModel):
    """
    Holds information about an element within a FHIR resources that a filter targets::

        :param path: Path to the targeted element as a FHIRPath expression
        :param types: Set of types supported by this element which can be multiple if the element is polymorphic
    """
    path: FHIRPath
    types: Set[str]
    cardinality: SimpleCardinality


class CQLTimeRestrictionParameter(CQLTypeParameter):
    """
    Represents a time restriction element in a CQL mapping entry. Since we expect the corresponding element in the
    instance data to never repeat (i.e. be a list of date/time values) its cardinality is fixed to `SINGLE`
    """
    # def __init__(self, path: FHIRPath, types: Set[str]):
    #     CQLTypeParameter.__init__(self, path, types, SimpleCardinality.SINGLE)


@dataclass
class CQLMapping:
    """
    CQLMapping stores all necessary information to translate a structured query to a CQL query.
    :param name: name of the mapping acting as primary key
    """
    name: str
    resourceType: str | None = None
    termCode: Optional[CQLTypeParameter] = None
    value: Optional[CQLTypeParameter] = None
    timeRestriction: Optional[CQLTimeRestrictionParameter] = None
    attributes: List[CQLAttributeSearchParameter] = field(default_factory=list)
    # only required for version 1 support
    key: Optional[str] = None


    def add_attribute(self, attribute_search_parameter: CQLAttributeSearchParameter):
        self.attributes.append(attribute_search_parameter)

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


class PathlingAttributeSearchParameter(AttributeSearchParameter):
    """
    ``PathlingAttributeSearchParameter`` stores the information how to translate the attribute part of a criteria to a
    Pathling query snippet
    """
    attributePath: str



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


class MapEntryList:
    def __init__(self):
        self.entries = []

    def to_json(self):
        self.entries = list(self.entries)
        return json.dumps(self.entries, cls=JSONFhirOntoEncoder, sort_keys=True, indent=4)

    def get_code_systems(self):
        code_systems = SortedSet()
        for entry in self.entries:
            code_systems.add(entry.key.system)
            for fixed_criteria in entry.fixedCriteria:
                if fixed_criteria.type == "Coding":
                    for value in fixed_criteria.value:
                        code_systems.add(value.system)
        return code_systems
