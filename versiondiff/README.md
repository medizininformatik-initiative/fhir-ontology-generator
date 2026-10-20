# versiondiff

Compare JSON documents produced by generator runs of different versions of this repository, and classify every 
difference by its impact on dataportal users.

The current version has to be a valid **pydantic v2** model instance. The previous version is passed as **raw JSON** 
and is never validated, so the diff still works even after the data model has changed. Type annotations on the current 
models only steer how values are matched and classified.

## Change categories

| Category        | Meaning                                                                 |
|-----------------|-------------------------------------------------------------------------|
| `TRANSPARENT`   | Affects consuming software in a way users don't notice.                 |
| `INFORMATIONAL` | Noticeable to users, but compatible with previous versions (e.g. new optional content). |
| `BREAKING`      | Not compatible with previous versions (e.g. removed content, new required content). |

Categories are ordered by severity (`TRANSPARENT < INFORMATIONAL < BREAKING`).

## Quick start

```python
from typing import Annotated

from pydantic import AliasChoices, Field

from versiondiff import Category, DiffModel, DiffRule, Identity, Unordered, compare


class Item(DiffModel):
    id: Annotated[str, Identity()]                                         # match list items by id
    name: str
    price: float = Field(validation_alias=AliasChoices("price", "cost"))   # was "cost"
    tags: Annotated[list[str], Unordered()] = []                           # order doesn't matter


class Catalog(DiffModel):
    generated_at: Annotated[str, DiffRule(ignore=True)]                    # never compared
    title: Annotated[str, DiffRule(on_change=Category.TRANSPARENT)]
    items: list[Item] = []


prev = """{"generated_at": "2026-01-01", "title": "Q2",
  "items": [{"id": "a", "name": "Apple", "cost": 1.0, "tags": ["red", "fruit"]},
            {"id": "z", "name": "Old", "cost": 9.0}]}"""

curr = Catalog(
    generated_at="2026-10-01",
    title="Q3",
    items=[
        Item(id="a", name="Apple", price=1.2, tags=["fruit", "red"]),
        Item(id="b", name="Banana", price=0.5),
    ],
)

report = compare(prev, curr)
print(report.model_dump_json(indent=2, exclude_none=True))
```

Output (abridged):

| path                | kind      | category        |
|---------------------|-----------|-----------------|
| `/title`            | `changed` | `transparent`   |
| `/items/id=a/price` | `renamed` | `informational` |
| `/items/id=a/price` | `changed` | `informational` |
| `/items/id=a/tags`  | `moved`   | `transparent`   |
| `/items/id=z`       | `removed` | `breaking`      |
| `/items/id=b`       | `added`   | `informational` |

```json
"severity": "breaking",
"counts": {"transparent": 2, "informational": 3, "breaking": 1}
```

### Top-level lists

When the current document is a list of models, pass the annotation explicitly:

```python
report = compare(prev_bytes, profiles, model=list[ProfileDetail])
```

## API

### `compare(prev, curr, *, model=None) -> DiffReport`

- `prev`: previous version as JSON text (`str`/`bytes`) or already-parsed JSON.
- `curr`: a model instance, or a list of model instances.
- `model`: the annotation to diff against. Defaults to `type(curr)`; required for lists.

### `DiffReport`

- `changes: list[Change]`
- `severity: Category | None`: the most severe category, or `None` if nothing changed.
- `counts: dict[Category, int]`: number of changes per category.

Both computed fields are included when the report is serialized.

### `Change`

