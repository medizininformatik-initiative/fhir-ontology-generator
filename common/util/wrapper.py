from copy import deepcopy
from typing import Self


class dotdict(dict):
    """
    Creates a wrapper around a `dict` instance to allow for property-like access to dict values via key names

    Taken from this `post <https://stackoverflow.com/questions/2352181/how-to-use-a-dot-to-access-members-of-dictionary?page=1&tab=trending#tab-top>`
    """

    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__

    def __copy__(self) -> Self:
        """
        Creates a shallow copy of the instance
        :return: Copied instance
        """
        cls = self.__class__
        copy = cls.__new__(cls)
        copy.update(self)
        return copy

    def copy(self) -> Self:
        """
        Creates a shallow copy of the instance
        :return: Copied instance
        """
        return self.__copy__()

    def __deepcopy__(self, memo_dict: dict[any, any] | None = None) -> Self:
        """
        Creates a deep copy of the instances
        :param memo_dict: Optional dictionary of already copied objects
        :return: Copied instance
        """
        if memo_dict is None:
            memo_dict = {}
        cls = self.__class__
        copy = cls.__new__(cls)
        memo_dict[id(self)] = copy
        for k, v in self.items():
            setattr(copy, k, deepcopy(v, memo_dict))
        return copy

    def deepcopy(self, memo_dict: dict[any, any] | None = None) -> Self:
        """
        Creates a deep copy of the instances
        :param memo_dict: Optional dictionary of already copied objects
        :return: Copied instance
        """
        return self.__deepcopy__(memo_dict)
