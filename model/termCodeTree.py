from __future__ import annotations

from typing import List

from model.UiDataModel import del_keys, del_none, TermEntry, TermCode
import json
from sortedcontainers import SortedSet

term_codes_in_tree = SortedSet()


def to_term_code_node(category_entries: List[TermEntry]) -> TermCodeNode:
    """
    Convert a list of TermEntry trees to a term code tree.
    :param category_entries:
    :return:
    """
    root_term_entry = TermEntry([TermCode("", "", "")], context=TermCode("", "", ""))
    root = TermCodeNode(root_term_entry.termCode, root_term_entry.context)
    for entry in category_entries:
        root.add_children(entry)
    return root


class TermCodeNode:
    DO_NOT_SERIALIZE = ["DO_NOT_SERIALIZE"]

    def __init__(self, term_code: TermCode, context: TermCode = None):
        self.termCode = term_code
        self.context = context
        self.children = []

    def add_children(self, entry: TermEntry):
        direct_children = [TermCodeNode(termCode, entry.context) for termCode in entry.termCodes]
        if not entry.termCodes:
            direct_children = [TermCodeNode(entry.termCode, entry.context)]
        for direct_child in direct_children:
            for child in entry.children:
                if child not in term_codes_in_tree:
                    direct_child.add_children(child)
                    term_codes_in_tree.add(child)
        self.children += direct_children

    def to_json(self) -> str:
        """
        Convert a TermCodeNode to JSON.
        :return: JSON representation of the TermCodeNode
        """
        return json.dumps(self, default=lambda o: del_none(
            del_keys(o.__dict__, self.DO_NOT_SERIALIZE)), sort_keys=True, indent=4)
