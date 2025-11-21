from __future__ import annotations

import abc
from typing import Optional, List, Literal, Annotated, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from cohort_selection_ontology.model.ui_data import (
    TranslationDisplayElement,
    BulkTranslationDisplayElement,
)
from common.util.fhir.enums import FhirDataType, FhirSearchType, FhirComplexDataType


class Filter(BaseModel):
    type: FhirSearchType
    name: str
    ui_type: Literal["code", "timeRestriction"]
    valueSetUrls: Annotated[Optional[List[str]], Field(default=None)]


class Detail(BaseModel, abc.ABC):
    display: Annotated[Optional[TranslationDisplayElement], Field(default=None)]
    description: Annotated[Optional[TranslationDisplayElement], Field(default=None)]
    module: Annotated[Optional[TranslationDisplayElement], Field(default=None)]


class ProfileReference(BaseModel):
    url: str
    display: TranslationDisplayElement
    fields: BulkTranslationDisplayElement


class FieldDetail(Detail):
    id: str
    type: Annotated[Optional[FhirDataType], Field(exclude=True, default=None)]
    recommended: Annotated[bool, Field(default=False)]
    required: Annotated[bool, Field(default=False)]
    children: Annotated[List[FieldDetail], Field(default=[])]

    model_config = ConfigDict(use_enum_values=True)


class ReferenceDetail(FieldDetail):
    type: Annotated[
        FhirDataType,
        Field(exclude=True, init=False, default=FhirComplexDataType.REFERENCE),
    ]
    referencedProfiles: Annotated[List[ProfileReference], Field(default=[])]


class ProfileDetail(Detail):
    url: str
    filters: Annotated[
        List[Filter],
        Field(
            default=[],
        ),
    ]
    fields: Annotated[List[FieldDetail], Field(default=[])]
    references: Annotated[List[ReferenceDetail], Field(default=[])]


ProfileDetailList: TypeAlias = List[ProfileDetail]
ProfileDetailListTA = TypeAdapter(ProfileDetailList)
