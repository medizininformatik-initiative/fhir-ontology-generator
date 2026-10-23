"""Generic diff engine over JSON values, guided by the current version's type annotations.

Both sides are JSON values (prev is raw JSON from the old version, curr is the
current model dumped with `mode="json", by_alias=True`). Annotations only steer
matching and classification; they never validate prev.
"""

import functools
import json
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from types import NoneType, UnionType
from typing import TYPE_CHECKING, Annotated, Any, Literal, Union, get_args, get_origin

from pydantic import AliasChoices, AliasPath, BaseModel, TypeAdapter, ValidationError
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined

from versiondiff.core.types import Category, Change, Kind

from .markers import DiffRule, Identity, Unordered

if TYPE_CHECKING:
    from pydantic import JsonValue


class _Missing:
    __slots__ = ()

    def __repr__(self) -> str:
        return "MISSING"


MISSING: Any = _Missing()
"""Marks a key/item that is absent on one side (unlike an explicit null)."""

_NO_RULE = DiffRule()
_LIST_ORIGINS = (list, tuple, set, frozenset, Sequence)
_UNORDERED_ORIGINS = (set, frozenset)


# --- helpers -----------------------------------------------------------------


def join(path: str, token: object) -> str:
    """Append a JSON Pointer token, escaping `~` and `/`."""
    return f"{path}/{str(token).replace('~', '~0').replace('/', '~1')}"


def json_type(value: object) -> str:
    """
    Returns the JSON data type of the passed value.
    """
    match value:
        case None:
            return "null"
        case bool():
            return "boolean"
        case int() | float():
            return "number"
        case str():
            return "string"
        case list():
            return "array"
        case dict():
            return "object"
    raise TypeError(f"not a JSON value: {value!r}")


def _json_kind(tp: Any) -> str | None:
    """
    Returns the JSON data type of the given type (its representation in JSON).
    """
    tp, _ = _unwrap(tp)
    origin = get_origin(tp) or tp
    if origin is NoneType:
        return "null"
    if origin is bool:
        return "boolean"
    if origin in (int, float):
        return "number"
    if origin is str:
        return "string"
    if origin in _LIST_ORIGINS:
        return "array"
    if origin in (dict, Mapping) or _is_model(tp):
        return "object"
    return None


def _canon(value: object) -> str:
    """Return a canonical JSON string representation of the value."""
    return json.dumps(value, sort_keys=True)


def _unwrap(tp: Any, meta: Iterable[Any] = ()) -> tuple[Any, list[Any]]:
    """Strip (nested) `Annotated`, collecting its metadata."""
    meta = list(meta)
    while get_origin(tp) is Annotated:
        tp, *extra = get_args(tp)
        meta.extend(extra)
    return tp, meta


def _find[T](meta: Iterable[Any], kind: type[T]) -> T | None:
    """
    Given a type annotation and some marker type, searches for the marker in the annotation. E.g. for type annotation
    ``_find(Annotation[str, ..., Identity, ...], Identity())`` returns the instance of the marker (``Identity()``).
    """
    return next((m for m in meta if isinstance(m, kind)), None)


def _is_model(tp: Any) -> bool:
    """
    Returns ``True`` if the given type is a subclass of ``pydantic.BaseModel`` (ignoring any typing wrappers like
    ``Annotated``).
    """
    return get_origin(tp) is None and isinstance(tp, type) and issubclass(tp, BaseModel)


def _name(tp: Any) -> str:
    """Returns the name of the given type (``__name__`` if present else ``repr(tp)``)."""
    return getattr(tp, "__name__", repr(tp))


def field_keys(name: str, field: FieldInfo) -> tuple[str, list[str]]:
    """The field's JSON key in the current version, plus older names it may carry in prev."""
    key = field.serialization_alias or field.alias or name
    alts: list[str] = []
    va = field.validation_alias
    for choice in va.choices if isinstance(va, AliasChoices) else [va]:
        if isinstance(choice, str):
            alts.append(choice)
        elif (
            isinstance(choice, AliasPath)
            and len(choice.path) == 1
            and isinstance(choice.path[0], str)
        ):
            alts.append(choice.path[0])
    alts += [a for a in (field.alias, name) if a]
    return key, [a for a in dict.fromkeys(alts) if a != key]


