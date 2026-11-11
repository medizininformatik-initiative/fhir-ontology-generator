from enum import Enum

from pydantic import BaseModel, Field
from typing_extensions import deprecated

from dataportal_generator.common.model.terminology import TermCode
from dataportal_generator.cohort_selection.model.mapping import AttributeSearchParameter, MappingEntry


class SimpleCardinality(str, Enum):
    SINGLE = "single"
    MANY = "many"

    def __mul__(self, other: "SimpleCardinality") -> "SimpleCardinality":
        if self == SimpleCardinality.MANY or other == SimpleCardinality.MANY:
            return SimpleCardinality.MANY
        else:
            return SimpleCardinality.SINGLE

    @staticmethod
    def from_fhir_cardinality(fhir_card: int | str) -> "SimpleCardinality":
        """
        Maps the cardinality value of an ElementDefinition instance in a FHIR StructureDefinition resource instance to a
        member of this enum. Note that the value '0' will be mapped to 'SINGLE'
        :param fhir_card: Cardinality value (either of 'min' or 'max' element) to map
        :return: Member of this enum class corresponding to the provided cardinality value
        """
        match fhir_card:
            case 0 | 1 | "0" | "1":
                return SimpleCardinality.SINGLE
            case _:
                return SimpleCardinality.MANY


class FixedCQLCriteria(BaseModel):
    types: set[str]
    value: list[TermCode]
    path: str
    cardinality: SimpleCardinality


class CQLAttributeSearchParameter(AttributeSearchParameter):
    """
    CQLAttributeSearchParameter stores the information how to translate the attribute part of a criteria to a CQL
    query snippet::
        :param types: Set of types the attribute supports
        :param attribute_code: Coding identifying the attribute
        :param path: FHIRPath expression used in CQL to address the location the value
        :param cardinality: Aggregated cardinality of the target element
    """

    path: str
    referenceTargetType: str | None = None
    cardinality: SimpleCardinality


class CQLTypeParameter(BaseModel):
    """
    Holds information about an element within a FHIR resources that a filter targets::

        :param path: Path to the targeted element as a FHIRPath expression
        :param types: Set of types supported by this element which can be multiple if the element is polymorphic
    """

    path: str
    types: set[str]
    cardinality: SimpleCardinality


class CQLTimeRestrictionParameter(CQLTypeParameter):
    """
    Represents a time restriction element in a CQL mapping entry. Since we expect the corresponding element in the
    instance data to never repeat (i.e. be a list of date/time values) its cardinality is fixed to `SINGLE`
    """

    # def __init__(self, path: FHIRPath, types: Set[str]):
    #     CQLTypeParameter.__init__(self, path, types, SimpleCardinality.SINGLE)


class CQLMapping(MappingEntry):
    """
    CQLMapping stores all necessary information to translate a structured query to a CQL query.
    """

    name: str
    resourceType: str
    value: CQLTypeParameter | None = Field(default=None)
    fixedCriteria: list[FixedCQLCriteria] = Field(default_factory=list, exclude_if=lambda x: len(x) == 0)
    attributes: list[CQLAttributeSearchParameter] = Field(default_factory=list, exclude_if=lambda x: len(x) == 0)
    timeRestriction: CQLTimeRestrictionParameter | None = Field(default=None)
    primaryCode: TermCode | None = Field(default=None)
    termCode: CQLTypeParameter | None = Field(default=None)

    def add_attribute(self, attribute_search_parameter: CQLAttributeSearchParameter):
        self.attributes.append(attribute_search_parameter)

    @classmethod
    @deprecated("Use ``CQLMapping.model_validate()``")
    def from_json(cls, json_dict, **kwargs) -> "CQLMapping":
        return cls.model_validate(json_dict, **kwargs)

    @deprecated("Use ``CQLMapping.model_dump_json()``")
    def to_json(self, **kwargs) -> str:
        return self.model_dump_json(**kwargs)
