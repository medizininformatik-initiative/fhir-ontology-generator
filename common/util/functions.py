from typing import TypeVar, Callable, Iterable, Reversible


A = TypeVar("A")
B = TypeVar("B")


def foldl(xs: Iterable[A], acc: B, f: Callable[[B, A], B]) -> B:
    """
    Applies a binary operator `acc` to all elements of an iterable `xs` from left to right and returns the resulting
    modified accumulator `acc`

    :param xs: Iterable to accumulate elements of
    :param acc: Accumulator holding the accumulated result
    :param f: Binary operator applied to each element and the accumulator
    :return: Modified accumulator `acc`
    """
    [acc := f(acc, x) for x in xs]
    return acc


def foldr(xs: Reversible[A], acc: B, f: Callable[[A, B], B]) -> B:
    """
    Applies a binary operator `acc` to all elements of an iterable `xs` from right to left and returns the resulting
    modified accumulator `acc`

    :param xs: Iterable to accumulate elements of
    :param acc: Accumulator holding the accumulated result
    :param f: Binary operator applied to each element and the accumulator
    :return: Modified accumulator `acc`
    """
    return foldl(reversed(xs), acc, f)


def first(xs: Iterable[A], f: Callable[[A], bool]) -> A | None:
    """
    Returns the first element matching the predicate from the provided iterable

    :param xs: Iterable object to filter
    :param f: Predicate to apply the iterables elements
    :return: First matching element or `None` if none matched
    """
    return next(filter(f, xs), None)