def _lookup(
    data: Mapping[str, Any], field_name: str, field: FieldInfo
) -> tuple[str | None, Any]:
    """
    Given a python dict (JSON object), look up the value for the given model field (identified by its name and field
    metadata). Returns the key of the field (name or alias) in the JSON object and the associated value. If the field
    is neither present in the JSON object nor has a default value, returns ``(None, MISSING)``.

    :param data: JSON object
    :param field_name: Name of the model field
    :param field: ``FieldInfo`` object holding the model field's metadata
    :return: tuple of the fields key and value
    """
    key, alts = field_keys(field_name, field)
    for k in (key, *alts):
        if k in data:
            return k, data[k]
    if field.default is not PydanticUndefined:
        return field_name, field.default
    elif (field_fac := field.default_factory) is not None:
        return field_name, field_fac()
    else:
        return None, MISSING


def _added(
    path: str,
    value: "JsonValue",
    rule: DiffRule,
    default: Category = Category.INFORMATIONAL,
    note: str | None = None,
) -> Change:
    return Change(
        path=path,
        kind=Kind.ADDED,
        category=rule.on_add or default,
        curr=value,
        note=note,
    )


def _removed(
    path: str, value: "JsonValue", rule: DiffRule, note: str | None = None
) -> Change:
    return Change(
        path=path,
        kind=Kind.REMOVED,
        category=rule.on_remove or Category.BREAKING,
        prev=value,
        note=note,
    )


# --- dispatcher --------------------------------------------------------------


def diff_value(
    tp: Any, prev: Any, curr: Any, path: str, meta: Iterable[Any] = ()
) -> list[Change]:
    """Diff two JSON values at `path`, using annotation `tp` (and its metadata) for the rules."""
    tp, meta = _unwrap(tp, meta)
    rule = _find(meta, DiffRule) or _NO_RULE
    if rule.ignore or (prev is MISSING and curr is MISSING):
        return []
    if prev is MISSING:
        return [_added(path, curr, rule)]
    if curr is MISSING:
        return [_removed(path, prev, rule)]
    if rule.compare:
        return list(rule.compare(prev, curr, path))

    origin = get_origin(tp)
    if origin is Union or origin is UnionType:
        return _diff_union(tp, prev, curr, path, meta, rule)

    pt, ct = json_type(prev), json_type(curr)
    if pt != ct:
        return [
            Change(
                path=path,
                kind=Kind.TYPE_CHANGED,
                category=Category.BREAKING,
                prev=prev,
                curr=curr,
                note=f"{pt} -> {ct}",
            )
        ]
    if _is_model(tp) and pt == "object":
        from .models import DiffModel  # deferred: model imports this module

        return (
            tp.diff(prev, curr, path)
            if issubclass(tp, DiffModel)
            else diff_model(tp, prev, curr, path)
        )
    if pt == "array":
        unordered = _find(meta, Unordered) is not None or origin in _UNORDERED_ORIGINS
        return _diff_list(_item_type(tp), prev, curr, path, rule, unordered)
    if pt == "object":
        return _diff_dict(_value_type(tp), prev, curr, path, rule)
    if prev == curr:
        return []
    return [
        Change(
            path=path,
            kind=Kind.CHANGED,
            category=rule.on_change or Category.INFORMATIONAL,
            prev=prev,
            curr=curr,
        )
    ]


def _item_type(tp: Any) -> Any:
    """Given a collection type, return the type of its items."""
    origin, args = get_origin(tp), get_args(tp)
    if origin is tuple:
        # tuple[T, ...] -> T where '...' represents the ellipsis
        return args[0] if len(args) == 2 and args[1] is Ellipsis else Any
    if origin in _LIST_ORIGINS and args:
        return args[0]
    return Any


def _value_type(tp: Any) -> Any:
    """Given a mapping type, return the type of its values."""
    args = get_args(tp)
    return args[1] if get_origin(tp) in (dict, Mapping) and len(args) == 2 else Any


# --- models ------------------------------------------------------------------


