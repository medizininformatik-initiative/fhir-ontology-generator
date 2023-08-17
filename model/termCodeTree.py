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
    root = TermCodeNode(root_term_entry)
    for entry in category_entries:
        root.children.append(TermCodeNode(entry))
    return root


class TermCodeNode:
    DO_NOT_SERIALIZE = ["DO_NOT_SERIALIZE"]
    """
    TermCodeNode is used to create a tree structure of term codes.
    TermCodeEntries are converted to TermCodeNodes.
    """

    def __init__(self, term_entry):
        terminology_entry = term_entry
        self.termCode = terminology_entry.termCode
        self.context = terminology_entry.context
        if not terminology_entry.selectable and not self.termCode.system:
            self.termCode.system = "mii.abide"
        self.children = self._get_children(terminology_entry)

    @staticmethod
    def _get_children(terminology_entry: TermEntry) -> List[TermCodeNode]:
        """
        Convert a TermEntry to a list of TermCodeNodes.
        :param terminology_entry: term entry to convert
        :return: list of TermCodeNodes
        """
        result = []
        for child in terminology_entry.children:
            if child not in term_codes_in_tree:
                result.append(TermCodeNode(child))
                term_codes_in_tree.add(child)
        return result

    def to_json(self) -> str:
        """
        Convert a TermCodeNode to JSON.
        :return: JSON representation of the TermCodeNode
        """
        return json.dumps(self, default=lambda o: del_none(
            del_keys(o.__dict__, self.DO_NOT_SERIALIZE)), sort_keys=True, indent=4)
