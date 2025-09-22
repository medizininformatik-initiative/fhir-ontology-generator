from typing import List, Any, Callable, TypeVar, Iterable, Optional


def flatten(lst: List[Any]) -> List[Any]:
    """
    Flattens a list of lists with arbitrary depth
    :param lst: List to flatten
    :return: Flattened list
    """
    if not isinstance(lst, list):
        yield lst
    else:
        for element in lst:
            if isinstance(element, list) and not isinstance(element, (str, bytes)):
                yield from flatten(element)
            else:
                yield element


T = TypeVar("T")

def first(f: Callable[[T], bool], xs: Iterable[T]) -> Optional[T]:
    """
    Attempts to find first match in the provided iterable

    :param f: Filter function
    :param xs: Iterable to find match in
    :return: First matching element or `None` if no match was found
    """
    return next(filter(f, xs), None)