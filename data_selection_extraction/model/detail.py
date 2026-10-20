import abc
from functools import total_ordering
from typing import Annotated, Literal, TypeAlias

from pydantic import ConfigDict, Field, TypeAdapter

from versiondiff.core.markers import DiffRule, Identity
from versiondiff.core.models import DiffModel


class Translation(DiffModel):
    language: Annotated[str, Identity()]
    value: str | None = Field(default=None)


class BulkTranslation(DiffModel):
    language: Annotated[str, Identity()]
    value: list[str | None] = Field(default_factory=list)


class TranslationDisplayElement(DiffModel):
    original: Annotated[str, Identity()]
    translations: list[Translation]


class BulkTranslationDisplayElement(DiffModel):
    original: list[str] = Field(default_factory=list)
    translations: list[BulkTranslation] = Field(default_factory=list)


@total_ordering
class Filter(DiffModel):
    type: str
    name: Annotated[str, Identity()]
    ui_type: Literal["code", "timeRestriction"]
    valueSetUrls: list[str] | None = Field(default=None)

    def __lt__(self, other: "Filter"):
        if not isinstance(other, Filter):
            return NotImplemented
        return self.name < other.name

    def __eq__(self, other: object):
        if not isinstance(other, Filter):
            return NotImplemented
        return self.name == other.name


class Detail(DiffModel, abc.ABC):
    display: Annotated[TranslationDisplayElement | None, DiffRule(ignore=True)] = Field(default=None)
    description: Annotated[TranslationDisplayElement | None, DiffRule(ignore=True)] = Field(default=None)
    module: Annotated[TranslationDisplayElement | None, DiffRule(ignore=True)] = Field(default=None)


class ProfileReference(DiffModel):
    url: Annotated[str, Identity()]
    display: Annotated[TranslationDisplayElement, DiffRule(ignore=True)]
    fields: Annotated[BulkTranslationDisplayElement, DiffRule(ignore=True)]

    def __lt__(self, other: "ProfileReference"):
        if not isinstance(other, ProfileReference):
            return NotImplemented
        return self.url < other.url

    def __eq__(self, other: object):
        if not isinstance(other, ProfileReference):
            return NotImplemented
        return self.url == other.url


class FieldDetail(Detail):
    id: Annotated[str, Identity()]
    type: str | None = Field(default=None, exclude=True)
    recommended: bool = Field(default=False)
    required: bool = Field(default=False)
    children: list["FieldDetail"] = Field(default_factory=list)

    model_config = ConfigDict(use_enum_values=True)

    def __lt__(self, other: "FieldDetail"):
        if not isinstance(other, FieldDetail):
            return NotImplemented
        return self.id < other.id

    def __eq__(self, other: object):
        if not isinstance(other, FieldDetail):
            return NotImplemented
        return self.id == other.id


class ReferenceDetail(FieldDetail):
    type: str | None = Field(
        default="reference", exclude=True
    )
    referencedProfiles: list[ProfileReference] = Field(default_factory=list)


class ProfileDetail(Detail):
    url: Annotated[str, Identity()]
    filters: list[Filter] = Field(default_factory=list)
    fields: list[FieldDetail] = Field(default_factory=list)
    references: list[ReferenceDetail] = Field(default_factory=list)

    def __lt__(self, other: "ProfileDetail"):
        if not isinstance(other, ProfileDetail):
            return NotImplemented
        return self.url < other.url

    def __eq__(self, other: object):
        if not isinstance(other, ProfileDetail):
            return NotImplemented
        return self.url == other.url


ProfileDetailList: TypeAlias = list[ProfileDetail]
ProfileDetailListTA = TypeAdapter(ProfileDetailList)