| Field      | Description                                                         |
|------------|---------------------------------------------------------------------|
| `path`     | JSON Pointer (RFC 6901) to the change. See [Paths](#paths).         |
| `kind`     | `added`, `removed`, `changed`, `type_changed`, `renamed` or `moved`. |
| `category` | A `Category`.                                                       |
| `prev`     | Old value (old key for `renamed`, old order for `moved`).           |
| `curr`     | New value (new key for `renamed`, new order for `moved`).           |
| `note`     | Extra detail, e.g. `"number -> string"` or `"Circle -> Square"`.    |

## Default classification

| Situation                                       | Kind           | Category        |
|-------------------------------------------------|----------------|-----------------|
| Field / key / item removed                      | `removed`      | `BREAKING`      |
| Required field added                            | `added`        | `BREAKING`      |
| Optional field, dict key or list item added     | `added`        | `INFORMATIONAL` |
| Scalar value changed                            | `changed`      | `INFORMATIONAL` |
| JSON type changed (e.g. number → string)        | `type_changed` | `BREAKING`      |
| Union variant changed (e.g. `Circle` → `Square`) | `type_changed` | `BREAKING`      |
| Optional value `null` → value                   | `added`        | `INFORMATIONAL` |
| Optional value value → `null`                   | `removed`      | `BREAKING`      |
| Field read from an old name (alias)             | `renamed`      | `INFORMATIONAL` |
| List reordered                                  | `moved`        | `INFORMATIONAL` |
| `Unordered` list or `set`/`frozenset` reordered | `moved`        | `TRANSPARENT`   |

Fields with `exclude=True` are skipped. Computed fields are compared like regular fields. Keys in `prev` that no 
current field accounts for are reported as removed.

## Markers

Markers go into `Annotated[...]` metadata on model fields.

### `Identity()`

Marks a field as (part of) the model's identity. Lists of that model are matched item by item via identity instead of 
position, so inserting an item in the middle yields a single `added` change rather than a cascade of modifications. 
Several `Identity()` fields form a composite key.

If any item in a list lacks an identity value, or two items share one, that list falls back to positional comparison.

### `Unordered()`

On a list field: a pure reorder is `TRANSPARENT` instead of `INFORMATIONAL`.

### `DiffRule(...)`

Per-field overrides of the defaults:

| Parameter   | Effect                                                                     |
|-------------|----------------------------------------------------------------------------|
| `on_change` | Category for scalar value changes.                                         |
| `on_add`    | Category when the field, or an item/key of a collection field, is added.   |
| `on_remove` | Category when the field, or an item/key of a collection field, is removed. |
| `ignore`    | Skip the field entirely.                                                   |
| `compare`   | `(prev, curr, path) -> list[Change]` replacing the built-in comparison.    |

```python
def tolerant(prev, curr, path):
    if abs(prev - curr) < 0.01:
        return []
    return [Change(path=path, kind=Kind.CHANGED, category=Category.BREAKING, prev=prev, curr=curr)]


class Point(DiffModel):
    x: Annotated[float, DiffRule(compare=tolerant)]
```

There are utility functions for some common cases such as `DiffIgnore()` (ignore field for diffing).

## Renamed fields

Old field names are taken from the field's `validation_alias` (a string, `AliasChoices`, or single-key `AliasPath`) and 
`alias`. If `prev` carries the value under one of those names, a `renamed` change is reported and the values are then 
compared as usual. The current key is the field's serialization alias, alias or name, in that order.

## Custom model comparison

Subclass `DiffModel` and override the `diff` classmethod. `prev` and `curr` are JSON objects, and `path` is the model's 
JSON Pointer:

```python
class Point(DiffModel):
    x: float

    @classmethod
    def diff(cls, prev, curr, path):
        changes = super().diff(prev, curr, path)
        return [c.model_copy(update={"note": "custom"}) for c in changes]
```

Nested plain `BaseModel` classes also work. They use the default field-by-field comparison.

## Paths

Paths are JSON Pointers with `~` and `/` escaped as `~0` and `~1`. Inside lists matched by `Identity()`, the token is 
the identity (`key=value`, joined with `,` for composite keys) instead of an index, so paths stay stable across 
versions:

```
/items/id=a/price
/url=https:~1~1example.org~1Profile/filters/name=onset-date
```

## Union handling

To decide which variant of a union a JSON value belongs to, the engine checks, in order:

1. a `Literal` tag field on a model variant (discriminated unions),
2. strict validation against each variant,
3. the value's JSON type.

If both sides resolve to the same variant, the comparison recurses into it. Otherwise a `type_changed` change is 
reported.

## Module layout

| File         | Contents                                                       |
|--------------|----------------------------------------------------------------|
| `__init__.py` | `compare()` and the public exports.                           |
| `core/types.py`   | `Category`, `Kind`, `Change`, `DiffReport`.                    |
| `core/markers.py` | `Identity`, `Unordered`, `DiffRule`.                           |
| `model.py`   | `DiffModel` base class.                                        |
| `core/engine.py`  | The annotation-guided JSON diff engine.                        |
