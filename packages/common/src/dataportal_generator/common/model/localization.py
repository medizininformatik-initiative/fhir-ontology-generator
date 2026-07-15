from typing import Optional, List

from pydantic import BaseModel


class Translation(BaseModel):
    language: str
    value: Optional[str]


class BulkTranslation(BaseModel):
    language: str
    value: List[Optional[str]] = []


class TranslationDisplayElement(BaseModel):
    original: str
    translations: List[Translation]


class BulkTranslationDisplayElement(BaseModel):
    original: List[str] = []
    translations: List[BulkTranslation] = []