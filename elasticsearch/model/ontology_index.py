from typing import Annotated

from pydantic import Field

from cohort_selection_ontology.model.ui_data import RelationalTermcode, TermCode
from common.model.pydantic.functions import is_empty
from elasticsearch.model import IndexDocDisplay
from versiondiff.core.markers import DiffIgnore, Identity
from versiondiff.core.models import DiffModel


class OntologyIndexDoc(DiffModel):
    hash: Annotated[str, Identity()]
    name: str
    availability: Annotated[int, DiffIgnore()]
    terminology: str
    termcode: str
    selectable: bool
    context: TermCode
    termcodes: list[TermCode] = Field(default_factory=list, exclude_if=is_empty)
    criteria_sets: list[str] = Field(default_factory=list, exclude_if=is_empty)
    display: Annotated[IndexDocDisplay, DiffIgnore()]
    parents: list[RelationalTermcode] = Field(default_factory=list, exclude_if=is_empty)
    children: list[RelationalTermcode] = Field(default_factory=list, exclude_if=is_empty)
    # Undo diff irrelevant if the field ever becomes relevant
    related_terms: Annotated[list, DiffIgnore()] = Field(default_factory=list, exclude_if=is_empty)
    kds_module: str

