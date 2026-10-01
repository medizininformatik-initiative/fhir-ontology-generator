from typing import Literal, Any

from pydantic import BaseModel, Field
from typing_extensions import deprecated

from common.model.localization import TranslationDisplayElement
from common.model.pydantic.mixins import SerializeSorted
from dataportal_generator.common.model.terminology import TermCode

UI_PROFILES = set()

VALUE_TYPE_OPTIONS = Literal[
    "concept", "quantity", "reference", "date", "composite", "Age"
]


class CriteriaSet(BaseModel):
    url: str
    contextualized_term_codes: list[tuple[TermCode, TermCode]] = Field(
        default_factory=list
    )

    @deprecated("Use ``model_dump_json()``")
    def to_json(self, **kwargs) -> str:
        return self.model_dump_json(**kwargs)


class ValueSet(BaseModel):
    url: str
    valueSet: dict[str, Any] = Field(default_factory=dict)

    @deprecated("Use ``model_dump_json()``")
    def to_json(self, **kwargs) -> str:
        return self.model_dump_json(**kwargs)


class ValueDefinition(BaseModel, SerializeSorted):
    type: VALUE_TYPE_OPTIONS
    referencedValueSet: list[ValueSet] = Field(default_factory=list)
    allowedUnits: list[TermCode] = Field(default_factory=list)
    precision: int = Field(default=1)
    min: int | None = Field(default=None)
    max: int | None = Field(default=None)
    referencedCriteriaSet: list[CriteriaSet] = Field(default_factory=list)
    optional: bool = Field(default=True)
    display: TranslationDisplayElement | None = Field(default=None)

    @deprecated("Use ``model_dump()``")
    def to_dict(self, **kwargs) -> dict[str, Any]:
        return self.model_dump(**kwargs)


class AttributeDefinition(ValueDefinition):
    attributeCode: TermCode | None = Field(default=None)


class UIProfile(BaseModel):
    name: str
    timeRestrictionAllowed: bool = Field(default=True)
    valueDefinition: ValueDefinition | None = Field(default=None)
    attributeDefinitions: list[AttributeDefinition] = Field(default_factory=list)

    @classmethod
    @deprecated("Use ``model_validate_json()``")
    def from_json(cls, json_string: str, **kwargs) -> "UIProfile":
        return cls.model_validate_json(json_string, **kwargs)

    @deprecated("Use ``model_dump_json()``")
    def to_json(self, **kwargs) -> str:
        return self.model_dump_json(**kwargs)

    @deprecated("Use ``model_dump()``")
    def to_dict(self, **kwargs) -> dict[str, Any]:
        return self.model_dump(**kwargs)

    def __eq__(self, other):
        return self.name == other.name

    def __hash__(self):
        return hash(self.name)
