from uuid import uuid4

from pydantic import BaseModel, Field, TypeAdapter, computed_field

from cohort_selection_ontology.model.ui_data import (
    TranslationDisplayElement,
)


class ProfileTreeNode(BaseModel):
    id: str = str(uuid4())
    name: str
    display: TranslationDisplayElement | None = Field(default=None)
    description: TranslationDisplayElement | None = Field(default=None)
    url: str | None = Field(default=None)
    module: TranslationDisplayElement | None = Field(default=None)
    selectable: bool = Field(default=False)
    fields: list[tuple[TranslationDisplayElement, TranslationDisplayElement | None]] = (
        Field(default_factory=list)
    )
    children: list["ProfileTreeNode"] = Field(default_factory=list)
    resource_type: str | None = Field(default=None)

    @computed_field
    @property
    def leaf(self) -> bool:
        return len(self.children) == 0


ProfileTreeTA = TypeAdapter(list[ProfileTreeNode])
