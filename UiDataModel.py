import json
import re
import uuid


def del_none(dictionary):
    """
    Delete keys with the value ``None`` in a dictionary, recursively.

    This alters the input so you may wish to ``copy`` the dict first.
    """
    for key, value in list(dictionary.items()):
        if value is None:
            del dictionary[key]
        elif value is []:
            del dictionary[key]
        elif isinstance(value, dict):
            del_none(value)
    return dictionary


def del_keys(dictionary, keys):
    for k in keys:
        dictionary.pop(k, None)
    return dictionary


class CategoryEntry:
    DO_NOT_SERIALIZE = ["path", "DO_NOT_SERIALIZE"]

    def __init__(self, entry_id, display, path):
        self.entryId = entry_id  # References TerminologyEntry
        self.display = display
        self.path = path  # not shared in json
        self.shortDisplay = display[0]  #

    def __str__(self):
        output = ""
        for _, var in vars(self).items():
            output += " " + str(var)
        return output

    def to_json(self):
        return json.dumps(self, default=lambda o: del_none(
            del_keys(o.__dict__, self.DO_NOT_SERIALIZE)),
                          sort_keys=True, indent=4)


class TermCode:
    def __init__(self, system, code, display, version=None):
        self.system = system
        self.code = code
        self.version = version
        self.display = display

    def __eq__(self, other):
        return self.system == other.system and self.code == other.code

    def __hash__(self):
        return hash(self.system + self.code)

    def __lt__(self, other):
        return self.display < other.display

    def __repr__(self):
        return self.display + " " + self.code + " " + self.system


class ValueDefinition:
    def __init__(self, value_type):
        self.type = value_type
        self.selectableConcepts = []
        self.allowedUnits = []
        self.precision = 1
        self.min = None
        self.max = None


class AttributeDefinition(ValueDefinition):
    def __init__(self, attribute_code, value_type):
        super().__init__(value_type)
        self.attributeCode = attribute_code
        self.optional = True


class Unit:
    def __init__(self, display, code):
        self.display = display
        self.code = code


class TerminologyEntry(object):
    DO_NOT_SERIALIZE = ["terminologyType", "path", "DO_NOT_SERIALIZE", "fhirMapperType", "termCode", "valueDefinitions",
                        "root"]

    def __init__(self, term_codes, terminology_type=None, leaf=True, selectable=True):
        self.id = str(uuid.uuid4())
        self.termCodes = term_codes
        self.termCode = term_codes[0]
        for code in self.termCodes:
            if code.system == "http://snomed.info/sct":
                self.termCode = code
        self.terminologyType = terminology_type
        self.path = None
        self.children = []
        self.leaf = leaf
        self.selectable = selectable
        self.timeRestrictionAllowed = True
        self.valueDefinition = None
        self.attributeDefinitions = []
        self.display = (self.termCode.display if self.termCode else None)
        self.fhirMapperType = None
        self.root = True

    def __lt__(self, other):
        if self.display and other.display:
            return self.display < other.display
        return self.termCode < other.termCode

    def __repr__(self):
        return self.termCode.display

    def __len__(self):
        return len(self.children) + 1

    def to_json(self):
        return json.dumps(self, default=lambda o: del_none(
            del_keys(o.__dict__, self.DO_NOT_SERIALIZE)), sort_keys=True, indent=4)

    def get_leaves(self):
        result = []
        for child in self.children:
            if child.children:
                result += child.get_leaves()
            else:
                result += child
        return result


def prune_terminology_tree(tree_node, max_depth):
    if max_depth != 0:  # and not tree_node.fhirMapperType == "Procedure":
        for child in tree_node.children:
            if re.match("[A-Z][0-9][0-9]-[A-Z][0-9][0-9]$", child.termCode.code):
                prune_terminology_tree(child, max_depth)
            else:
                prune_terminology_tree(child, max_depth - 1)
    else:
        tree_node.children = []
        tree_node.leaf = True
