from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, Field, field_serializer, model_serializer
from pydantic_core.core_schema import SerializationInfo, SerializerFunctionWrapHandler
from typing_extensions import deprecated

from cohort_selection_ontology.model.ui_data import Module, TermCode
from common.util.log.functions import get_logger

_logger = get_logger(__file__)


class TermEntryNode(BaseModel):
    term_code: TermCode
    parents: list[str] = Field(default_factory=list)
    children: list[str] = Field(default_factory=list)

    def __repr__(self) -> str:
        return f"{self.parents} {self.children}"

    def __hash__(self) -> int:
        return hash(self.term_code)

    def to_ui_tree_entry(self) -> dict[str, Any]:
        return {
            "key": self.term_code.code,
            "parents": self.parents,
            "children": self.children,
        }


class TreeMap(BaseModel):
    entries: dict[str, TermEntryNode]
    context: TermCode
    system: str
    version: str

    @classmethod
    @field_serializer("entries")
    def _serialize_entries(cls, entries: dict[str, TermEntryNode]) -> list[dict[str, Any]]:
        return [value.to_ui_tree_entry() for value in entries.values()]

    def __repr__(self) -> str:
        return f"{self.system} {self.version} {self.context} {self.entries}"

    @deprecated("Use ``TreeMap.model_dump(exclude_none=True)`` instead")
    def to_dict(self):
        return self.model_dump(exclude_none=True)


class TreeMapList(BaseModel):
    entries: list[TreeMap] = Field(default_factory=list)
    # For naming the files
    module_name: str | None = None

    @model_serializer(mode="plain")
    def _serialize(self, info: SerializationInfo) -> list[object]:
        return [entry.model_dump(
            mode=info.mode,
            exclude_none=info.exclude_none,
            exclude_unset=info.exclude_unset,
            exclude_defaults=info.exclude_defaults,
            context=info.context
        ) for entry in self.entries]

    @deprecated("Use ``TreeMapList.model_dump_json(exclude_none=True)`` instead")
    def to_json(self) -> str:
        return self.model_dump_json(exclude_none=True)


class ContextualizedTermCode(BaseModel):
    context: TermCode
    term_code: TermCode

    @deprecated("Use ``ContextualizedTermCode.model_dump()`` instead")
    def to_dict(self) -> dict:
        return self.model_dump()


class Designation(BaseModel):
    language: str
    display: str

    @deprecated("Use ``Designation.model_dump()`` instead")
    def to_dict(self) -> dict:
        return self.model_dump()


class ContextualizedTermCodeInfo(BaseModel):
    term_code: TermCode
    context: TermCode | None = Field(default=None)
    module: Module | None = Field(default=None)
    children_count: int = 0
    designations: list[Designation] = Field(default_factory=list)
    siblings: list[ContextualizedTermCode] = Field(default_factory=list)
    recalculated: bool = Field(default=False, exclude=True)

    @model_serializer(mode="wrap")
    def _serialize(self, handler: SerializerFunctionWrapHandler) -> dict[str, object]:
        if not self.designations:
            self.designations = [
                Designation(language="default", display=self.term_code.display)
            ]
        if not self.context:
            raise ValueError("Context is required")
        if not self.module:
            raise ValueError("Module is required")
        if not self.recalculated:
            _logger.warning(
                "Ensure you call update_children_count before calling to_dict, otherwise children_count will be incorrect."
            )
        return handler(self)

    @deprecated("Use ``ContextualizedTermCodeInfo.model_dump()`` instead")
    def to_dict(self) -> dict:
        """
        Builds a JSON string representation of this instance

        :return: JSON string
        """
        return self.model_dump()


class ContextualizedTermCodeInfoList(BaseModel):
    entries: list[ContextualizedTermCodeInfo] = Field(default_factory=list)

    def update_descendant_count(self, tree_map_list: TreeMapList):
        """
        Updates the descendant count of entries of this instance

        :param tree_map_list: List of tree maps to aggregate descendants in
        """
        count_maps = {
            f"{tree_map.system}#{tree_map.version}": self.__get_descendant_or_self_count_map(
                tree_map
            )
            for tree_map in tree_map_list.entries
        }
        for entry in self.entries:
            term_code = entry.term_code
            if count_map := count_maps.get(f"{term_code.system}#{term_code.version}"):
                count = count_map.get(term_code.code, 0)
                entry.children_count = count
                entry.recalculated = True
            else:
                _logger.warning(
                    f"No tree map for code system '{term_code.system}' and version {term_code.version} => Skipping"
                )
                continue

    def __get_descendant_or_self_count_map(
        self, tree_map: TreeMap
    ) -> Mapping[str, int]:
        """
        Builds up the descendant-or-self count mapping for the given tree map

        :param tree_map: `TreeMap` instance to build up descendant count mapping for
        :return: Descendant count mapping
        """
        m = {}
        entries = tree_map.entries
        for k, v in entries.items():
            if len(v.children) == 0:
                m[k] = 1
                if len(v.parents) > 0:
                    for p_key in v.parents:
                        self.__traverse_parent(p_key, {k}, tree_map, m)
        return m

    def __traverse_parent(
        self,
        parent_key: str,
        descendants: set[str],
        tree_map: TreeMap,
        count_map: dict[str, tuple[int, set[str]] | int],
    ):
        """
        Internal method for traversing `tree_map` upwards and build up the descendant count map `count_map`. Note that
        this method is built to handle poly hierarchies (like SNOMED CT) and as such there might be faster algorithms
        for other types of hierarchies. If the method was called on all parents of all leaf concepts the count map will
        be complete

        :param parent_key: Key of the parent concept in the tree map
        :param descendants: Set of descendant concepts of a child concept of the parent concept
        :param tree_map: Tree map providing information on parents and children of concepts
        :param count_map: Associates a concept to its currently identified set of descendant concepts and of how many
                          of its child concepts descendants where already merged into its descendant set. If all
                          children contributed their descendants than the value will be replaced by the total descendant
                          count identified
        """
        parent = tree_map.entries[parent_key]
        if parent_key not in count_map:
            visits = 0
            p_descendants = {parent_key}
        else:
            visits, p_descendants = count_map[parent_key]
        visits += 1
        p_descendants.update(descendants)
        if len(parent.children) <= visits:
            count_map[parent_key] = len(p_descendants)
            for p_parent_key in parent.parents:
                self.__traverse_parent(p_parent_key, p_descendants, tree_map, count_map)
        else:
            count_map[parent_key] = (visits, p_descendants)

    @model_serializer(mode="plain")
    def _serialize(self, info: SerializationInfo) -> list[object]:
        return [
            entry.model_dump(
                mode=info.mode,
                exclude_none=info.exclude_none,
                exclude_unset=info.exclude_unset,
                exclude_defaults=info.exclude_defaults,
                context=info.context,
            )
            for entry in self.entries
        ]

    @deprecated("Use ``ContextualizedTermCodeInfoList.model_dump_json()`` instead")
    def to_json(self):
        """
        Builds a JSON string representation of this instance

        :return: JSON string
        """
        return self.model_dump_json()
