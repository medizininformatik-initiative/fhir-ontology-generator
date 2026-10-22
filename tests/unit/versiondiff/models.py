from typing import Annotated, Literal

from pydantic import AliasChoices, Field

from versiondiff import Category, DiffModel, DiffRule, Identity, Unordered
from versiondiff.core.markers import DiffIgnore


class Circle(DiffModel):
    kind: Literal["circle"] = "circle"
    radius: float


class Square(DiffModel):
    kind: Literal["square"] = "square"
    side: float


class Item(DiffModel):
    id: Annotated[str, Identity()]
    name: str
    value: float = Field(validation_alias=AliasChoices("value", "data"))  # was "cost"
    tags: Annotated[list[str], Unordered()] = Field(default_factory=list)
    note: str | None = None


class Report(DiffModel):
    generated_at: Annotated[str, DiffIgnore()]
    title: Annotated[str, DiffRule(on_change=Category.TRANSPARENT)]
    items: list[Item] = Field(default_factory=list)
    shape: Annotated[Circle | Square, Field(discriminator="kind")]
    labels: dict[str, int] = Field(default_factory=dict)
