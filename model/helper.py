import copy
import sys


def del_none(dictionary):
    """
    Delete keys with the value ``None`` in a dictionary, recursively.
    :param dictionary: The dictionary to delete empty keys from.
    :return: The dictionary with empty keys deleted.
    """

    def delete_empty_elements_from_list(list_element):
        if not list_element:
            del dict_copy[key]
        for element in list_element:
            if isinstance(element, dict):
                del_none(element)
            elif isinstance(element, str):
                continue
            elif isinstance(element, list):
                delete_empty_elements_from_list(element)
            else:
                del_none(element.__dict__)

    dict_copy = copy.deepcopy(dictionary)
    for key, value in list(dict_copy.items()):
        if value is None:
            del dict_copy[key]
        elif isinstance(value, dict):
            del_none(value)
        elif isinstance(value, list):
            delete_empty_elements_from_list(value)
    return dict_copy


def str_to_class(class_name):
    """
    Convert a string to a class.
    :param class_name: name of the class
    :return: the class
    """
    return getattr(sys.modules[__name__], class_name)
