import copy
import json
from typing import Annotated, Any

import pytest
from _pytest.mark import param
from pydantic import BaseModel, Field

from versiondiff import Category, Change, DiffModel, DiffRule, Kind, compare

from .models import Circle, Item, Report, Square


def make_report(**overrides: Any) -> Report:
    data: dict[str, Any] = {
        "generated_at": "2026-10-15T00:00:00Z",
        "title": "Q3",
        "items": [
            Item(id="a", name="A", value=1.0, tags=["a1", "a2"]),
            Item(id="b", name="B", value=0.5),
        ],
        "shape": Circle(radius=2),
        "labels": {"x": 1},
    }
    return Report(**(data | overrides))


@pytest.fixture
def curr() -> Report:
    return make_report()


@pytest.fixture
def prev(curr: Report) -> dict[str, Any]:
    return copy.deepcopy(curr.model_dump(mode="json", by_alias=True))


def only(report, **attrs) -> Change:
    assert len(report.changes) == 1, report.changes
    change = report.changes[0]
    for k, v in attrs.items():
        assert getattr(change, k) == v, (k, change)
    return change


def test_identical(prev, curr):
    report = compare(prev, curr)
    assert report.changes == []
    assert report.severity is None


def test_ignored_field(prev, curr):
    prev["generated_at"] = "1970-01-01"
    assert compare(prev, curr).changes == []


def test_added_optional_field(prev, curr):
    del prev["items"][0]["note"]
    assert compare(prev, curr).changes == []


def test_added_required_field(prev, curr):
    del prev["items"][0]["name"]
    only(
        compare(prev, curr),
        path="/items/id=a/name",
        kind=Kind.ADDED,
        category=Category.BREAKING,
    )


def test_removed_field(prev, curr):
    prev["legacy"] = 42
    only(
        compare(prev, curr),
        path="/legacy",
        kind=Kind.REMOVED,
        category=Category.BREAKING,
        prev=42,
    )


def test_scalar_change_default(prev, curr):
    prev["items"][1]["value"] = 0.4
    only(
        compare(prev, curr),
        path="/items/id=b/value",
        kind=Kind.CHANGED,
        category=Category.INFORMATIONAL,
        prev=0.4,
        curr=0.5,
    )


def test_scalar_change_with_rule(prev, curr):
    prev["title"] = "Q2"
    only(
        compare(prev, curr),
        path="/title",
        kind=Kind.CHANGED,
        category=Category.TRANSPARENT,
    )


def test_type_change(prev, curr):
    prev["items"][1]["value"] = "0.5"
    only(
        compare(prev, curr),
        path="/items/id=b/value",
        kind=Kind.TYPE_CHANGED,
        category=Category.BREAKING,
    )


def test_insert_mid_list_is_single_add(prev):
    curr = make_report(
        items=[
            Item(id="a", name="A", value=1.0, tags=["a1", "a2"]),
            Item(id="x", name="X", value=2.0),
            Item(id="b", name="B", value=0.5),
        ]
    )
    only(
        compare(prev, curr),
        path="/items/id=x",
        kind=Kind.ADDED,
        category=Category.INFORMATIONAL,
    )


def test_removed_item(prev, curr):
    prev["items"].append({"id": "z", "name": "Old", "value": 9})
    only(
        compare(prev, curr),
        path="/items/id=z",
        kind=Kind.REMOVED,
        category=Category.BREAKING,
    )


def test_reordered_keyed_list(prev, curr):
    prev["items"].reverse()
    only(
        compare(prev, curr),
        path="/items",
        kind=Kind.MOVED,
        category=Category.INFORMATIONAL,
        prev=["id=b", "id=a"],
    )


def test_reordered_unordered_list(prev, curr):
    prev["items"][0]["tags"] = ["a2", "a1"]
    only(
        compare(prev, curr),
        path="/items/id=a/tags",
        kind=Kind.MOVED,
        category=Category.TRANSPARENT,
    )


def test_scalar_list_add_and_remove(prev, curr):
    prev["items"][0]["tags"] = ["a1", "a3"]
    report = compare(prev, curr)
    assert {(c.path, c.kind, c.category) for c in report.changes} == {
        ("/items/id=a/tags/1", Kind.REMOVED, Category.BREAKING),
        ("/items/id=a/tags/1", Kind.ADDED, Category.INFORMATIONAL),
    }


