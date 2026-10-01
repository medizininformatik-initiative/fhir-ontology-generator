from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, model_validator, Field, model_serializer
from typing_extensions import deprecated

from dataportal_generator.cohort_selection.model.ui_profile import VALUE_TYPE_OPTIONS
from dataportal_generator.common.model.terminology import TermCode


class AttributeSearchParameter(BaseModel):
    """
    AttributeSearchParameter the information how to translate the attribute part of a criteria to a FHIR query snippet
    :param key: Defines the code of the attribute and acts as unique identifier within the ui_profile
                           (Required)
    :param types: Set of types the attribute supports
    """

    key: TermCode
    types: set[str]


# TODO: Remodel similar to CQL counterpart by incorporating abstract base classes structure
class FhirSearchAttributeSearchParameter(BaseModel):
    """
    FhirSearchAttributeSearchParameter stores the information how to translate the attribute part of a criteria to a
    FHIR Search query snippet::
        :param attributeType: VALUE_TYPE_OPTIONS Defines the type of the criteria
        :param attributeKey: Defines the code of the attribute and acts as unique identifier within the ui_profile
        :param attributeSearchParameter: Defines the FHIR search parameter for the attribute
        :param compositeCode: Defines the composite code for the attribute
    """

    attributeType: VALUE_TYPE_OPTIONS
    attributeKey: TermCode
    attributeSearchParameter: str
    compositeCode: TermCode | None = None

    @model_validator(mode="after")
    def validate(self, value: Any):
        if self.attributeType == "composite" and self.compositeCode is None:
            raise ValueError(
                "Attributes of type 'composite' must have compositeCode not None"
            )

        return self


class SimpleCardinality(str, Enum):
    SINGLE = "single"
    MANY = "many"

    def __mul__(self, other: SimpleCardinality) -> SimpleCardinality:
        if self == SimpleCardinality.MANY or other == SimpleCardinality.MANY:
            return SimpleCardinality.MANY
        else:
            return SimpleCardinality.SINGLE

    @staticmethod
    def from_fhir_cardinality(fhir_card: int | str) -> SimpleCardinality:
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


class FixedFHIRCriteria(BaseModel):
    value: list[TermCode]
    type: str
    searchParameter: str


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


class FhirMapping(BaseModel):
    """
    FhirMapping stores all necessary information to translate a structured query to a FHIR query::

        :param name: name of the mapping acting as primary key
        :param termCodeSearchParameter: FHIR search parameter that is used to identify the criteria in the structured
    """

    name: str
    termCodeSearchParameter: str | None = None
    valueSearchParameter: str | None = None
    valueType: str | None = None
    timeRestrictionParameter: str | None = None
    attributeSearchParameters: list[FhirSearchAttributeSearchParameter] = []
    fhirResourceType: str | None = None
    # only required for version 1 support / json representation
    key: TermCode | None = None
    context: TermCode | None = None
    fixedCriteria: list[FixedFHIRCriteria] = []

    @deprecated("Use ``FhirMapping.model_dump_json()``")
    def to_json(self, **kwargs):
        return self.model_dump_json(**kwargs)

    def add_attribute(
        self,
        attribute_type,
        attribute_key: TermCode,
        attribute_search_parameter: str,
        composite_code = None,
    ):
        self.attributeSearchParameters.append(
            FhirSearchAttributeSearchParameter(
                attributeType=attribute_type,
                attributeKey=attribute_key,
                attributeSearchParameter=attribute_search_parameter,
                compositeCode=composite_code,
            )
        )

    #  only required for version 1 support
    def __eq__(self, other):
        return self.key == other.key

    def __ne__(self, other):
        return not self.__eq__(other)

    def __lt__(self, other):
        return self.key < other.key

    def __hash__(self):
        return hash(self.key)


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


class CQLMapping(BaseModel):
    """
    CQLMapping stores all necessary information to translate a structured query to a CQL query.
    :param name: name of the mapping acting as primary key
    """

    name: str
    resourceType: str | None = None
    termCode: CQLTypeParameter | None = None
    value: CQLTypeParameter | None = None
    timeRestriction: CQLTimeRestrictionParameter | None = None
    attributes: list[CQLAttributeSearchParameter] = Field(default_factory=list)
    # only required for version 1 support
    key: str | None = None

    def add_attribute(self, attribute_search_parameter: CQLAttributeSearchParameter):
        self.attributes.append(attribute_search_parameter)

    @classmethod
    @deprecated("Use ``CQLMapping.model_validate()``")
    def from_json(cls, json_dict, **kwargs) -> "CQLMapping":
        return cls.model_validate(json_dict, **kwargs)

    @deprecated("Use ``CQLMapping.model_dump_json()``")
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


class MapEntryList(BaseModel):
    entries: list = Field(default_factory=list)

    @model_serializer(mode="plain")
    def _serialize_model(self) -> list:
        return [e.model_dump() for e in self.entries]

    @deprecated("Use ``MapEntryList.model_dump_json()``")
    def to_json(self, **kwargs) -> str:
        return self.model_dump_json(**kwargs)

    def get_code_systems(self) -> set[str]:
        code_systems = set()
        for entry in self.entries:
            code_systems.add(entry.key.system)
            for fixed_criteria in entry.fixedCriteria:
                if fixed_criteria.type == "Coding":
                    for value in fixed_criteria.value:
                        code_systems.add(value.system)
        return code_systems
