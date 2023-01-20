from __future__ import annotations

import copy
import json
import random as rd
import re
import uuid
from typing import List


def del_none(dictionary):
    import model.UIProfileModel
    """
    Delete keys with the value ``None`` in a dictionary, recursively.

    This alters the input so you may wish to ``copy`` the dict first.
    """
    for key, value in list(dictionary.items()):
        if value is None:
            del dictionary[key]
        elif isinstance(value, model.UIProfileModel.UIProfile):
            ui_profile = value.__dict__.copy()
            del ui_profile["name"]
            dictionary.update(del_none(ui_profile))
            del dictionary[key]
        elif isinstance(value, dict):
            del_none(value)
        elif isinstance(value, list):
            if not value:
                del dictionary[key]
            for element in value:
                if not isinstance(element, str):
                    del_none(element.__dict__)
    return dictionary


def del_keys(dictionary, keys):
    """
    Deletes the keys in a copy of the dictionary and returns said copy
    :param dictionary: the dictionary to delete the keys from
    :param keys: the keys to delete
    :return: the copy of the dictionary without the keys
    """
    result = copy.deepcopy(dictionary)
    for k in keys:
        result.pop(k, None)
    return result


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
    """
    A TermCode represents a concept from a terminology system.
    :param system: the terminology system
    :param code: the code for the concept
    :param display: the display for the concept
    :param version: the version of the terminology system
    """

    def __init__(self, system: str, code: str, display: str, version=None):
        self.system = system
        self.code = code
        self.version = version
        self.display = display

    def __eq__(self, other):
        return self.system == other.system and self.code == other.code

    def __hash__(self):
        return hash(self.system + self.code)

    def __lt__(self, other):
        return self.display.casefold() < other.display.casefold()

    def __repr__(self):
        return self.system + " " + self.code


class ValueDefinition:
    """
    A ValueDefinition defines the value. Contrary to the AttributeDefinition, the ValueDefinition referes to the value
    defined by the term code of the concept. I.e. the Loinc Code 3137-7 (Body height) defines the value. While the
    Snomed Code 119361006 (Plasma specimen) does not define the value, but the specimen. To express the extraction
    location an AttributeDefinition for the body site is used.
    :param value_type: defines the type of the value
    :param selectable_concepts: defines the selectable concepts for the value if the type is "concept"
    :param allowed_units: defines the allowed units for the value if the value type is "quantity"
    :param precision: defines the precision for the value if the value type is "quantity"
    :param min_val: defines the minimum value if the value type is "quantity"
    :param max_val: defines the maximum value if the value type is "quantity"
    """

    def __init__(self, value_type, selectable_concepts: List[TermCode] | None = None,
                 allowed_units: List[TermCode] | None = None, precision: int | None = None,
                 min_val: float | None = None, max_val: float | None = None):
        self.type = value_type
        self.selectableConcepts = selectable_concepts if selectable_concepts else []
        self.allowedUnits = allowed_units if allowed_units else []
        self.precision = precision if precision else 1
        self.min: float = min_val
        self.max: float = max_val


class AttributeDefinition(ValueDefinition):
    """
    An AttributeDefinition defines an attribute.
    """
    def __init__(self, attribute_code, value_type):
        super().__init__(value_type)
        self.attributeCode = attribute_code
        self.optional = True


class Unit:
    """
    Defines a unit from the UCUM code system
    :param display: the display name of the unit
    :param code: the UCUM code of the unit
    """
    def __init__(self, display, code):
        self.display = display
        self.code = code


class TermEntry(object):
    DO_NOT_SERIALIZE = ["terminologyType", "path", "DO_NOT_SERIALIZE", "fhirMapperType", "termCode", "valueDefinitions",
                        "root"]
    """
    A TermEntry represents a medical concept. TermEntries are organized in a tree structure.
    It's concept is defined by one or more TermCodes in a specific context.
    :param term_codes: A list of TermCodes that define the concept of this TermEntry
    :param terminology_type
    :param leaf: True if this TermEntry has no children
    :param selectable: True if this TermEntry can be selected by the user
    :param context: The context of this TermEntry. All children of this TermEntry will have the same context.
    """
    # TODO: context should be after term_codes. This would be a breaking change -> requires updating all uses of this \
    # class
    def __init__(self, term_codes: List[TermCode], terminology_type=None, leaf=True,
                 selectable=True, context: TermCode = None):
        self.id = str(uuid.UUID(int=rd.getrandbits(128)))
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
        self.display = (self.termCode.display if self.termCode else None)
        self.root = True
        self.context = context

    def __lt__(self, other):
        if self.display and other.display:
            return self.display.casefold() < other.display.casefold()
        return self.termCode < other.termCode

    def __repr__(self):
        return self.termCode.display

    def __len__(self):
        return len(self.children) + 1

    def to_json(self):
        """
        Serializes the TermEntry to json
        :return: The JSON representation of the TermEntry
        """
        return json.dumps(self, default=lambda o: del_none(
            del_keys(o.__dict__, self.DO_NOT_SERIALIZE)), sort_keys=True, indent=4)

    def get_leaves(self):
        """
        Returns all leaves of the TermEntry tree
        :return: the leaves of the TermEntry tree
        """
        result = []
        for child in self.children:
            if child.children:
                result += child.get_leaves()
            else:
                result += child
        return result

    def to_v1_entry(self, ui_profile):
        for key, value in ui_profile.__dict__.items():
            setattr(self, key, value)


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
