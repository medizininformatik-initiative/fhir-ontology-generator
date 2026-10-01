from abc import ABC
from typing import Generic, Literal, TYPE_CHECKING

if TYPE_CHECKING:
    from _typeshed import SupportsRead

import yaml
from pydantic import BaseModel, Field, model_validator
from typing_extensions import deprecated, Any, TypeVar

from dataportal_generator.common.model.terminology import TermCode


class Expression(BaseModel):
    language: str = Field(default="text/fhirpath")
    expression: str

    @model_validator(mode="before")
    @classmethod
    def _validate_input(cls, data: Any) -> Any:
        match data:
            case str(v):
                return {"language": "text/fhirpath", "expression": v}
            case dict(v):
                return v
            case _:
                raise TypeError(f"Unsupported type '{type(data)}'")


class CriterionDefinitionSource(BaseModel):
    structure_definition: str = Field(alias="structureDefinition")
    scope: Expression | None = Field(default=None)


T = TypeVar("T")


class CriterionIdentifier(BaseModel, ABC, Generic[T]):
    type: Literal["fixed", "binding"] = Field(default="binding")
    definition: list[TermCode] | Expression | None = Field(default=None)

    @model_validator(mode="after")
    @classmethod
    def _validate_model(cls, data: "CriterionIdentifier") -> "CriterionIdentifier":
        if data.type == "fixed" and not isinstance(data.definition, list):
            raise ValueError("For type 'fixed', definition must be a list of TermCode.")
        if data.type == "binding" and not isinstance(data.definition, Expression):
            raise ValueError("For type 'binding', definition must be an Expression.")
        return data


class CriterionValue(BaseModel):
    # TODO: Is 'type' still needed? Can't we extract it from the element definition
    type: Literal["code", "concept", "quantity", "Age", "reference", "integer", "calculated", "reference"]
    definition: Expression
    optional: bool = Field(default=True)


class CriterionAttribute(BaseModel):
    name: str
    type: str | None = Field(default=None)
    definition: Expression
    optional: bool = Field(default=True)


class CriterionDefinition(BaseModel):
    """
    CriterionDefinition stores all necessary information to extract the queryable data from a FHIR resource.
    Care the combination of resource_type and context has to be unique.
    """

    name: str
    context: TermCode
    module: str
    definition_source: CriterionDefinitionSource = Field(alias="definitionSource")

    identifier: CriterionIdentifier
    time_restriction: Expression | None = Field(default=None, alias="timeRestriction")
    value: CriterionValue | None = Field(default=None)
    attributes: list[CriterionAttribute] = Field(default_factory=list)

    @deprecated("Use ``model_dump_json()``")
    def to_json(self, **kwargs) -> str:
        """
        Convert the object to a JSON string
        :return: JSON representation of the object, without None values
        """
        return self.model_dump_json(**kwargs)

    @classmethod
    @deprecated("Use ``model_validate``")
    def from_json(cls, json_data: dict[str, Any], **kwargs) -> "CriterionDefinition":
        """
        Convert the JSON data to a CriterionDefinition object
        :param json_data: JSON object to parse as an instance of this class
        :return: CriterionDefinition object
        """
        return cls.model_validate(json_data, **kwargs)

    @classmethod
    def model_validate_yaml(cls, data: "str | bytes | SupportsRead[str] | SupportsRead[bytes]") -> "CriterionDefinition":
        """
        Loads a model instance from YAML-formatted data
        :param data: YAML data/data source
        :return: ``CriterionDefinition`` instance
        """
        return cls.model_validate(yaml.safe_load(data))
