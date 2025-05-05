from __future__ import annotations

import abc
from typing import Optional, List, Literal

from pydantic import BaseModel, ConfigDict

from cohort_selection_ontology.model.ui_data import TranslationDisplayElement, BulkTranslationDisplayElement
from common.util.fhir.enums import FhirDataType, FhirSearchType, FhirComplexDataType


class Filter(BaseModel):
    type: FhirSearchType
    name: str
    ui_type: Literal["code", "timeRestriction"]
    valueSetUrls: Optional[List[str]] = None


class Detail(BaseModel, abc.ABC):
    display: Optional[TranslationDisplayElement] = None
    description: Optional[TranslationDisplayElement] = None
    module: Optional[TranslationDisplayElement] = None


class ProfileReference(BaseModel):
    url: str
    display: TranslationDisplayElement
    fields: BulkTranslationDisplayElement


class FieldDetail(Detail):
    id: str
    type: Optional[FhirDataType] = None
    recommended: bool = False
    required: bool = False
    children: List[FieldDetail] = []

    model_config = ConfigDict(use_enum_values=True)


class ReferenceDetail(FieldDetail):
    type: FhirDataType = FhirComplexDataType.REFERENCE
    referencedProfiles: List[ProfileReference] = []


class ProfileDetail(Detail):
    url: str
    filters: List[Filter] = []
    fields: List[FieldDetail] = []
    references: List[ReferenceDetail] = []
