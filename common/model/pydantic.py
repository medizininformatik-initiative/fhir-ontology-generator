from typing import Type, Mapping, Any, Dict, TypeVar

import cachetools
from pydantic import BaseModel, TypeAdapter
from pydantic.fields import FieldInfo
from pydantic.v1.utils import to_lower_camel


T = TypeVar("T", bound=BaseModel)


class CamelCaseBaseModel(BaseModel):
    """
    Base model class fi serialization of field in lower camel case is desired
    """

    class Config:
        alias_generator = to_lower_camel


@cachetools.cached(cache={}, key=lambda fi: hash(fi))
def _get_type_adapter_for_field(field_info: FieldInfo) -> TypeAdapter:
    return TypeAdapter(field_info.annotation)


def validate_subset(model_cls: Type[T], data: Mapping[str, Any]) -> Dict[str, Any]:
    """
    Validates a subset of fields against a model class, e.g. missing fields are ignored

    :param model_cls: Model class to validate against
    :param data: Collection of a subset of field value pairs required for a valid model instance
    :return: Validated subset
    """
    validated = {}
    for key, value in data.items():
        if key in model_cls.model_fields:
            field = model_cls.model_fields[key]
            validated[key] = _get_type_adapter_for_field(field).validate_python(value)
    return validated
