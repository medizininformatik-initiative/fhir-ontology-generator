from collections.abc import Iterable
from typing import List, Any


def flatten(lst: list[Any]) -> list[Any]:
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
