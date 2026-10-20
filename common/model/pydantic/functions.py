from collections.abc import Sized


def is_empty(x: Sized) -> bool:
    return len(x) == 0