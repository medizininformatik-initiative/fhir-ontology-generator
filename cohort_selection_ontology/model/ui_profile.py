from collections.abc import Mapping
from typing import Annotated, Any, Literal

from pydantic import Field, field_serializer
from typing_extensions import deprecated

from cohort_selection_ontology.model.ui_data import TermCode, TranslationDisplayElement
from versiondiff.core.markers import DiffIgnore, Identity
from versiondiff.core.models import DiffModel

VALUE_TYPE_OPTIONS = Literal[
    "concept", "quantity", "reference", "date", "composite", "Age"
]


class CriteriaSet(DiffModel):
    url: Annotated[str, Identity()]
    contextualized_term_codes: list[tuple[TermCode, TermCode]] = Field(
        default_factory=list
    )
    
    @deprecated("Use ``CriteriaSet.model_dump_json()`` instead")
    def to_json(self) -> str:
        return self.model_dump_json()


class ValueSet(DiffModel):
    url: Annotated[str, Identity()]
    valueSet: Mapping[str, Any] = Field(default_factory=dict)

    @deprecated("Use ``ValueSet.model_dump_json(exclude_none=True)`` instead")
    def to_json(self) -> str:
        return self.model_dump_json(exclude_none=True)


class ValueDefinition(DiffModel):
    type: VALUE_TYPE_OPTIONS
    referencedValueSet: list[ValueSet | str] = Field(default_factory=list)
    allowedUnits: list[TermCode] = Field(default_factory=list)
    precision: int = Field(default=1)
    min: float | None = Field(default=None)
    max: float | None = Field(default=None)
    referencedCriteriaSet: list[CriteriaSet | str] = Field(default_factory=list)
    optional: bool = Field(default=True)
    display: Annotated[TranslationDisplayElement | None, DiffIgnore()] = Field(default=None)

    @field_serializer("referencedValueSet")
    def _serialize_referenced_value_set(self, data: list[ValueSet]) -> list[object]:
        return sorted((x.url if isinstance(x, ValueSet) else x) for x in data)

    @field_serializer("referencedCriteriaSet")
    def _serialize_referenced_criteria_set(self, data: list[CriteriaSet]) -> list[object]:
        return sorted((x.url if isinstance(x, ValueSet) else x) for x in data)

    @deprecated("Use ``ValueDefinition.model_dump(exclude_none=True)`` instead")
    def to_dict(self) -> dict:
        return self.model_dump(exclude_none=True)


class AttributeDefinition(ValueDefinition):
    attributeCode: Annotated[TermCode, Identity()]


class UIProfile(DiffModel):
    name: Annotated[str, Identity()]
    timeRestrictionAllowed: bool = Field(default=True)
    valueDefinition: ValueDefinition | None = Field(default=None)
    attributeDefinitions: list[AttributeDefinition] = Field(default_factory=list)

    @classmethod
    @deprecated("Use ``UIProfile.model_validate_json()`` instead")
    def from_json(cls, json_string: str) -> "UIProfile":
        return cls.model_validate_json(json_string)

    @deprecated("Use ``UIProfile.model_dump_json()`` instead")
    def to_json(self) -> str:
        return self.model_dump_json()

    @deprecated("Use ``UIProfile.model_dump()`` instead")
    def to_dict(self) -> dict:
        return self.model_dump()

    def __eq__(self, other):
        return self.name == other.name

    def __hash__(self):
        return hash(self.name)
