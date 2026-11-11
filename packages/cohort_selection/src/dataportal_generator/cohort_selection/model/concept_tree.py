import uuid
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, Field, model_validator, model_serializer
from pydantic_core.core_schema import SerializerFunctionWrapHandler


class ConceptTreeEntry(BaseModel):
    """
    Concept within a concept tree listing the codes of its immediate parent and child concepts. Both lists are empty if
    the code system does not define a hierarchy. If that is the case, instances of this model class will be serialized
    as a string representing the value of the ``code`` field.
    """

    code: str
    parents: list[str] = Field(default_factory=list, exclude_if=lambda v: len(v) == 0)
    children: list[str] = Field(default_factory=list, exclude_if=lambda v: len(v) == 0)

    @model_validator(mode="before")
    @classmethod
    def _deserialize(self, data: Any) -> Any:
        if isinstance(data, str):
            return {"code": data}
        return data

    @model_serializer(mode="wrap")
    def _serialize(self, handler: SerializerFunctionWrapHandler) -> Any:
        data = handler(self)
        return data["code"] if len(data) == 1 and "code" in data else data


class ConceptTree(BaseModel):
    """
    (Sub)set of concepts of a specific code system (version) and their hierarchical relations
    """

    system: str
    version: str
    entries: list[ConceptTreeEntry] = Field(default_factory=list)


class ConceptTreeGroup(BaseModel):
    """
    Actual content of a concept tree file. Contained concept trees are associated with particular value set or criterion
    attribute. The ``valueSet`` field holds the canonical of the actual value set version used to generate the group and
    ``None`` if the group was not generated from a value set
    """

    identifier: str
    valueSet: str | None = Field(default=None)
    trees: Mapping[str, ConceptTree] = Field(default_factory=dict)

    @classmethod
    def uuid_of(cls, identifier: str) -> str:
        """
        Returns the UUID generated from the supplied identifier of a concept tree group. The value is used as the
        file name for the serialized group

        :param identifier: Concept tree group identifier string
        :return: UUID generated from the identifier
        """
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, identifier))


CRITERION_IDENTIFIER_KEY = "$identifier"
CRITERION_VALUE_KEY = "$value"


# Module -> Criterion -> Identifier/Attributes. Each attribute is associated with one or more trees. For instance, if
# target element is sliced and each slices binds to a different value set, then each value sets tree will be referenced
type CriterionTreeMapping = dict[str, dict[str, dict[str, list[str]]]]