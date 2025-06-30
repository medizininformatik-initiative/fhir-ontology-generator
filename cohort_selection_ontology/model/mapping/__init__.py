from __future__ import annotations

import json
from abc import ABC
from dataclasses import dataclass

from enum import Enum
from typing import Set, Union

from sortedcontainers import SortedSet

from cohort_selection_ontology.model.ui_data import TermCode
from common.util.codec.json import JSONFhirOntoEncoder


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