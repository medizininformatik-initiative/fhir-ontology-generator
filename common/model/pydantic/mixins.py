from typing import Any, Callable

import pydantic
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from pydantic_core.core_schema import (
    SerializerFunctionWrapHandler,
    FieldSerializationInfo,
)

from common.typing.functions import resolve_type, type_is_sortable


class StandardBaseModel(BaseModel):
    """
    Default `pydantic` base model class providing both camel-case, ordered, and non-empty serialization
    """
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    @pydantic.field_serializer("*", mode="wrap")
    def _serialize_field(
        self,
        value: Any,
        handler: SerializerFunctionWrapHandler,
        info: FieldSerializationInfo,
    ):
        ser_value = handler(value)
        field_info = self.model_fields[info.field_name]
        try:
            match ser_value:
                case list():
                    field_t, _ = resolve_type(field_info.annotation)
                    if issubclass(field_t, StandardBaseModel):
                        return sorted(ser_value, key=field_t.__sort_key__())
                    return sorted(ser_value) if type_is_sortable(field_t) else ser_value
                case _:
                    return ser_value
        except Exception as exc:
            raise Exception(
                f"Failed to sort serialized content of field '{info.field_name}' in model class '{type(self).__name__}': {repr(exc)}"
            ) from exc


    @pydantic.model_serializer(mode="wrap")
    def _serialize_model(
        self,
        handler: SerializerFunctionWrapHandler,
    ):
        ser_model = handler(self)
        return self._sort_model(self._drop_empty_values_from_model(ser_model))


    @classmethod
    def _sort_model(cls, ser_model: dict[str, Any]) -> dict[str, Any]:
        return dict(sorted(ser_model.items()))

    @classmethod
    def __is_empty(cls, value: Any):
        match value:
            case list() | dict():
                return not value
            case None:
                return True
            case _:
                return False

    @classmethod
    def _drop_empty_values_from_model(cls, ser_model: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in ser_model.items() if not cls.__is_empty(v)}

    @classmethod
    def __sort_key__(cls) -> Callable[[dict[str, Any]], Any]:
        raise NotImplementedError("__sort_key__ not implemented")
