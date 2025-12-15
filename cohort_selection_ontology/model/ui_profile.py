import copy
import json
from dataclasses import field, asdict
from typing import Literal, List, Tuple, ClassVar, Optional, Mapping, Any

from pydantic import BaseModel, Field

from cohort_selection_ontology.model.ui_data import TermCode, TranslationDisplayElement
from common.util.codec.functions import del_none
from common.util.codec.json import JSONFhirOntoEncoder

UI_PROFILES = set()

VALUE_TYPE_OPTIONS = Literal[
    "concept", "quantity", "reference", "date", "composite", "Age"
]


class CriteriaSet(BaseModel):
    url: str
    contextualized_term_codes: List[Tuple[TermCode, TermCode]] = Field(
        default_factory=list
    )

    def to_json(self):
        def custom_serializer(obj):
            if isinstance(obj, BaseModel):
                return obj.model_dump()
            raise TypeError(f"Type {type(obj)} not serializable")

        criteria_dict = self.model_dump()
        return json.dumps(criteria_dict, default=custom_serializer, indent=4)


class ValueSet(BaseModel):
    url: str
    valueSet: Mapping[str, Any] = {}

    def to_json(self):
        return json.dumps(self, default=lambda o: del_none(self.valueSet), indent=4)


class ValueDefinition(BaseModel):
    type: VALUE_TYPE_OPTIONS
    referencedValueSet: List[ValueSet] = Field(default_factory=list)
    allowedUnits: List[TermCode] = Field(default_factory=list)
    precision: int = 1
    min: float = None
    max: float = None
    referencedCriteriaSet: List[CriteriaSet] = Field(default_factory=list)
    optional: bool = True
    display: TranslationDisplayElement = None

    def to_dict(self):
        data = self.model_dump()
        if self.referencedCriteriaSet:
            data["referencedCriteriaSet"] = sorted([x.url for x in self.referencedCriteriaSet])
        if self.referencedValueSet:
            data["referencedValueSet"] = sorted([x.url for x in self.referencedValueSet])
        return data


class AttributeDefinition(ValueDefinition):
    attributeCode: TermCode = None

    # TODO: This is not best practice. See python dataclass non-default argument follows default argument
    # However would require a lot of refactoring
    # def __init__(self, attribute_code, value_type, optional: bool = True):
    #     super().__init__(value_type, optional=optional)
    #     self.attributeCode = attribute_code


class Unit:
    def __init__(self, display, code):
        self.display = display
        self.code = code


def del_keys(dictionary, keys):
    result = copy.deepcopy(dictionary)
    for k in keys:
        result.pop(k, None)
    return result


class UIProfile(BaseModel):
    name: str
    timeRestrictionAllowed: bool = True
    valueDefinition: ValueDefinition = None
    attributeDefinitions: List[AttributeDefinition] = Field(default_factory=list)
    DO_NOT_SERIALIZE: ClassVar[List[str]] = (
        []
    )  # ClassVar indicates that it's a class-level variable

    @classmethod
    def from_json(cls, json_string):
        return cls(**json.loads(json_string))

    def to_json(self):
        return json.dumps(
            self.to_dict(), sort_keys=True, indent=4, cls=JSONFhirOntoEncoder
        )

    def to_dict(self):
        data = self.model_dump()
        if self.valueDefinition:
            data["valueDefinition"] = self.valueDefinition.to_dict()
        if self.attributeDefinitions:
            data["attributeDefinitions"] = [
                attr.to_dict() for attr in self.attributeDefinitions
            ]
        return data

    def __eq__(self, other):
        return self.name == other.name

    def __hash__(self):
        return hash(self.name)
