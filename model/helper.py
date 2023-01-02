import copy
import sys


def del_none(dictionary):
    """
    Delete keys with the value ``None`` in a dictionary, recursively.
    :param dictionary: The dictionary to delete empty keys from.
    :return: The dictionary with empty keys deleted.
    """
    dict_copy = copy.deepcopy(dictionary)
    for key, value in list(dict_copy.items()):
        if value is None:
            del dict_copy[key]
        elif isinstance(value, dict):
            del_none(value)
        elif isinstance(value, list):
            if not value:
                del dict_copy[key]
            for element in value:
                del_none(element.__dict__)
    return dict_copy


def str_to_class(class_name):
    """
    Convert a string to a class.
    :param class_name: name of the class
    :return: the class
    """
    return getattr(sys.modules[__name__], class_name)