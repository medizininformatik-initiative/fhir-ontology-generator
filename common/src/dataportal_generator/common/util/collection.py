from typing import List, Any, Callable, TypeVar, Iterable, Optional


def flatten(xs: List[Any]) -> List[Any]:
    """
    Flattens a list of lists with arbitrary depth

    :param xs: List to flatten
    :return: Flattened list
    """
    if not isinstance(xs, list):
        return xs
    else:
        return [(flatten(x) if isinstance(x, list) else x) for x in xs]


T = TypeVar("T")


def first(f: Callable[[T], bool], xs: Iterable[T]) -> Optional[T]:
    """
    Attempts to find first match in the provided iterable

    :param f: Filter function
    :param xs: Iterable to find match in
    :return: First matching element or `None` if no match was found
    """
    return next(filter(f, xs), None)
