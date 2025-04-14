import copy
import json
from dataclasses import dataclass, field, asdict
from typing import Literal, List, Tuple, ClassVar, Dict

from model.UiDataModel import TermCode, TranslationElementDisplay
from common.util.codec.functions import del_none

UI_PROFILES = set()

VALUE_TYPE_OPTIONS = Literal["concept", "quantity", "reference", "date", "composite"]


@dataclass
class CriteriaSet:
    url: str
    contextualized_term_codes: List[Tuple[TermCode, TermCode]] = field(default_factory=list)

    def to_json(self):
        def custom_serializer(obj):
            if isinstance(obj, TermCode):
                return asdict(obj)
            if isinstance(obj, CriteriaSet):
                return asdict(obj)
            raise TypeError(f"Type {type(obj)} not serializable")

        criteria_dict = asdict(self)

        return json.dumps(criteria_dict, default=custom_serializer, indent=4)


@dataclass
class ValueSet:
    url: str
    valueSet: Dict = field(default_factory=dict)

    def to_json(self):
        return json.dumps(self, default=lambda o: del_none(self.valueSet), indent=4)


@dataclass
class ValueDefinition:
    type: VALUE_TYPE_OPTIONS
    referencedValueSet: ValueSet = None
    allowedUnits: List[TermCode] = field(default_factory=list)
    precision: int = 1
    min: float = None
    max: float = None
    referencedCriteriaSet: CriteriaSet = None
    optional: bool = True
    display: TranslationElementDisplay = None

    def to_dict(self):
        data = asdict(self)
        if self.referencedCriteriaSet:
            data['referencedCriteriaSet'] = self.referencedCriteriaSet.url
        if self.referencedValueSet:
            data['referencedValueSet'] = self.referencedValueSet.url
        return data


@dataclass
class AttributeDefinition(ValueDefinition):
    attributeCode: TermCode = None

    # TODO: This is not best practice. See python dataclass non-default argument follows default argument
    # However would require a lot of refactoring
    def __init__(self, attribute_code, value_type, optional: bool = True):
        super().__init__(value_type, optional=optional)
        self.attributeCode = attribute_code


class Unit:
    def __init__(self, display, code):
        self.display = display
        self.code = code


def del_keys(dictionary, keys):
    result = copy.deepcopy(dictionary)
    for k in keys:
        result.pop(k, None)
    return result


@dataclass
class UIProfile:
    name: str
    timeRestrictionAllowed: bool = True
    valueDefinition: ValueDefinition = None
    attributeDefinitions: List[AttributeDefinition] = field(default_factory=list)
    DO_NOT_SERIALIZE: ClassVar[List[str]] = []  # ClassVar indicates that it's a class-level variable

    @classmethod
    def from_json(cls, json_string):
        return cls(**json.loads(json_string))

    def to_json(self):
        return json.dumps(self.to_dict(), default=del_none, sort_keys=True, indent=4)

    def to_dict(self):
        data = asdict(self)
        if self.valueDefinition:
            data["valueDefinition"] = self.valueDefinition.to_dict()
        if self.attributeDefinitions:
            data["attributeDefinitions"] = [attr.to_dict() for attr in self.attributeDefinitions]
        return data

    def __eq__(self, other):
        return self.name == other.name

    def __hash__(self):
        return hash(self.name)