def test_renamed_field(prev, curr):
    prev["items"][0]["data"] = prev["items"][0].pop("value")
    only(
        compare(prev, curr),
        path="/items/id=a/value",
        kind=Kind.RENAMED,
        category=Category.INFORMATIONAL,
        prev="data",
        curr="value",
    )


def test_renamed_field_with_value_change(prev, curr):
    prev["items"][0]["data"] = 3.0
    del prev["items"][0]["value"]
    kinds = [c.kind for c in compare(prev, curr).changes]
    assert kinds == [Kind.RENAMED, Kind.CHANGED]


def test_union_variant_switch(prev):
    curr = make_report(shape=Square(side=2))
    only(
        compare(prev, curr),
        path="/shape",
        kind=Kind.TYPE_CHANGED,
        category=Category.BREAKING,
        note="Circle -> Square",
    )


def test_union_same_variant_recurses(prev, curr):
    prev["shape"]["radius"] = 3
    only(compare(prev, curr), path="/shape/radius", kind=Kind.CHANGED)


def test_optional_null_transitions(prev, curr):
    curr.items[0].note = "ripe"
    prev["items"][0]["note"] = None
    only(
        compare(prev, curr),
        path="/items/id=a/note",
        kind=Kind.ADDED,
        note="null -> value",
    )

    prev["items"][0]["note"] = "old"
    curr.items[0].note = None
    only(
        compare(prev, curr),
        path="/items/id=a/note",
        kind=Kind.REMOVED,
        category=Category.BREAKING,
    )


def test_dict_keys(prev, curr):
    prev["labels"] = {"x": 2, "gone": 0}
    report = compare(prev, curr)
    assert {(c.path, c.kind) for c in report.changes} == {
        ("/labels/x", Kind.CHANGED),
        ("/labels/gone", Kind.REMOVED),
    }


def test_pointer_escaping(prev, curr):
    curr.labels["a/b~c"] = 1
    only(compare(prev, curr), path="/labels/a~1b~0c", kind=Kind.ADDED)


def test_duplicate_identity_falls_back_to_positional(prev, curr):
    prev["items"][1]["id"] = "a"
    report = compare(prev, curr)
    assert any(c.path == "/items/1/id" for c in report.changes)


def test_custom_compare_and_override():
    def tolerant(prev, curr, path):
        return (
            []
            if abs(prev - curr) < 0.01
            else [
                Change(
                    path=path,
                    kind=Kind.CHANGED,
                    category=Category.BREAKING,
                    prev=prev,
                    curr=curr,
                )
            ]
        )

    class Point(DiffModel):
        x: Annotated[float, DiffRule(compare=tolerant)]

        @classmethod
        def diff(cls, prev, curr, path):
            return [
                c.model_copy(update={"note": "custom"})
                for c in super().diff(prev, curr, path)
            ]

    assert compare({"x": 1.001}, Point(x=1.0)).changes == []
    only(
        compare({"x": 2}, Point(x=1.0)),
        kind=Kind.CHANGED,
        category=Category.BREAKING,
        note="custom",
    )


def test_prev_missing_field_with_default():
    class ModelWithDefault(DiffModel):
        id: int
        field: str = Field(default="abc")
    # Set by default
    prev = {"id": 123}
    curr = ModelWithDefault(id=123)
    report = compare(prev, curr, model=ModelWithDefault)
    assert len(report.changes) == 0
    # Set explicitly
    curr = ModelWithDefault(id=123, field="abc")
    report = compare(prev, curr, model=ModelWithDefault)
    assert len(report.changes) == 0
    # Set non-default value explicitly
    curr = ModelWithDefault(id=123, field="def")
    report = compare(prev, curr, model=ModelWithDefault)
    assert len(report.changes) == 1


def test_prev_missing_field_with_default_factory():
    class ModelWithDefaultFactory(DiffModel):
        id: int
        field: list[str] = Field(default_factory=list)
    # Set by factory
    prev = {"id": 123}
    curr = ModelWithDefaultFactory(id=123)
    report = compare(prev, curr, model=ModelWithDefaultFactory)
    assert len(report.changes) == 0
    # Set explicitly
    curr = ModelWithDefaultFactory(id=123, field=[])
    report = compare(prev, curr, model=ModelWithDefaultFactory)
    assert len(report.changes) == 0
    # Set non-default value explicitly
    curr = ModelWithDefaultFactory(id=123, field=["def"])
    report = compare(prev, curr, model=ModelWithDefaultFactory)
    assert len(report.changes) == 1


