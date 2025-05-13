from __future__ import annotations

import json
from typing import List, Dict, Optional
from common.util.codec.functions import del_none
from cohort_selection_ontology.model.ui_data import TermCode, Module
from pydantic import BaseModel, model_validator, field_validator

ALLOWED_VALUE_TYPE_OPTIONS = ["code", "concept", "quantity", "Age", "reference", "integer", "calculated", "reference"]

# TODO: we want to combine all value_types and their casting to a new class below. The class should support casting
# TODO: code -> concept, Age->Quantity with a set allowed units, ... Specified in cso/core/generators/ui_profile
# class ResourceQueryingMetaDataValueType(BaseModel):
#     type: Optional[str] = None
#
#     @field_validator(mode='before')
#     def validate_value_type(cls, field, value):
#         if cls.type not in ALLOWED_VALUE_TYPE_OPTIONS:
#             raise ValueError(
#                 f"{cls.name}: Value type {cls.value_type} is not supported. Expected one of {{{', '.join(ALLOWED_VALUE_TYPE_OPTIONS)}}}"
#             )
#
#         return cls
#
#         elif value_type == "Age":
#             value_definition.type = "quantity"
#             # TODO: This could be the better option once the ValueSet is available, but then we might want to limit the
#             #  allowed units for security reasons
#             # value_definition.allowedUnits = get_termcodes_from_onto_server(AGE_UNIT_VALUE_SET)
#             value_definition.allowedUnits = [TermCode(system=UCUM_SYSTEM, code="a", display="a"), TermCode(system=UCUM_SYSTEM, code="mo", display="mo"),
#                                              TermCode(system=UCUM_SYSTEM, code="wk", display="wk"), TermCode(system=UCUM_SYSTEM, code="d", display="d")]

class ResourceQueryingMetaData(BaseModel):
    """
    ResourceQueryingMetaData stores all necessary information to extract the queryable data from a FHIR resource.
    Care the combination of resource_type and context has to be unique::
    
        :param name: Name of the QueryingMetaData
        :param resource_type: is taken from the FHIR resource type. (Required)
        :param context: defines the context of the resource. (Required)
        :param term_code_defining_id: defines the id that identifies the term_code element.
        :param term_codes: defines the term_code elements. Prefer using term_code_defining_id. But if no id to obtain the
        term_code from is available use this parameter, i.e. to define the term_code for Patient.birthdate. If possible use
        SNOMED CT codes.
        :param value_defining_id: defines the id that identifies the value element.
        :param value_type: defines the value type of the value element.
        Typically, this will be inferred from the FHIR profile. But can be overwritten here.
        :param attribute_defining_id_type_map: define the ids that identify the attribute elements. The corresponding type
        entry defines the type of the attribute element and is typically inferred from the FHIR profile. But can be
        overwritten here.
        :param time_restriction_defining_id: defines the id that identifies the time restriction element.
    """

    name: str
    context: TermCode
    module: Module | dict
    resource_type: str

    value_type: str | None = None
    value_defining_id: str | None = None
    value_optional: bool = True

    term_code_defining_id: str | None = None
    term_codes: List[TermCode] | List[dict] | None = None
    attribute_defining_id_type_map: Dict[str, Attribute] = {}
    time_restriction_defining_id: str | None = None

    @model_validator(mode='after')
    def validate(self):
        if self.value_defining_id is not None:
            if self.value_type is None:
                raise ValueError(f"{self.name}: If value_defining_id is provided, value_type shall be set")
            if self.value_type not in ALLOWED_VALUE_TYPE_OPTIONS:
                raise ValueError(f"{self.name}: Value type {self.value_type} is not supported. Expected one of {{{', '.join(ALLOWED_VALUE_TYPE_OPTIONS)}}}")

        for attribute_id, attribute in self.attribute_defining_id_type_map.items():
            if attribute.type is None:
                raise ValueError(f"{self.name}: Every Attribute must have a type set. Missing attribute type for {attribute_id}")
        if self.term_code_defining_id is None and self.term_codes is None:
            raise ValueError(f"{self.name}: Either term_code_defining_id or term_codes must be provided")
        return self

    class Attribute(BaseModel):
        name: Optional[str] = None
        type: Optional[str] = None
        optional: bool = True

    def to_json(self):
        """
        Convert the object to a JSON string
        :return: JSON representation of the object, without None values
        """
        return json.dumps(self, default=lambda o: del_none(o.__dict__), sort_keys=True, indent=4)

    @staticmethod
    def from_json(json_data):
        """
        Convert the JSON data to a ResourceQueryingMetaData object
        :param json_data: JSON object to parse as an instance of this class
        :return: ResourceQueryingMetaData object
        """
        return ResourceQueryingMetaData(**json.load(json_data))

    def __str__(self):
        return self.to_json()

    def __repr__(self):
        return self.to_json()
