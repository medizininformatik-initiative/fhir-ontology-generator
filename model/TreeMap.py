from dataclasses import dataclass, field
from typing import List, Dict

import json
import logging

from helper import JsonSerializable
from model.UIProfileModel import del_keys, del_none
from model.UiDataModel import Module, TermCode

@dataclass
class TermEntryNode:
    term_code: TermCode
    parents: List[str] = field(default_factory=list)
    children: List[str] = field(default_factory=list)

    def __repr__(self) -> str:
        return f"{self.parents} {self.children}"
    
    def __hash__(self) -> int:
        return hash(self.term_code)
    
    def to_ui_tree_entry(self):
        return {"parents": self.parents,
                "children": self.children}

@dataclass
class TreeMap(JsonSerializable):
    entries: Dict[str, TermEntryNode] 
    context: TermCode
    system: str
    version: str
    DO_NOT_SERIALIZE = ["DO_NOT_SERIALIZE"]

    def __repr__(self) -> str:
        return f"{self.system} {self.version} {self.context} {self.entries}"

    def to_dict(self):
        data = self.__dict__.copy()
        data["entries"] = {key: value.to_ui_tree_entry() for key, value in self.entries.items()}
        data["context"] = self.context.to_dict()
        return del_none(del_keys(data, self.DO_NOT_SERIALIZE))
    
@dataclass
class TreeMapList(JsonSerializable):
    entries: List[TreeMap] = field(default_factory=list)
    # For naming the files
    module_name: str = None

    def to_json(self):
        return json.dumps([entry.to_dict() for entry in self.entries])


@dataclass 
class ContextualizedTermCode:
    context: TermCode
    term_code: TermCode

    def to_dict(self):
        return {"context": self.context.to_dict(),
                "term_code": self.term_code.to_dict()}

@dataclass
class Designation:
    language: str
    display: str

    def to_dict(self):
        return {"language": self.language,
                "display": self.display}

@dataclass
class ContextualizedTermCodeInfo:
    term_code: TermCode
    context: TermCode = None
    module: Module = None
    children_count: int = 0
    designations: List[Designation] = field(default_factory=list)
    siblings: List[ContextualizedTermCode] = field(default_factory=list)
    recalculated: bool = False

    def to_dict(self):
        if not self.designations:
            self.designations = [Designation("default", self.term_code.display)]
        if not self.context:
            raise ValueError("Context is required.")
        if not self.module:
            raise ValueError("Module is required.")
        if not self.recalculated:
            logging.warning(f"Ensure you call update_children_count before calling to_dict, otherwise children_count will be incorrect.")
        return {"context": self.context.to_dict(),
                "term_code": self.term_code.to_dict(),
                "children_count": self.children_count,
                "module": self.module.to_dict(),
                "designations": [designation.to_dict() for designation in self.designations],
                "siblings": [sibling.to_dict() for sibling in self.siblings]}
    
    def recalculate_children_count(self, tree_map_list: TreeMapList, term_code: TermCode):
        count = 0
        self.recalculated = True
        for tree_map in tree_map_list.entries:
            if term_code.code in tree_map.entries.keys():
                # traverse and count children
                count = len(tree_map.entries[term_code.code].children)
                for child in tree_map.entries[term_code.code].children:
                    count += self.recalculate_children_count(tree_map_list, TermCode(term_code.system, child, "", term_code.version))
                return count

@dataclass
class ContextualizedTermCodeInfoList(JsonSerializable):
    entries: List[ContextualizedTermCodeInfo] = field(default_factory=list)

    def update_children_count(self, tree_map_list: TreeMapList):
        for entry in self.entries:
            count = entry.recalculate_children_count(tree_map_list, entry.term_code)
            entry.children_count = count

    def to_json(self):
        return json.dumps([entry.to_dict() for entry in self.entries])





