import json
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
        return self.code < other.code

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


class Unit:
    def __init__(self, display, code):
        self.display = display
        self.code = code


class TerminologyEntry(object):
    DO_NOT_SERIALIZE = ["terminologyType", "path", "DO_NOT_SERIALIZE", "fhirMapperType"]

    def __init__(self, term_code, terminology_type, leaf=False, selectable=True):
        self.id = str(uuid.uuid4())
        self.termCode = term_code
        self.terminologyType = terminology_type
        self.path = None
        self.children = []
        self.leaf = leaf
        self.selectable = selectable
        self.timeRestrictionAllowed = False
        self.valueDefinitions = []
        self.display = (self.termCode.display if self.termCode else None)
        self.fhirMapperType = None

    def __lt__(self, other):
        return self.termCode < other.termCode

    def __repr__(self):
        return self.termCode.display

    def to_json(self):
        return json.dumps(self, default=lambda o: del_none(
            del_keys(o.__dict__, self.DO_NOT_SERIALIZE)), sort_keys=True, indent=4)


def prune_terminology_tree(tree_node, max_depth):
    if max_depth != 0:
        for child in tree_node.children:
            prune_terminology_tree(child, max_depth-1)
    else:
        tree_node.children = []
        tree_node.leaf = True
