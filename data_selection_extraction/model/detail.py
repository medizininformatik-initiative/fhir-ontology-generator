from __future__ import annotations

import abc
from functools import total_ordering
from typing import Optional, List, Literal, Annotated, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from cohort_selection_ontology.model.ui_data import (
    TranslationDisplayElement,
    BulkTranslationDisplayElement,
)
from common.model.pydantic.mixins import SerializeSorted
from common.util.fhir.enums import FhirDataType, FhirSearchType, FhirComplexDataType


@total_ordering
class Filter(BaseModel, SerializeSorted):
    type: FhirSearchType
    name: str
    ui_type: Literal["code", "timeRestriction"]
    valueSetUrls: Annotated[
        Optional[List[str]],
        Field(default=None),
    ]

    def __eq__(self, other):
        return self.name == other.name

    def __lt__(self, other):
        return self.name < other.name


class Detail(BaseModel, abc.ABC, SerializeSorted):
    display: Annotated[Optional[TranslationDisplayElement], Field(default=None)]
    description: Annotated[Optional[TranslationDisplayElement], Field(default=None)]
    module: Annotated[Optional[TranslationDisplayElement], Field(default=None)]


@total_ordering
class ProfileReference(BaseModel, SerializeSorted):
    url: str
    display: TranslationDisplayElement
    fields: BulkTranslationDisplayElement

    def __eq__(self, other):
        return self.url == other.url

    def __lt__(self, other):
        return self.url < other.url


@total_ordering
class FieldDetail(Detail):
    id: str
    type: Annotated[Optional[FhirDataType], Field(exclude=True, default=None)]
    recommended: Annotated[bool, Field(default=False)]
    required: Annotated[bool, Field(default=False)]
    children: Annotated[List[FieldDetail], Field(default=[])]

    model_config = ConfigDict(use_enum_values=True)

    def __eq__(self, other):
        return self.id == other.id

    def __lt__(self, other):
        return self.id < other.id


class ReferenceDetail(FieldDetail):
    type: Annotated[
        FhirDataType,
        Field(exclude=True, init=False, default=FhirComplexDataType.REFERENCE),
    ]
    referencedProfiles: Annotated[List[ProfileReference], Field(default=[])]


@total_ordering
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

    def __eq__(self, other):
        return self.url == other.url

    def __lt__(self, other):
        return self.url < other.url


ProfileDetailList: TypeAlias = List[ProfileDetail]
ProfileDetailListTA = TypeAdapter(ProfileDetailList)
