from typing import List
from uuid import uuid4

from pydantic import BaseModel, computed_field, Field, TypeAdapter
from typing_extensions import Optional, Self

from cohort_selection_ontology.model.ui_data import (
    TranslationDisplayElement,
)


class ProfileTreeNode(BaseModel):
    id: str = str(uuid4())
    name: str
    display: Optional[TranslationDisplayElement] = None
    description: Optional[TranslationDisplayElement] = None
    url: Optional[str] = None
    module: Optional[TranslationDisplayElement] = None
    selectable: bool = False
    fields: list[tuple[TranslationDisplayElement, TranslationDisplayElement | None]] = Field(
        default_factory=list
    )
    children: List["ProfileTreeNode"] = []
    resource_type: Optional[str] = Field(default=None)

    @computed_field
    @property
    def leaf(self) -> bool:
        return len(self.children) == 0


ProfileTreeTA = TypeAdapter(list[ProfileTreeNode])
