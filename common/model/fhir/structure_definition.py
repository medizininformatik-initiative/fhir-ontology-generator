import abc
import functools
import json
from collections import namedtuple
from functools import cached_property, reduce
from importlib import resources
from itertools import groupby
from typing import Mapping, List, Optional, Annotated, Union, Literal, Tuple, Any

import cachetools
from fhir.resources.R4B.elementdefinition import (
    ElementDefinition,
)
from fhir.resources.R4B.structuredefinition import StructureDefinition
from pydantic import computed_field, TypeAdapter, Discriminator, Tag

from cohort_selection_ontology.resources import cql, fhir

ProcessedElementResult = namedtuple(
    "ProcessedElementResult",
    ["element", "profile_snapshot", "module_dir", "last_short_desc"],
)
ShortDesc = namedtuple("ShortDesc", ["origin", "desc"])
FHIR_TYPES_TO_VALUE_TYPES = json.load(
    fp=(resources.files(fhir) / "fhir-types-to-value-types.json").open(
        "r", encoding="utf-8"
    )
)

CQL_TYPES_TO_VALUE_TYPES = json.load(
    fp=(resources.files(cql) / "cql-types-to-value-types.json").open(
        "r", encoding="utf-8"
    )
)


def _elem_def_key(s: StructureDefinition, e_id: str) -> str:
    return s.url + "|" + (s.version if s.version else "") + "|" + e_id


class AbstractIndexedStructureDefinition(abc.ABC, StructureDefinition):
    __indexed_field_path = str
    __indexed_field = List[ElementDefinition]

    def __check_indexed_field_type(self):
        path_components = self.__indexed_field_path.split(".")
        idx_field_value: List[ElementDefinition] = reduce(
            lambda acc, field_name: getattr(acc, field_name), path_components, self
        )
        self.__indexed_field = idx_field_value

    def __init__(self, **kwargs):
        indexed_field_path = kwargs.pop("__indexed_field_path")
        super().__init__(**kwargs)
        self.__indexed_field_path = indexed_field_path
        self.__check_indexed_field_type()

    @computed_field
    @cached_property
    def __element_by_id(self) -> Mapping[str, ElementDefinition]:
        return {element_def.id: element_def for element_def in self.__indexed_field}

    @computed_field
    @cached_property
    def __elements_by_path(self) -> Mapping[str, List[ElementDefinition]]:
        key_func = lambda ed: ed.path
        return {
            k: list(vs)
            for k, vs in groupby(
                sorted(self.__indexed_field, key=key_func), key=key_func
            )
        }

    def get_element_by_id(self, id: str) -> Optional[ElementDefinition]:
        """
        Finds an element with matching ID

        :param id: ID value to search with
        :return: `ElementDefinition` instance matching the ID or `None` if no match was found
        """
        return self.__element_by_id.get(id)

    def get_element_by_path(self, path: str) -> List[ElementDefinition]:
        """
        Finds elements with matching path

        :param path: Path value to search with
        :return: List of `ElementDefinition` instances matching the path
        """
        return self.__elements_by_path.get(path, [])

    # @cachetools.cachedmethod(cache=lambda self: self.__max_card_cache)
    @cachetools.cached(cache={}, key=_elem_def_key)
    def get_aggregated_max_cardinality(self, element_id: str) -> int | Literal["*"]:
        """
        Finds the aggregated max cardinality of an element (element definition) matching the ID

        :param element_id: ID of the element definition
        :return: Aggregated max cardinality
        """
        elem_def = self.get_element_by_id(element_id)
        if not elem_def:
            return 0
        elif elem_def.max == "0":
            return 0
        else:
            p_elem_id = elem_def.id.rsplit(".", 1)[0]
            if p_elem_id == self.type:
                return "*" if elem_def.max == "*" else int(elem_def.max)
            else:
                p_max = self.get_aggregated_max_cardinality(p_elem_id)
                return (
                    "*"
                    if p_max == "*" or elem_def.max == "*"
                    else int(elem_def.max) * p_max
                )

    # @cachetools.cachedmethod(cache=lambda self: self.__min_card_cache)
    @cachetools.cached(cache={}, key=_elem_def_key)
    def get_aggregated_min_cardinality(self, element_id: str) -> int:
        """
        Finds the aggregated min cardinality of an element (element definition) matching the ID

        :param element_id: ID of the element definition
        :return: Aggregated min cardinality
        """
        elem_def = self.get_element_by_id(element_id)
        if not elem_def:
            return 0
        elif elem_def.min == 0:
            return 0
        p_elem_id = elem_def.id.rsplit(".", 1)[0]
        if p_elem_id == self.type:
            return elem_def.min
        else:
            p_min = self.get_aggregated_min_cardinality(p_elem_id)
            return 0 if p_min == 0 else elem_def.min * p_min

    @functools.cache
    def get_aggregated_cardinality(self, element_id: str) -> Tuple[int, str]:
        """
        Finds the aggregated cardinality of an element (element definition) matching the ID

        :param element_id: ID of the element definition
        :return: Tuple containing the aggregated min and max cardinalities
        """
        return (
            self.get_aggregated_min_cardinality(element_id),
            str(self.get_aggregated_max_cardinality(element_id)),
        )


class StructureDefinitionDifferential(AbstractIndexedStructureDefinition):
    def __init__(self, /, **kwargs):
        kwargs.update({"__indexed_field_path": "differential.element"})
        super().__init__(**kwargs)


class StructureDefinitionSnapshot(AbstractIndexedStructureDefinition):
    def __init__(self, /, **kwargs):
        kwargs.update({"__indexed_field_path": "snapshot.element"})
        super().__init__(**kwargs)


def _idx_struct_def_discriminator_value(v):
    if isinstance(v, dict):
        is_snapshot = len(v.get("snapshot", {}).get("element", [])) > 0
    else:
        is_snapshot = len(getattr(getattr(v, "snapshot", {}), "element", [])) > 0
    return "snapshot" if is_snapshot else "differential"


IndexedStructureDefinition = TypeAdapter(
    Annotated[
        Union[
            Annotated[StructureDefinitionDifferential, Tag("differential")],
            Annotated[StructureDefinitionSnapshot, Tag("snapshot")],
        ],
        Discriminator(_idx_struct_def_discriminator_value),
    ]
)


def model_construct(data: Any) -> AbstractIndexedStructureDefinition:
    match _idx_struct_def_discriminator_value(data):
        case "differential":
            return StructureDefinitionDifferential.model_construct(data)
        case "snapshot":
            return StructureDefinitionSnapshot.model_construct(data)
        case _ as t:
            raise ValueError(f"Unknown structure definition type '{t}'. Cannot determine target model class")