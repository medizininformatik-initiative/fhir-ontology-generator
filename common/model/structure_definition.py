import abc
from functools import cached_property, reduce
from itertools import groupby
from typing import Mapping, List, Optional, ClassVar, Annotated, Union

from fhir.resources.R4B.elementdefinition import (
    ElementDefinition,
)
from fhir.resources.R4B.structuredefinition import StructureDefinition
from pydantic import computed_field, PrivateAttr, TypeAdapter, Tag, Field, Discriminator

from common.util.log.functions import get_class_logger


class AbstractIndexedStructureDefinition(abc.ABC, StructureDefinition):
    __indexed_field_path = str
    __indexed_field = List[ElementDefinition]

    def __check_indexed_field_type(self):
        path_components = self.__indexed_field_path.split(".")
        idx_field_value = reduce(
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

    def get_element_by_id(self, element_id: str) -> Optional[ElementDefinition]:
        """
        Finds an element with matching ID

        :param element_id: ID value to search with
        :return: `ElementDefinition` instance matching the ID or `None` if no match was found
        """
        return self.__element_by_id.get(element_id)

    def get_element_by_path(self, path: str) -> List[ElementDefinition]:
        """
        Finds elements with a matching path

        :param path: Path value to search with
        :return: List of `ElementDefinition` instances matching the path
        """
        return self.__elements_by_path.get(path)


class StructureDefinitionDifferential(AbstractIndexedStructureDefinition):
    def __init__(self, /, **kwargs):
        kwargs.update({"__indexed_field_path": "differential.element"})
        super().__init__(**kwargs)


class StructureDefinitionSnapshot(AbstractIndexedStructureDefinition):
    __logger: ClassVar = PrivateAttr(
        default=get_class_logger("StructureDefinitionSnapshot")
    )

    def __init__(self, /, **kwargs):
        kwargs.update({"__indexed_field_path": "snapshot.element"})
        super().__init__(**kwargs)

    def get_element_by_id(self, element_id: str) -> Optional[ElementDefinition]:
        element = super().get_element_by_id(element_id)
        if element is None:
            self.__logger.debug(
                f"Element {element_id} not found in snapshot: {self.name}"
            )
        return element


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
        Field(discriminator=Discriminator(_idx_struct_def_discriminator_value)),
    ]
)
