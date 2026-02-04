from typing import Any, get_args, Tuple

from types import UnionType


def resolve_type(ann: Any) -> Tuple[Any, bool]:
    """
    Resolves the actual type of the given `typing` annotation

    :param ann: Annotation
    :return: Type wrapped by the `typing` annotation
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
    raise ValueError(f"Cannot resolve unambiguous underlying type of annotation {ann}")