def diff_model(
    cls: type[BaseModel], prev: dict[str, Any], curr: dict[str, Any], path: str
) -> list[Change]:
    """Default model diff: fields of the current version drive the comparison."""
    changes: list[Change] = []
    consumed: set[str] = set()  # prev keys mapped to a field
    known: set[str] = set()  # curr keys produced by a field

    for name, field in cls.model_fields.items():
        if field.exclude:
            continue
        key, _ = field_keys(name, field)
        known.add(key)
        rule = _find(field.metadata, DiffRule) or _NO_RULE
        prev_key, p = _lookup(prev, name, field)
        if prev_key is not None:
            consumed.add(prev_key)
        if rule.ignore:
            continue
        c = curr.get(key, MISSING)
        fpath = join(path, key)
        if p is MISSING and c is not MISSING:
            default = (
                Category.BREAKING if field.is_required() else Category.INFORMATIONAL
            )
            changes.append(_added(fpath, c, rule, default))
            continue
        if prev_key is not None and prev_key != key:
            changes.append(
                Change(
                    path=fpath,
                    kind=Kind.RENAMED,
                    category=Category.INFORMATIONAL,
                    prev=prev_key,
                    curr=key,
                )
            )
        changes += diff_value(field.annotation, p, c, fpath, field.metadata)

    for name, cfield in cls.model_computed_fields.items():
        key = cfield.alias or name
        known.add(key)
        if key in prev:
            consumed.add(key)
        changes += diff_value(
            cfield.return_type,
            prev.get(key, MISSING),
            curr.get(key, MISSING),
            join(path, key),
        )

    # Keys no current field accounts for: dropped fields, or extras (extra="allow").
    for key in [k for k in prev if k not in consumed]:
        changes += diff_value(Any, prev[key], curr.get(key, MISSING), join(path, key))
    for key in [k for k in curr if k not in known and k not in prev]:
        changes.append(_added(join(path, key), curr[key], _NO_RULE))
    return changes


@functools.cache
def identity_fields(cls: type[BaseModel]) -> tuple[tuple[str, FieldInfo], ...]:
    """(key, keys to try in prev) for each field marked `Identity()`."""
    out = []
    for name, field in cls.model_fields.items():
        if _find(field.metadata, Identity):
            out.append((name, field))
    return tuple(out)


def _identity(
    fields: tuple[tuple[str, FieldInfo], ...], item: Any
) -> tuple[Any, ...] | None:
    if not isinstance(item, dict):
        return None
    values = []
    for field_name, field in fields:
        _, v = _lookup(item, field_name, field)
        if v is MISSING:
            return None
        values.append(
            v if isinstance(v, (str, int, float, bool, NoneType)) else _canon(v)
        )
    return tuple(values)


# --- collections -------------------------------------------------------------


def _diff_list(
    item_tp: Any,
    prev: list[Any],
    curr: list[Any],
    path: str,
    rule: DiffRule,
    unordered: bool,
) -> list[Change]:
    inner, _ = _unwrap(item_tp)
    fields = identity_fields(inner) if _is_model(inner) else ()
    if (
        fields
        and (keyed := _diff_keyed(fields, item_tp, prev, curr, path, rule, unordered))
        is not None
    ):
        return keyed
    if all(json_type(v) not in ("array", "object") for v in (*prev, *curr)):
        return _diff_multiset(prev, curr, path, rule, unordered)
    return _diff_positional(item_tp, prev, curr, path, rule)


def _moved(
    path: str, prev_order: list[Any], curr_order: list[Any], unordered: bool
) -> list[Change]:
    if prev_order == curr_order:
        return []
    category = Category.TRANSPARENT if unordered else Category.INFORMATIONAL
    return [
        Change(
            path=path,
            kind=Kind.MOVED,
            category=category,
            prev=prev_order,
            curr=curr_order,
        )
    ]


def _diff_keyed(
    fields, item_tp, prev, curr, path, rule, unordered
) -> list[Change] | None:
    """Match items by identity. Returns None (fall back to positional) on missing or duplicate keys."""

    def index(items: list[Any]) -> dict[tuple[Any, ...], Any] | None:
        out: dict[tuple[Any, ...], Any] = {}
        for item in items:
            ident = _identity(fields, item)
            if ident is None or ident in out:
                return None
            out[ident] = item
        return out

    pmap, cmap = index(prev), index(curr)
    if pmap is None or cmap is None:
        return None

    def token(ident: tuple[Any, ...]) -> str:
        return ",".join(f"{key}={v}" for (key, _), v in zip(fields, ident))

    changes: list[Change] = []
    for ident, p in pmap.items():
        sub = join(path, token(ident))
        if ident in cmap:
            changes += diff_value(item_tp, p, cmap[ident], sub)
        else:
            changes.append(_removed(sub, p, rule))
    changes += [
        _added(join(path, token(i)), c, rule) for i, c in cmap.items() if i not in pmap
    ]
    changes += _moved(
        path,
        [token(i) for i in pmap if i in cmap],
        [token(i) for i in cmap if i in pmap],
        unordered,
    )
    return changes


