from typing import Any

from pydantic import BaseModel


dict_keys = type({}.keys())


def field_names(x: dict | object | BaseModel) -> set[str]:
    """
    Returns the field names of the argument
    :param x: Either `dict`, `object`, or `pydantic.BaseModel` instance
    :return: Set of field names
    """
    match x:
        case dict():
            ks = x.keys()
        case object():
            ks = x.__dict__.keys()
        case BaseModel():
            ks = x.model_fields.keys()
        case _:
            raise TypeError(
                f"Unsupported type [expected={{'dict', 'object', 'pydantic.BaseModel'}}, actual='{type(x)}']"
            )
    return set(ks)
