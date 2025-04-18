import copy


def del_none(dictionary):
    """
    Delete keys with the value ``None`` in a dictionary, recursively.
    :param dictionary: The dictionary to delete empty keys from.
    :return: The dictionary with empty keys deleted.
    """

    def delete_empty_elements_from_list(list_element: list) -> list:
        if not list_element:
            del dict_copy[key]
        l = list()
        for element in list_element:
            if isinstance(element, dict):
                l.append(del_none(element))
            elif isinstance(element, str):
                l.append(element)
            elif isinstance(element, list):
                l.append(delete_empty_elements_from_list(element))
            else:
                l.append(del_none(element.__dict__))
        return l

    dict_copy = copy.deepcopy(dictionary)
    for key, value in list(dict_copy.items()):
        if value is None:
            del dict_copy[key]
        elif isinstance(value, dict):
            dict_copy[key] = del_none(value)
        elif isinstance(value, list):
            dict_copy[key] = delete_empty_elements_from_list(value)
    return dict_copy
