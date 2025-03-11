from __future__ import annotations

import dataclasses
import json
from abc import ABC
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Set, Literal, Union

from sortedcontainers import SortedSet

from model.UIProfileModel import VALUE_TYPE_OPTIONS
from model.UiDataModel import TermCode
from model.helper import del_none
from util.codec.json import JSONSetEncoder
from util.typing.fhir import FHIRPath


class AttributeSearchParameter:
    key: TermCode
    types: Set[str]

    def __init__(self, types: Set[str], attribute_code: TermCode):
        """
        AttributeSearchParameter the information how to translate the attribute part of a criteria to a FHIR query snippet
        :param attribute_code: Defines the code of the attribute and acts as unique identifier within the ui_profile
                               (Required)
        :param types: Set of types the attribute supports
        """
        self.key = attribute_code
        self.types = types


class FhirSearchAttributeSearchParameter(AttributeSearchParameter):
    def __init__(self, types: Set[VALUE_TYPE_OPTIONS], attribute_code: TermCode, search_parameter: str,
                 composite_code=None):
        """
        FhirSearchAttributeSearchParameter stores the information how to translate the attribute part of a criteria to a
        FHIR Search query snippet
        :param types: Defines the type of the criteria
        :param attribute_code: Defines the code of the attribute and acts as unique identifier within the ui_profile
        :param search_parameter: Defines the FHIR search parameter for the attribute
        :param composite_code: Defines the composite code for the attribute
        """
        super().__init__(types, attribute_code)
        self.attributeSearchParameter = search_parameter
        self.compositeCode = composite_code


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


@dataclass
class HasSimpleCardinality(ABC):
    """
    Abstract class to represent inheriting classes having information about cardinality in a simplified manner, i.e.
    whether some of its aspects are repeatable or not
    """
    cardinality: SimpleCardinality

    def __init__(self, cardinality: SimpleCardinality):
        self.cardinality = cardinality


class FixedFHIRCriteria:
    def __init__(self, types: Set[str], search_parameter, value=None):
        if value is None:
            value = []
        self.types = types
        self.value = value
        self.searchParameter = search_parameter


class FixedCQLCriteria(HasSimpleCardinality):
    def __init__(self, types: Set[str], path: FHIRPath, cardinality: SimpleCardinality, value=None,):
        HasSimpleCardinality.__init__(self, cardinality)
        if value is None:
            value = []
        self.types = types
        self.value = value
        self.path = path


@dataclass
class CQLAttributeSearchParameter(AttributeSearchParameter, HasSimpleCardinality):
    path: FHIRPath

    def __init__(self, types: Set[str], attribute_code: TermCode, path: FHIRPath, cardinality: SimpleCardinality):
        """
        CQLAttributeSearchParameter stores the information how to translate the attribute part of a criteria to a CQL
        query snippet
        :param types: Set of types the attribute supports
        :param attribute_code: Coding identifying the attribute
        :param path: FHIRPath expression used in CQL to address the location the value
        :param cardinality: Aggregated cardinality of the target element
        """
        AttributeSearchParameter.__init__(self, types, attribute_code)
        HasSimpleCardinality.__init__(self, cardinality)
        self.path = path


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
class CQLTypeParameter(HasSimpleCardinality):
    """
    Holds information about an element within a FHIR resources that a filter targets
    :param path: Path to the targeted element as a FHIRPath expression
    :param types: Set of types supported by this element which can be multiple if the element is polymorphic
    """
    path: FHIRPath
    types: Set[str]

    def __init__(self, path: FHIRPath, types: Set[str], cardinality: SimpleCardinality):
        super().__init__(cardinality)
        self.path = path
        self.types = types


@dataclass
class CQLTimeRestrictionParameter(CQLTypeParameter):
    """
    Represents a time restriction element in a CQL mapping entry. Since we expect the corresponding element in the
    instance data to never repeat (i.e. be a list of date/time values) its cardinality is fixed to `SINGLE`
    """
    def __init__(self, path: FHIRPath, types: Set[str]):
        CQLTypeParameter.__init__(self, path, types, SimpleCardinality.SINGLE)


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
        return json.dumps(self.entries, cls=JSONSetEncoder, sort_keys=True, indent=4)

    def get_code_systems(self):
        code_systems = SortedSet()
        for entry in self.entries:
            code_systems.add(entry.key.system)
            for fixed_criteria in entry.fixedCriteria:
                if fixed_criteria.types == "Coding":
                    for value in fixed_criteria.value:
                        code_systems.add(value.system)
        return code_systems
