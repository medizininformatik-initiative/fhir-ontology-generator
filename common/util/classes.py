import sys
from types import ModuleType
from typing import Type, Set

from common.util.functions import foldl


def get_subclasses(
    c: Type, direct_only: bool = False
) -> Set[Type]:
    """
    Returns all currently loaded (e.g. imported) subclasses of the given class

    :param c: Class to get subclasses of
    :param direct_only: If `True` only direct subclasses are returned
    :return: Set of class objects of subclasses
    """
    subclasses = set(c.__subclasses__())
    if direct_only:
        return subclasses
    else:
        return foldl(
            subclasses,
            subclasses.copy(),
            lambda acc, sc: acc.union(get_subclasses(sc)),
        )
