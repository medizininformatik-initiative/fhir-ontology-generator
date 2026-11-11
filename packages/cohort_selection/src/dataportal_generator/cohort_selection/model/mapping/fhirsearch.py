# TODO: Remodel similar to CQL counterpart by incorporating abstract base classes structure
from typing import Any

from pydantic import BaseModel, model_validator
from typing_extensions import deprecated

from common.model.terminology import TermCode
from dataportal_generator.cohort_selection.model.ui_profile import VALUE_TYPE_OPTIONS


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


class FixedFHIRCriteria(BaseModel):
    value: list[TermCode]
    type: str
    searchParameter: str


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