from typing import List

from pydantic import BaseModel, Field


class ElementPath(BaseModel):
    tokens: List[str] = Field(default=["$this"], min_length=1)

