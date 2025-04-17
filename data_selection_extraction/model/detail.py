from __future__ import annotations

import abc
from typing import Optional, List, Literal

from pydantic import BaseModel

from cohort_selection_ontology.model.ui_data import TranslationElementDisplay
from common.util.fhir.enums import FhirDataType, FhirSearchType


class Filter(BaseModel):
    type: FhirSearchType
    name: str
    ui_type: Literal["code", "timeRestriction"]
    valueSetUrls: Optional[List[str]] = None


class Detail(BaseModel, abc.ABC):
    display: Optional[TranslationElementDisplay] = None
    description: Optional[TranslationElementDisplay] = None


class FieldDetail(Detail):
    id: str
    referencedProfiles: List[str] = []
    type: Optional[FhirDataType] = None
    recommended: bool = False
    required: bool = False
    children: Optional[List[FieldDetail]] = None


class ProfileDetail(Detail):
    url: str
    filters: List[Filter] = []
    fields: List[FieldDetail] = []
