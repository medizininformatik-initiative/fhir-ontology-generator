from pydantic import BaseModel, Field


class Translation(BaseModel):
    language: str
    value: str | None = Field(default=None)


class BulkTranslation(BaseModel):
    language: str
    value: list[str | None] = Field(default_factory=list)


class TranslationDisplayElement(BaseModel):
    original: str
    translations: list[Translation] = Field(default_factory=list)


class BulkTranslationDisplayElement(BaseModel):
    original: list[str] = Field(default_factory=list, min_length=1)
    translations: list[BulkTranslation] = Field(default_factory=list)