from typing import List, Any, Iterable


def flatten(lst: List[Any]) -> Iterable[Any]:
    """
    Flattens a list of lists with arbitrary depth
    :param lst: List to flatten
    :return: Iterator of flattened list
    """
    if not isinstance(lst, list):
        yield lst
    else:
        for element in lst:
            if isinstance(element, list) and not isinstance(element, (str, bytes)):
                yield from flatten(element)
            else:
                yield element