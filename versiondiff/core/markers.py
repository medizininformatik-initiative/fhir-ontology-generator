"""`Annotated` metadata that controls how fields are diffed."""

from collections.abc import Callable
from dataclasses import dataclass

from pydantic import JsonValue

from versiondiff.core.types import Category, Change


@dataclass(frozen=True)
class Identity:
    """Marks a field as (part of) the model's identity, which is used to match list items."""


@dataclass(frozen=True)
class Unordered:
    """On a list field: a reorder by itself is TRANSPARENT."""


@dataclass(frozen=True)
class DiffRule:
    """Per-field overrides of the default classification.

    on_add / on_remove apply to the field itself and to items or keys of a
    collection field. on_change applies to scalar value changes.
    """

    on_change: Category | None = None
    on_add: Category | None = None
    on_remove: Category | None = None
    ignore: bool = False
    compare: Callable[[JsonValue, JsonValue, str], list[Change]] | None = None

def DiffIgnore() -> DiffRule:
    """Marks a field as ignored for diffing purposes."""
    return DiffRule(ignore=True)