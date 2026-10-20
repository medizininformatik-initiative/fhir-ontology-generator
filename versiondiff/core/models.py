from typing import Any

from pydantic import BaseModel

from .engine import diff_model
from versiondiff.core.types import Change


class DiffModel(BaseModel):
    """Base for models whose instances can be compared across versions.

    The default `diff` walks the current version's fields. Override it for
    models that need custom comparison; `prev` is raw JSON from the old
    version and is never validated.
    """

    @classmethod
    def diff(cls, prev: dict[str, Any], curr: dict[str, Any], path: str) -> list[Change]:
        return diff_model(cls, prev, curr, path)
