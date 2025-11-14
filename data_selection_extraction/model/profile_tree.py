from typing import Mapping, List
from uuid import uuid4

from pydantic import BaseModel, computed_field
from typing_extensions import Optional, Self

from cohort_selection_ontology.model.ui_data import (
    BulkTranslationDisplayElement,
    BulkTranslation,
    TranslationDisplayElement,
)


class ProfileTreeNode(BaseModel):
    id: str = str(uuid4())
    name: str
    display: Optional[TranslationDisplayElement] = None
    url: Optional[str] = None
    module: Optional[str] = None
    selectable: bool = False
    fields: BulkTranslationDisplayElement = BulkTranslationDisplayElement()
    children: List[Self] = []

    @computed_field
    @property
    def leaf(self) -> bool:
        return len(self.children) == 0
