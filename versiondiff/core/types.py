"""Report types: change categories, change kinds and the diff report itself."""

from enum import Enum, StrEnum
from functools import total_ordering

from pydantic import BaseModel, JsonValue, computed_field


@total_ordering
class Category(Enum):
    """Impact of a change on consumers, ordered by severity."""

    TRANSPARENT = "transparent"
    INFORMATIONAL = "informational"
    BREAKING = "breaking"

    @property
    def rank(self) -> int:
        return list(type(self)).index(self)

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Category):
            return NotImplemented
        return self.rank < other.rank


class Kind(StrEnum):
    ADDED = "added"
    REMOVED = "removed"
    CHANGED = "changed"
    TYPE_CHANGED = "type_changed"
    RENAMED = "renamed"
    MOVED = "moved"


class Change(BaseModel):
    """A single difference between two documents.

    `path` is a JSON Pointer (RFC 6901). Inside lists matched by identity, the
    token is the identity instead of an index (e.g. `/items/id=a1/price`), so
    paths stay stable across versions.
    """

    path: str
    kind: Kind
    category: Category
    prev: JsonValue = None
    curr: JsonValue = None
    note: str | None = None


class DiffReport(BaseModel):
    changes: list[Change] = []

    @computed_field
    @property
    def severity(self) -> Category | None:
        """The most severe category of any change, or None if nothing changed."""
        return max((c.category for c in self.changes), default=None)

    @computed_field
    @property
    def counts(self) -> dict[Category, int]:
        return {cat: sum(c.category is cat for c in self.changes) for cat in Category}
