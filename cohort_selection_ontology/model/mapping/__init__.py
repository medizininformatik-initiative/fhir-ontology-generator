from __future__ import annotations

import json
from abc import ABC, abstractmethod
from functools import total_ordering
from typing import List, TypeVar, Generic

from pydantic import BaseModel
from sortedcontainers import SortedSet

from cohort_selection_ontology.model.ui_data import TermCode
from common.model.fhir.types import FHIRResourceTypeStr
from common.model.pydantic.mixins import SerializeSorted, CamelCase
from common.util.codec.json import JSONFhirOntoEncoder


class AttributeSearchParameter(BaseModel):
    """
    AttributeSearchParameter the information how to translate the attribute part of a criteria to a FHIR query snippet
    :param key: Defines the code of the attribute and acts as unique identifier within the ui_profile
                           (Required)
    :param types: Set of types the attribute supports
    """

    key: TermCode
    types: List[str]


T = TypeVar("T", bound="DenormalizedMapping")


@total_ordering
class Mapping(BaseModel, Generic[T], ABC, CamelCase, SerializeSorted):
    name: str
    resource_type: FHIRResourceTypeStr["R4B"]

    @abstractmethod
    def denormalize(self, context: TermCode, key: TermCode) -> T:
        """
        Builds the denormalized version of the generic CQL mapping object uniquely identified by the provided context
        and key

        :param context: Context coding to associate with the denormalized version
        :param key: Key coding to associate with the denormalized version
        :return: Object of type ``T`` extending ``DenormalizedCQLMapping``
        """

        pass

    # only required for version 1 support
    def __eq__(self, other):
        return issubclass(other, self.__class__) and self.name == other.name

    def __lt__(self, other):
        return self.name < other.name

    def __hash__(self):
        return hash(self.name)


@total_ordering
class DenormalizedMapping(ABC, BaseModel, CamelCase, SerializeSorted):
    name: str
    resource_type: FHIRResourceTypeStr["R4B"]
    context: TermCode
    key: TermCode

    # only required for version 1 support
    def __eq__(self, other):
        return self.key == other.key

    def __lt__(self, other):
        return self.key < other.key

    def __hash__(self):
        return hash(self.key)


class MapEntryList:
    def __init__(self):
        self.entries = []

    def to_json(self):
        self.entries = list(self.entries)
        return json.dumps(
            self.entries, cls=JSONFhirOntoEncoder, sort_keys=True, indent=4
        )

    def get_code_systems(self):
        code_systems = SortedSet()
        for entry in self.entries:
            code_systems.add(entry.key.system)
            for fixed_criteria in entry.fixedCriteria:
                if fixed_criteria.type == "Coding":
                    for value in fixed_criteria.value:
                        code_systems.add(value.system)
        return code_systems
