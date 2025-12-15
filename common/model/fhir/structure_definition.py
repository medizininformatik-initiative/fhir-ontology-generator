import abc
import json
from collections import namedtuple
from functools import reduce, cached_property
from itertools import groupby
from importlib import resources
from typing import List, Mapping, Optional, Annotated, Union, Self

from fhir.resources.R4B.elementdefinition import ElementDefinition
from fhir.resources.R4B.structuredefinition import StructureDefinition
from pydantic import (
    computed_field,
    Discriminator,
    Tag,
    TypeAdapter,
    model_validator,
    PrivateAttr,
)

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


class AbstractIndexedStructureDefinition(abc.ABC, StructureDefinition):
    _indexed_field_path: Annotated[str, PrivateAttr()]
    _indexed_field: Annotated[List[ElementDefinition], PrivateAttr()]

    @model_validator(mode="after")
    def __check_indexed_field_type(self) -> Self:
        path_components = self._indexed_field_path.split(".")
        idx_field_value = reduce(
            lambda acc, field_name: getattr(acc, field_name), path_components, self
        )
        # Type inference fails here since it is based on the type of the initial value of the reduction
        self._indexed_field = idx_field_value
        return self

    @computed_field
    @cached_property
    def __element_by_id(self) -> Mapping[str, ElementDefinition]:
        return {element_def.id: element_def for element_def in self._indexed_field}

    @computed_field
    @cached_property
    def __elements_by_path(self) -> Mapping[str, List[ElementDefinition]]:
        key_func = lambda ed: ed.path
        return {
            k: list(vs)
            for k, vs in groupby(
                sorted(self._indexed_field, key=key_func), key=key_func
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


class StructureDefinitionDifferential(AbstractIndexedStructureDefinition):
    _indexed_field_path: str = "differential.element"


class StructureDefinitionSnapshot(AbstractIndexedStructureDefinition):
    _indexed_field_path: str = "snapshot.element"


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
