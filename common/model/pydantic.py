from typing import Any

import cachetools
from pydantic import BaseModel, TypeAdapter
from pydantic.v1.utils import to_lower_camel


class CamelCaseBaseModel(BaseModel):
    """
    Base model class fi serialization of field in lower camel case is desired
    """

    class Config:
        alias_generator = to_lower_camel


@cachetools.cached(cache={}, key=lambda fi: hash(fi))
def _get_type_adapter_for_type(t: Any) -> TypeAdapter:
    return TypeAdapter(t)
