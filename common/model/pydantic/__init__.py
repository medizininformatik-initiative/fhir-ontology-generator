from typing import Any

import cachetools
from pydantic import TypeAdapter


@cachetools.cached(cache={}, key=lambda fi: hash(fi))
def get_type_adapter_for_type(t: Any) -> TypeAdapter:
    return TypeAdapter(t)
