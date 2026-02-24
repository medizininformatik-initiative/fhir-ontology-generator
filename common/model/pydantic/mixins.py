from typing import Final

from pydantic import BaseModel, model_serializer
from pydantic.v1.utils import to_lower_camel
from pydantic_core.core_schema import SerializerFunctionWrapHandler

from common.typing.functions import resolve_type


class CamelCase:
    """
    Base model class if serialization of field in lower camel case is desired
    """

    class Config:
        alias_generator = to_lower_camel


class SerializeSorted:
    """
    Pydantic model class mixin to automatically sort content during serialization, e.g. dict entries by their key and
    lists by their values ordering
    """

    __key__: Final[str] = "sorted"

    @model_serializer(mode="wrap")
    def serialize_model(
        self, handler: SerializerFunctionWrapHandler
    ) -> dict[str, object]:
        serialized = handler(self)
        for key, value in serialized.items():
            field_info = self.model_fields[key]
            sort = (
                field_info.json_schema_extra.get(SerializeSorted.__key__)
                if field_info.json_schema_extra
                else None
            )
            field_t, _ = resolve_type(field_info.annotation)
            if not issubclass(field_t, SerializeSorted) and sort != False:
                match value:
                    case list():
                        if sort is not None:
                            serialized[key] = sort(value)
                        else:
                            serialized[key] = sorted(value)
                    case _:
                        pass
        return {k: v for k, v in sorted(serialized.items())}