def test_plain_basemodel_nested():
    class Inner(BaseModel):
        v: int

    class Outer(DiffModel):
        inner: Inner

    only(
        compare({"inner": {"v": 1}}, Outer(inner=Inner(v=2))),
        path="/inner/v",
        kind=Kind.CHANGED,
    )


def test_report_json_roundtrip(prev, curr):
    prev["legacy"] = 1
    prev["title"] = "old"
    report = compare(json.dumps(prev), curr)
    data = json.loads(report.model_dump_json())
    assert data["severity"] == "breaking"
    assert data["counts"] == {"transparent": 1, "informational": 0, "breaking": 1}
    assert report.severity == max(c.category for c in report.changes)


def _make_model_list() -> list[Item]:
    return [
        Item(id="a", name="A", value=1.0, tags=["a1", "a2"]),
        Item(id="b", name="B", value=2.0, tags=["b1", "b2"]),
        Item(id="c", name="C", value=3.0, tags=["c1"]),
    ]


@pytest.fixture
def curr_list() -> list[Item]:
    return _make_model_list()


@pytest.fixture
def prev_list() -> list[dict]:
    return [
        model.model_dump(mode="json", by_alias=True) for model in _make_model_list()
    ]


@pytest.mark.parametrize(
    argnames=["prev_list", "curr_list", "expected"],
    argvalues=[
        param(
            [
                {"id": "a", "name": "A", "value": 1.0, "tags": ["a1", "a2"]},
                {"id": "b", "name": "B", "value": 2.0, "tags": ["b1", "b2"]},
                {"id": "c", "name": "C", "value": 3.0, "tags": ["c1"]},
            ],
            [
                Item(id="a", name="A", value=1.0, tags=["a1", "a2"]),
                Item(id="b", name="B", value=2.0, tags=["b1", "b2"]),
                Item(id="x", name="X", value=3.0, tags=["x1"]),
            ],
            [
                Change(
                    path="/id=c",
                    kind=Kind.REMOVED,
                    category=Category.BREAKING,
                    prev={"id": "c", "name": "C", "value": 3.0, "tags": ["c1"]},
                    curr=None,
                    note=None,
                ),
                Change(
                    path="/id=x",
                    kind=Kind.ADDED,
                    category=Category.INFORMATIONAL,
                    prev=None,
                    curr={
                        "id": "x",
                        "name": "X",
                        "value": 3.0,
                        "tags": ["x1"],
                        "note": None,
                    },
                    note=None,
                ),
            ],
            id="item-replaced",
        ),
        param(
            [
                {"id": "a", "name": "A", "value": 1.0, "tags": ["a1", "a2"]},
                {"id": "b", "name": "B", "value": 2.0, "tags": ["b1", "b2"]},
                {"id": "c", "name": "C", "value": 3.0, "tags": ["c1"]},
            ],
            [
                Item(id="a", name="A", value=1.0, tags=["a1", "a2"]),
                Item(id="b", name="B", value=2.0, tags=["b1", "b2"]),
            ],
            [
                Change(
                    path="/id=c",
                    kind=Kind.REMOVED,
                    category=Category.BREAKING,
                    prev={"id": "c", "name": "C", "value": 3.0, "tags": ["c1"]},
                    curr=None,
                    note=None,
                )
            ],
            id="item-removed",
        ),
        param(
            [
                {"id": "a", "name": "A", "value": 1.0, "tags": ["a1", "a2"]},
                {"id": "b", "name": "B", "value": 2.0, "tags": ["b1", "b2"]},
                {"id": "c", "name": "C", "value": 3.0, "tags": ["c1"]},
            ],
            [
                Item(id="a", name="A", value=1.0, tags=["a1", "a2"]),
                Item(id="b", name="B", value=2.0, tags=["b1", "b2"]),
                Item(id="c", name="C", value=3.0, tags=["c1"]),
                Item(id="d", name="D", value=0.5),
            ],
            [
                Change(
                    path="/id=d",
                    kind=Kind.ADDED,
                    category=Category.INFORMATIONAL,
                    prev=None,
                    curr={
                        "id": "d",
                        "name": "D",
                        "value": 0.5,
                        "tags": [],
                        "note": None,
                    },
                    note=None,
                )
            ],
            id="item-added",
        ),
    ],
)
def test_compare_model_list(prev_list, curr_list, expected):
    actual = compare(prev_list, curr_list, model=list[Item]).changes
    assert actual == expected
