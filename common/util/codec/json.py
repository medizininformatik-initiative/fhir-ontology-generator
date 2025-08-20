import json
import os
from typing import Any, Protocol

from pydantic import BaseModel

from common.util.codec.functions import del_none


class JSONSerializable(Protocol):
    def to_json(self) -> str:
        ...


def write_object_as_json(serializable: JSONSerializable, file_name: str):
    """
    Writes a list of objects as json to a file
    :param serializable: object that can be serialized to json
    :param file_name: name of the file
    """
    os.makedirs(os.path.dirname(file_name), exist_ok=True)
    with open(file_name, mode="w", encoding="utf-8") as f:
        f.write(serializable.to_json())


class JSONFhirOntoEncoder(json.JSONEncoder):
    """
    Custom JSON encoder for the project which has some additional capabilities such as set encoding and deleting keys
    without values
    """
    def default(self, o: Any):
        """
        Provides a fallback for instances of the set class and those who have the __dict__ attribute
        :param o: Object to convert into serialize object
        :return: JSON-serializable object
        """
        # If the object is an instance of set convert it to a list object which is JSON serializable
        if isinstance(o, set):
            o.discard(None)
            return list(o)
        # Else if the object is a pydantic model class use the dump method inherent to it
        elif isinstance(o, BaseModel):
            return del_none(o.model_dump())
        # Else if an object can be serialized via the __dict__ attribute use it
        elif hasattr(o, "__dict__"):
            return del_none(o.__dict__)
        # Else use the default JSON encoder default function (which throws an exception)
        else:
            json.JSONEncoder.default(self, o)