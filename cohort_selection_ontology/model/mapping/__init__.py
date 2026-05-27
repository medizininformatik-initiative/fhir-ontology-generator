from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, TypeVar, Generic, Callable, Any

from pydantic import Field, SerializeAsAny
from sortedcontainers import SortedSet

from cohort_selection_ontology.model.ui_data import TermCode
from common.model.fhir.types import FHIRResourceTypeStr
from common.model.pydantic.mixins import StandardBaseModel
from common.util.log.functions import name


class AttributeSearchParameter(StandardBaseModel):
    """
    AttributeSearchParameter the information how to translate the attribute part of a criteria to a FHIR query snippet
    :param key: Defines the code of the attribute and acts as unique identifier within the ui_profile
                           (Required)
    :param types: Set of types the attribute supports
    """

    key: TermCode
    types: List[str]


T = TypeVar("T", bound="DenormalizedMapping")


class Mapping(StandardBaseModel, Generic[T], ABC):
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

    @classmethod
    def __sort_key__(cls) -> Callable[[dict[str, Any]], Any]:
        return lambda x: x.get("name")


class DenormalizedMapping(StandardBaseModel):
    name: str
    resource_type: FHIRResourceTypeStr["R4B"]
    context: TermCode
    key: TermCode

    @classmethod
    def __sort_key__(cls) -> Callable[[dict[str, Any]], Any]:
        return lambda x: repr(x.get("context")) + ":" + repr(x.get("key")) + ":" + name


class MapEntryList(StandardBaseModel):
    entries: List[SerializeAsAny[DenormalizedMapping]] = Field(default_factory=list)

    def get_code_systems(self):
        code_systems = SortedSet()
        for entry in self.entries:
            code_systems.add(entry.key.system)
            for fixed_criteria in entry.fixedCriteria:
                if fixed_criteria.type == "Coding":
                    for value in fixed_criteria.value:
                        code_systems.add(value.system)
        return code_systems
