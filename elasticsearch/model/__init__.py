from pydantic import BaseModel, Field


class IndexDocDisplay(BaseModel):
    original: str
    de: str = Field(default="")
    en: str = Field(default="")