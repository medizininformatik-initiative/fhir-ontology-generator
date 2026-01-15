from dataclasses import dataclass, field
from logging import Logger
from typing import List, Dict, Set, Mapping, Tuple

import json

from pydantic import BaseModel, Field

from cohort_selection_ontology.model.ui_profile import del_keys, del_none
from cohort_selection_ontology.model.ui_data import Module, TermCode
from common.util.codec.json import JSONSerializable
from common.util.log.functions import get_class_logger


class TermEntryNode(BaseModel):
    term_code: TermCode
    parents: List[str] = Field(default_factory=list)
    children: List[str] = Field(default_factory=list)

    def __repr__(self) -> str:
        return f"{self.parents} {self.children}"

    def __hash__(self) -> int:
        return hash(self.term_code)

    def to_ui_tree_entry(self):
        return {
            "key": self.term_code.code,
            "parents": self.parents,
            "children": self.children,
        }


@dataclass
class TreeMap(JSONSerializable):
    entries: Dict[str, TermEntryNode]
    context: TermCode
    system: str
    version: str
    DO_NOT_SERIALIZE = ["DO_NOT_SERIALIZE"]

    def __repr__(self) -> str:
        return f"{self.system} {self.version} {self.context} {self.entries}"

    def to_dict(self):
        data = self.__dict__.copy()
        data["entries"] = list(
            value.to_ui_tree_entry() for value in self.entries.values()
        )
        if self.context:
            data["context"] = self.context.to_dict()
        return del_none(del_keys(data, self.DO_NOT_SERIALIZE))


@dataclass
class TreeMapList(JSONSerializable):
    entries: List[TreeMap] = field(default_factory=list)
    # For naming the files
    module_name: str = None

    def to_json(self):
        return json.dumps([entry.to_dict() for entry in self.entries])


class ContextualizedTermCode(BaseModel):
    context: TermCode
    term_code: TermCode

    def to_dict(self):
        return {
            "context": self.context.to_dict(),
            "term_code": self.term_code.to_dict(),
        }


class Designation(BaseModel):
    language: str
    display: str

    def to_dict(self):
        return {"language": self.language, "display": self.display}


class ContextualizedTermCodeInfo(BaseModel):
    term_code: TermCode
    context: TermCode = None
    module: Module = None
    children_count: int = 0
    designations: List[Designation] = Field(default_factory=list)
    siblings: List[ContextualizedTermCode] = Field(default_factory=list)
    recalculated: bool = False
    __logger: Logger = get_class_logger("ContextualizedTermCodeInfo")

    def to_dict(self):
        """
        Builds a JSON string representation of this instance

        :return: JSON string
        """
        if not self.designations:
            self.designations = [
                Designation(language="default", display=self.term_code.display)
            ]
        if not self.context:
            raise ValueError("Context is required.")
        if not self.module:
            raise ValueError("Module is required.")
        if not self.recalculated:
            self.__logger.warning(
                f"Ensure you call update_children_count before calling to_dict, otherwise children_count will be incorrect."
            )
        return {
            "context": self.context.to_dict(),
            "term_code": self.term_code.to_dict(),
            "children_count": self.children_count,
            "module": self.module.to_dict(),
            "designations": [
                designation.to_dict() for designation in self.designations
            ],
            "siblings": [sibling.to_dict() for sibling in self.siblings],
        }


@dataclass
class ContextualizedTermCodeInfoList(JSONSerializable):
    entries: List[ContextualizedTermCodeInfo] = field(default_factory=list)
    __logger: Logger = get_class_logger("ContextualizedTermCodeInfoList")

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
                self.__logger.warning(
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
        descendants: Set[str],
        tree_map: TreeMap,
        count_map: Dict[str, Tuple[int, Set[str]] | int],
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

    def to_json(self):
        """
        Builds a JSON string representation of this instance

        :return: JSON string
        """
        return json.dumps([entry.to_dict() for entry in self.entries])
