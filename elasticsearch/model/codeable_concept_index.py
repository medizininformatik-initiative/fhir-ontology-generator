from typing import Annotated

from pydantic import Field

from cohort_selection_ontology.model.ui_data import TermCode
from elasticsearch.model import IndexDocDisplay
from versiondiff.core.markers import DiffIgnore, Identity
from versiondiff.core.models import DiffModel


class CodeableConceptIndexDoc(DiffModel):
    hash: Annotated[str, Identity()]
    termcode: TermCode
    value_sets: list[str] = Field(min_length=1)
    display: Annotated[IndexDocDisplay, DiffIgnore()]
