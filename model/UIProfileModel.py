import copy
import json
from typing import Literal, List

from model.UiDataModel import TermCode
from model.helper import del_none

UI_PROFILES = set()

VALUE_TYPE_OPTIONS = Literal["concept", "quantity", "reference", "date", "composed"]


class ValueDefinition:
    def __init__(self, value_type: VALUE_TYPE_OPTIONS):
        self.type = value_type
        self.selectableConcepts: List[TermCode] = []
        self.allowedUnits: List[TermCode] = []
        self.precision = 1
        self.min = None
        self.max = None
        self.optional = True


class AttributeDefinition(ValueDefinition):
    def __init__(self, attribute_code, value_type):
        super().__init__(value_type)
        self.attributeCode = attribute_code
        self.optional = True


class Unit:
    def __init__(self, display, code):
        self.display = display
        self.code = code


def del_keys(dictionary, keys):
    result = copy.deepcopy(dictionary)
    for k in keys:
        result.pop(k, None)
    return result


class UIProfile(object):
    DO_NOT_SERIALIZE = []

    def __init__(self, name):
        self.name = name
        self.timeRestrictionAllowed = True
        self.valueDefinition = None
        self.attributeDefinitions = []

    def to_json(self):
        return json.dumps(self, default=lambda o: del_none(
            del_keys(o.__dict__, self.DO_NOT_SERIALIZE)), sort_keys=True, indent=4)

    def __eq__(self, other):
        return self.name == other.name

    def __hash__(self):
        return hash(self.name)
