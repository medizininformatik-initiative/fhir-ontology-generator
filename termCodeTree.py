from UiDataModel import del_keys, del_none, TerminologyEntry, TermCode
import json

term_codes_in_tree = set()


def to_term_code_node(category_entries):
    root = TermCodeNode(TermCode("", "", ""))
    for entry in category_entries:
        root.children.append(TermCodeNode(entry))
    return root


class TermCodeNode:
    DO_NOT_SERIALIZE = ["DO_NOT_SERIALIZE"]

    def __init__(self, *args):
        if isinstance(args[0], TerminologyEntry):
            terminology_entry = args[0]
            self.termCode = terminology_entry.termCode
            self.children = self.get_term_codes(terminology_entry)
        elif isinstance(args[0], TermCode):
            self.termCode = args[0]
            self.children = []

    @staticmethod
    def get_term_codes(terminology_entry: TerminologyEntry):
        result = []
        for child in terminology_entry.children:
            if child.termCode not in term_codes_in_tree:
                result.append(TermCodeNode(child))
                term_codes_in_tree.add(child.termCode)
        return result

    def to_json(self):
        return json.dumps(self, default=lambda o: del_none(
            del_keys(o.__dict__, self.DO_NOT_SERIALIZE)), sort_keys=True, indent=4)
