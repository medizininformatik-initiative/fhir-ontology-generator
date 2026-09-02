from __future__ import annotations

import abc
from functools import total_ordering
from typing import Annotated, Literal, TypeAlias

from common.model.pydantic.mixins import SerializeSorted
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from cohort_selection_ontology.model.ui_data import (
    BulkTranslationDisplayElement,
    TranslationDisplayElement,
)


@total_ordering
class Filter(BaseModel, SerializeSorted):
    type: str
    name: str
    ui_type: Literal["code", "timeRestriction"]
    valueSetUrls: Annotated[
        list[str] | None,
        Field(default=None),
    ]

    def __eq__(self, other):
        return self.name == other.name

    def __lt__(self, other):
        return self.name < other.name


class Detail(BaseModel, abc.ABC, SerializeSorted):
    display: Annotated[TranslationDisplayElement | None, Field(default=None)]
    description: Annotated[TranslationDisplayElement | None, Field(default=None)]
    module: Annotated[TranslationDisplayElement | None, Field(default=None)]


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
    type: Annotated[str | None, Field(exclude=True, default=None)]
    recommended: Annotated[bool, Field(default=False)]
    required: Annotated[bool, Field(default=False)]
    children: Annotated[list[FieldDetail], Field(default=[])]

    model_config = ConfigDict(use_enum_values=True)

    def __eq__(self, other):
        return self.id == other.id

    def __lt__(self, other):
        return self.id < other.id


class ReferenceDetail(FieldDetail):
    type: Annotated[
        Literal["Reference", "Extension"],
        Field(exclude=True, init=False, default="Reference"),
    ]
    referencedProfiles: Annotated[list[ProfileReference], Field(default=[])]


@total_ordering
class ProfileDetail(Detail):
    url: str
    filters: Annotated[
        list[Filter],
        Field(
            default=[],
        ),
    ]
    fields: Annotated[list[FieldDetail], Field(default=[])]
    references: Annotated[list[ReferenceDetail], Field(default=[])]

    def __eq__(self, other):
        return self.url == other.url

    def __lt__(self, other):
        return self.url < other.url


ProfileDetailList: TypeAlias = list[ProfileDetail]
ProfileDetailListTA = TypeAdapter(ProfileDetailList)
