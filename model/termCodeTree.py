from __future__ import annotations

from model.UiDataModel import del_keys, del_none, TermEntry, TermCode
import json
from sortedcontainers import SortedSet

term_codes_in_tree = SortedSet()


def to_term_code_node(category_entries):
    """
    Convert a list of TermEntry trees to a term code tree.
    :param category_entries:
    :return:
    """
    root = TermCodeNode(TermCode("", "", ""))
    for entry in category_entries:
        root.children.append(TermCodeNode(entry))
    return root


class TermCodeNode:
    DO_NOT_SERIALIZE = ["DO_NOT_SERIALIZE"]
    """
    TermCodeNode is used to create a tree structure of term codes.
    TermCodeEntries are converted to TermCodeNodes.
    """
    def __init__(self, *args: TermEntry | TermCode):
        if isinstance(args[0], TermEntry):
            terminology_entry = args[0]
            self.termCode = terminology_entry.termCode
            if not terminology_entry.selectable:
                self.termCode.system = "mii.abide"
            self.children = self._get_term_codes(terminology_entry)
        elif isinstance(args[0], TermCode):
            self.termCode = args[0]
            self.children = []

    @staticmethod
    def _get_term_codes(terminology_entry: TermEntry):
        """
        Convert a TermEntry to a list of TermCodeNodes.
        :param terminology_entry: term entry to convert
        :return: list of TermCodeNodes
        """
        result = []
        for child in terminology_entry.children:
            if child.termCode not in term_codes_in_tree:
                result.append(TermCodeNode(child))
                term_codes_in_tree.add(child.termCode)
        return result

    def to_json(self):
        """
        Convert a TermCodeNode to JSON.
        :return: JSON representation of the TermCodeNode
        """
        return json.dumps(self, default=lambda o: del_none(
            del_keys(o.__dict__, self.DO_NOT_SERIALIZE)), sort_keys=True, indent=4)
