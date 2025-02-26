import json
from collections.abc import Callable
from typing import Any, Tuple, TypeAlias

from typing_extensions import Never, Optional

from model.helper import del_none


class JSONSetEncoder(json.JSONEncoder):
    """
    Custom JSON encoder to enable encoding of Python set instances to JSON arrays
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
        # Else if an object can be serialized via the __dict__ attribute use it
        elif hasattr(o, "__dict__"):
            return del_none(o.__dict__)
        # Else use the default JSON encoder default function (which throws an exception)
        else:
            json.JSONEncoder.default(self, o)