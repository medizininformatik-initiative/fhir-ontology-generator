from dataclasses import dataclass, field
from typing import List, Dict, Set

import json
import logging

from pydantic import BaseModel, Field

from cohort_selection_ontology.model.ui_profile import del_keys, del_none
from cohort_selection_ontology.model.ui_data import Module, TermCode
from common.util.codec.json import JSONSerializable


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

    def to_dict(self):
        """
        Builds a JSON string representation of this instance

        :return: JSON string
        """
        if not self.designations:
            self.designations = [Designation(language="default", display=self.term_code.display)]
        if not self.context:
            raise ValueError("Context is required.")
        if not self.module:
            raise ValueError("Module is required.")
        if not self.recalculated:
            logging.warning(
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

    def recalculate_descendant_count(
        self, tree_map_list: TreeMapList, term_code: TermCode
    ) -> int:
        """
        Calculates the number of descendants the concept represented by the `term_code` parameter has in the list of
        tree maps

        :param tree_map_list: Tree maps to iterate over
        :param term_code: Concept to count descendants of
        :return: Number of descendants
        """
        self.recalculated = True
        return len(self.__collect_descendants(tree_map_list, term_code))

    def __collect_descendants(
        self, tree_map_list: TreeMapList, term_code: TermCode
    ) -> Set[TermCode]:
        """
        Collects the descendants the concepts represented by the `term_code` parameter has in the list of tree maps

        :param tree_map_list: Tree maps to iterate over
        :param term_code: Concept to collect descendants of
        :return: Set of descendants
        """
        descendants = set()
        for tree_map in tree_map_list.entries:
            if term_code.code in tree_map.entries.keys():
                # traverse and count children
                count = len(tree_map.entries[term_code.code].children)
                for child in tree_map.entries[term_code.code].children:
                    descendants = descendants.union(
                        self.__collect_descendants(
                            tree_map_list,
                            TermCode(system=term_code.system, code=child, display="", version=term_code.version)
                        )
                    )
        return descendants


@dataclass
class ContextualizedTermCodeInfoList(JSONSerializable):
    entries: List[ContextualizedTermCodeInfo] = field(default_factory=list)

    def update_descendant_count(self, tree_map_list: TreeMapList):
        """
        Updates the descendant count of entries of this instance

        :param tree_map_list: List of tree maps to aggregate descendants in
        """
        for entry in self.entries:
            count = entry.recalculate_descendant_count(tree_map_list, entry.term_code)
            entry.children_count = count

    def to_json(self):
        """
        Builds a JSON string representation of this instance

        :return: JSON string
        """
        return json.dumps([entry.to_dict() for entry in self.entries])
