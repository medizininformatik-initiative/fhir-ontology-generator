from __future__ import annotations

import copy
import json
import random as rd
import uuid
from dataclasses import dataclass
from typing import List, Optional

from pydantic import BaseModel


def del_none(dictionary):
    import cohort_selection_ontology.model.ui_profile
    """
    Delete keys with the value ``None`` in a dictionary, recursively.

    This alters the input so you may wish to ``copy`` the dict first.
    """
    for key, value in list(dictionary.items()):
        if value is None:
            del dictionary[key]
        elif isinstance(value, cohort_selection_ontology.model.ui_profile.UIProfile):
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
    # TODO: is this class still in use? else mark as deprecated
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

    def __repr__(self):
        return self.display

    def to_json(self):
        return json.dumps(self, default=lambda o: del_none(
            del_keys(o.__dict__, self.DO_NOT_SERIALIZE)),
                          sort_keys=True, indent=4)


class Module(BaseModel):
    code: str
    display: str

    def to_dict(self):
        return {"code": self.code,
                "display": self.display}

class RelationalTermcode(BaseModel):
    contextualized_termcode_hash: str
    display: str | dict


class Translation(BaseModel):
    language: str
    value: Optional[str]


class BulkTranslation(BaseModel):
    language: str
    value: List[Optional[str]] = []


class TranslationDisplayElement(BaseModel):
    original: str
    translations: List[Translation]


class BulkTranslationDisplayElement(BaseModel):
    original: List[str] = []
    translations: List[BulkTranslation] = []

class TermCode(BaseModel):
    """
    A TermCode represents a concept from a terminology system.::

        :system: the terminology system
        :code: the code for the concept
        :display: the display for the concept
        :version: the version of the terminology system
    """

    system: str
    code: str
    display: str | TranslationDisplayElement
    version: str | None = None

    def __eq__(self, other):
        if isinstance(other, TermCode):
            return self.system == other.system and self.code == other.code
        return False

    def __hash__(self):
        return hash(self.system + self.code)

    def __lt__(self, other):
        if isinstance(other, TermCode):
            this_display = self.display.original if isinstance(self.display, TranslationDisplayElement) else self.display
            other_display = other.display.original if isinstance(other.display, TranslationDisplayElement) else other.display

            return this_display.casefold() < other_display.casefold()
        return NotImplemented

    def __repr__(self):
        return self.system + " " + self.code + " " + self.version if self.version else ""

    def to_dict(self):
        if isinstance(self.display,str):
            return {"system": self.system, "code": self.code, "display": self.display, "version": self.version}
        if isinstance(self.display, TranslationDisplayElement):
            return {"system": self.system, "code": self.code, "display": self.display.model_dump_json(), "version": self.version}
        return None


class Unit(BaseModel):
    # TODO: is this still in use? else mark as deprecated
    """
    Defines a unit from the UCUM code system
    :param display: the display name of the unit
    :param code: the UCUM code of the unit
    """
    display: str
    code: str

    # def __init__(self, display, code):
    #     self.display = display
    #     self.code = code


class TermEntry(object):
    # TODO: is this still in use? else mark as deprecated
    """
    A TermEntry represents a medical concept. TermEntries are organized in a tree structure.
    It's concept is defined by one or more TermCodes in a specific context.::

        :param term_codes: A list of TermCodes that define the concept of this TermEntry
        :param terminology_type
        :param leaf: True if this TermEntry has no children
        :param selectable: True if this TermEntry can be selected by the user
        :param context: The context of this TermEntry. All children of this TermEntry will have the same context.
    """
    DO_NOT_SERIALIZE = [
        "terminologyType",
        "path",
        "DO_NOT_SERIALIZE",
        "fhirMapperType",
        "termCode",
        "valueDefinitions",
        "root",
    ]

    # TODO: context should be after term_codes. This would be a breaking change -> requires updating all uses of this \
    # class
    def __init__(self, term_codes: List[TermCode], terminology_type=None, leaf=True,
                 selectable=True, context: TermCode = None, ui_profile=None):
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

    def __eq__(self, other):
        return self.termCode == other.termCode and self.context == other.context

    def __hash__(self):
        return hash(self.termCode.system + self.termCode.code + self.context.system + self.context.code)

    def to_json(self):
        """
        Serializes the TermEntry to json
        :return: The JSON representation of the TermEntry
        """
        return json.dumps(self, default=lambda o: del_none(
            del_keys(o.__dict__, self.DO_NOT_SERIALIZE)), sort_keys=True, indent=4)

    def get_leaves(self)->List[TermEntry]:
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

    def to_v1_entry(self, ui_profile)->None:
        for key, value in ui_profile.__dict__.items():
            setattr(self, key, value)
