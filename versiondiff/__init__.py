"""Compare JSON documents produced by different versions of pydantic models."""

import json
from typing import Any

from pydantic import BaseModel

from versiondiff.core.engine import diff_value
from versiondiff.core.markers import DiffRule, Identity, Unordered
from versiondiff.core.models import DiffModel
from versiondiff.core.types import Category, Change, DiffReport, Kind

__all__ = ["Category", "Change", "DiffModel", "DiffReport", "DiffRule", "Identity", "Kind", "Unordered", "compare"]


def compare(prev: str | bytes | Any, curr: BaseModel | list[BaseModel], *, model: type[BaseModel] | type[list[BaseModel]] | None = None) -> DiffReport:
    """Diff `prev` (old-version JSON text or parsed JSON) against the current instance `curr`."""
    prev_json = json.loads(prev) if isinstance(prev, (str, bytes)) else prev
    curr_json = [e.model_dump(mode="json", by_alias=True) for e in curr] if isinstance(curr, list) else curr.model_dump(mode="json", by_alias=True)
    return DiffReport(changes=diff_value(model or type(curr), prev_json, curr_json, ""))
