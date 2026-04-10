from __future__ import annotations

import json
from typing import Any, List, Optional

from pydantic import BaseModel, model_validator

from cohort_selection_ontology.model.ui_data import TermCode
from cohort_selection_ontology.model.ui_profile import VALUE_TYPE_OPTIONS
from common.util.codec.functions import del_none


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
    value: List[TermCode]
    type: str
    searchParameter: str


class FhirMapping(BaseModel):
    """
    FhirMapping stores all necessary information to translate a structured query to a FHIR query::

        :param name: name of the mapping acting as primary key
        :param termCodeSearchParameter: FHIR search parameter that is used to identify the criteria in the structured
    """

    name: str
    termCodeSearchParameter: Optional[str] = None
    valueSearchParameter: Optional[str] = None
    valueType: Optional[str] = None
    timeRestrictionParameter: Optional[str] = None
    attributeSearchParameters: List[FhirSearchAttributeSearchParameter] = []
    fhirResourceType: Optional[str] = None
    # only required for version 1 support / json representation
    key: TermCode = None
    context: TermCode = None
    fixedCriteria: List[FixedFHIRCriteria] = []

    def to_json(self):
        return json.dumps(
            self, default=lambda o: del_none(o.__dict__), sort_keys=True, indent=4
        )

    def add_attribute(
        self,
        attribute_type,
        attribute_key: TermCode,
        attribute_search_parameter: str,
        composite_code=None,
    ):
        self.attributeSearchParameters.append(
            FhirSearchAttributeSearchParameter(
                attributeType=attribute_type,
                attributeKey=attribute_key,
                attributeSearchParameter=attribute_search_parameter,
                compositeCode=composite_code,
            )
        )

    def denormalize(self, context: TermCode, key: TermCode) -> FhirMapping:
        # TODO: Preliminary implementation of the Mapping API. The FHIRSearch mapping should be properly reworked in the
        #       future
        self.context = context
        self.key = key
        return self