def _diff_multiset(
    prev: list[Any], curr: list[Any], path: str, rule: DiffRule, unordered: bool
) -> list[Change]:
    """Scalar lists: compare as multisets, then report a reorder of what remains."""
    pc, cc = Counter(map(_canon, prev)), Counter(map(_canon, curr))
    gone, new = pc - cc, cc - pc
    changes: list[Change] = []

    def split(items: list[Any], extra: Counter[str], make) -> list[Any]:
        kept = []
        for i, v in enumerate(items):
            if extra[_canon(v)] > 0:
                extra[_canon(v)] -= 1
                changes.append(make(join(path, i), v, rule))
            else:
                kept.append(v)
        return kept

    kept_prev = split(prev, gone, _removed)
    kept_curr = split(curr, new, _added)
    return changes + _moved(path, kept_prev, kept_curr, unordered)


def _diff_positional(
    item_tp: Any, prev: list[Any], curr: list[Any], path: str, rule: DiffRule
) -> list[Change]:
    changes: list[Change] = []
    for i in range(max(len(prev), len(curr))):
        p = prev[i] if i < len(prev) else MISSING
        c = curr[i] if i < len(curr) else MISSING
        sub = join(path, i)
        if p is MISSING:
            changes.append(_added(sub, c, rule))
        elif c is MISSING:
            changes.append(_removed(sub, p, rule))
        else:
            changes += diff_value(item_tp, p, c, sub)
    return changes


def _diff_dict(
    value_tp: Any, prev: dict[str, Any], curr: dict[str, Any], path: str, rule: DiffRule
) -> list[Change]:
    changes: list[Change] = []
    for key in [*prev, *(k for k in curr if k not in prev)]:
        p, c = prev.get(key, MISSING), curr.get(key, MISSING)
        sub = join(path, key)
        if p is MISSING:
            changes.append(_added(sub, c, rule))
        elif c is MISSING:
            changes.append(_removed(sub, p, rule))
        else:
            changes += diff_value(value_tp, p, c, sub)
    return changes


# --- unions ------------------------------------------------------------------


def _diff_union(
    tp: Any, prev: Any, curr: Any, path: str, meta: list[Any], rule: DiffRule
) -> list[Change]:
    if prev is None and curr is None:
        return []
    if prev is None:
        return [_added(path, curr, rule, note="null -> value")]
    if curr is None:
        return [_removed(path, prev, rule, note="value -> null")]

    variants = [a for a in get_args(tp) if a is not NoneType]
    pv, cv = _select_variant(variants, prev), _select_variant(variants, curr)
    if cv is None:
        cv = Any
    if pv is not None and pv != cv:
        note = f"{_name(_unwrap(pv)[0])} -> {_name(_unwrap(cv)[0])}"
        return [
            Change(
                path=path,
                kind=Kind.TYPE_CHANGED,
                category=Category.BREAKING,
                prev=prev,
                curr=curr,
                note=note,
            )
        ]
    return diff_value(cv, prev, curr, path, meta)


def _select_variant(variants: list[Any], value: Any) -> Any | None:
    """Pick the union member a JSON value belongs to: tag, then strict validation, then JSON type."""
    if isinstance(value, dict):
        for v in variants:
            inner, _ = _unwrap(v)
            if _is_model(inner) and _tag_matches(inner, value):
                return v
    for v in variants:
        if _validates(v, value):
            return v
    for v in variants:
        if _json_kind(v) == json_type(value):
            return v
    return None


def _tag_matches(cls: type[BaseModel], data: dict[str, Any]) -> bool:
    for name, field in cls.model_fields.items():
        ann, _ = _unwrap(field.annotation)
        if get_origin(ann) is Literal:
            _, v = _lookup(data, name, field)
            if v is not MISSING and v in get_args(ann):
                return True
    return False


@functools.lru_cache(maxsize=256)
def _cached_adapter(tp: Any) -> TypeAdapter[Any]:
    return TypeAdapter(tp)


def _validates(tp: Any, value: Any) -> bool:
    try:
        adapter = _cached_adapter(tp)
    except TypeError:  # unhashable annotation metadata
        adapter = TypeAdapter(tp)
    try:
        adapter.validate_json(json.dumps(value), strict=True)
    except ValidationError:
        return False
    return True
