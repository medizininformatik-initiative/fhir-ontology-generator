from collections import Counter
from functools import reduce
from operator import and_
from typing import Any, get_args, Tuple, Iterable, Optional

from types import UnionType


def mca_type(ts: Iterable[type]) -> type:
    """
    Finds to most common ancestor type of the given types

    :param ts: Types to find common ancestors of
    :return: Most common ancestor type
    """
    return next(iter(reduce(and_, (Counter(t.mro()) for t in ts))))


def resolve_type(ann: Any) -> Tuple[Any, bool]:
    """
    Resolves the actual type of the given `typing` annotation

    :param ann: Annotation
    :return: Type wrapped by the `typing` annotation and boolean indicating whether the value is repeatable (e.g. when
             the type indicates a list of values etc.)
    """
    if isinstance(ann, type):
        return ann, False
    if isinstance(ann, UnionType):
        # Handling of older union type representation
        return resolve_type(get_args(ann)[0])
    match ann.__name__:
        case "Annotated" | "Optional":
            return resolve_type(get_args(ann)[0])
        case "Union":
            # TODO: Add handling for union types beside those representing typing.Optional e.g. <type> | None
            return resolve_type(get_args(ann)[0])
        case "List":
            t, _ = resolve_type(get_args(ann)[0])
            return t, True
        case "Literal":
            return mca_type([type(v) for v in get_args(ann)]), False
    raise ValueError(f"Cannot resolve unambiguous underlying type of annotation {ann}")
