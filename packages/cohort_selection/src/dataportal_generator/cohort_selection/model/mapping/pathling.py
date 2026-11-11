from pydantic import BaseModel, Field
from typing_extensions import deprecated

from dataportal_generator.cohort_selection.model.mapping import AttributeSearchParameter


class PathlingAttributeSearchParameter(AttributeSearchParameter):
    """
    ``PathlingAttributeSearchParameter`` stores the information how to translate the attribute part of a criteria to a
    Pathling query snippet
    """

    attributePath: str


class PathlingMapping(BaseModel):
    """
    PathlingMapping stores all necessary information to translate a structured query to a Pathling query.
    :param name: name of the mapping acting as primary key
    """

    name: str
    termCodeFhirPath: str | None = None
    valueFhirPath: str | None = None
    valueType = None
    timeRestrictionFhirPath: str | None = None
    attributeFhirPaths: list[PathlingAttributeSearchParameter] = Field(
        default_factory=list
    )
    # only required for version 1 support
    key: str | None = None

    def add_attribute(
        self, attribute_search_parameter: PathlingAttributeSearchParameter
    ):
        self.attributeFhirPaths.append(attribute_search_parameter)

    @classmethod
    @deprecated("Use ``PathlingMapping.model_validate()``")
    def from_json(cls, json_dict, **kwargs) -> "PathlingMapping":
        return cls.model_validate(json_dict, **kwargs)

    @deprecated("Use ``PathlingMapping.model_dump_json()``")
    def to_json(self, **kwargs) -> str:
        return self.model_dump_json(**kwargs)

    # only required for version 1 support
    def __eq__(self, other):
        return self.key == other.key

    def __ne__(self, other):
        return not self.__eq__(other)

    def __lt__(self, other):
        return self.key < other.key

    def __hash__(self):
        return hash(self.key)