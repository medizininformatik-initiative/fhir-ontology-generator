from pydantic import BaseModel
from typing_extensions import deprecated

from typing import Literal, Any, ClassVar

from pydantic import BaseModel, Field, field_serializer
from typing_extensions import deprecated

from common.model.localization import TranslationDisplayElement
from dataportal_generator.common.model.terminology import TermCode

VALUE_TYPE_OPTIONS = Literal[
    "concept", "quantity", "reference", "date", "composite", "age"
]


class Module(BaseModel):
    code: str
    display: str

    def to_dict(self):
        return {"code": self.code, "display": self.display}


class RelationalTermcode(BaseModel):
    contextualized_termcode_hash: str
    display: str | dict
    terminology: str
    term_code: str
    selectable: bool

    @deprecated("Use ``model_dump()``")
    def to_dict(self, **kwargs):
        return self.model_dump(**kwargs)


class CriteriaSet(BaseModel):
    UrlBase: ClassVar[str] = "https://forschen-fuer-gesundheit.de/CriteriaSet"

    url: str
    #contextualized_term_codes: list[tuple[TermCode, TermCode]] = Field(
    #    default_factory=list
    #)
    context: TermCode
    tree_groups: list[str] = Field(default_factory=list)

    @deprecated("Use ``model_dump_json()``")
    def to_json(self, **kwargs) -> str:
        return self.model_dump_json(**kwargs)


class ValueSet(BaseModel):
    url: str
    valueSet: dict[str, Any] = Field(default_factory=dict)

    @deprecated("Use ``model_dump_json()``")
    def to_json(self, **kwargs) -> str:
        return self.model_dump_json(**kwargs)


# TODO: Tailor model class via subclassing to the supported value variants (e.g. concept, quantity, etc.)
class ValueDefinition(BaseModel):
    type: VALUE_TYPE_OPTIONS
    referencedValueSet: list[str] = Field(default_factory=list)
    allowedUnits: list[TermCode] = Field(default_factory=list)
    precision: int = Field(default=1)
    min: int | None = Field(default=None)
    max: int | None = Field(default=None)
    referencedCriteriaSet: list[CriteriaSet] = Field(default_factory=list)
    optional: bool = Field(default=True)
    display: TranslationDisplayElement | None = Field(default=None)

    @deprecated("Use ``ValueDefinition.model_dump(exclude_none=True)`` instead")
    def to_dict(self) -> dict:
        return self.model_dump(exclude_none=True)


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
