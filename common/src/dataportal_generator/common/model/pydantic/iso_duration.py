import datetime
from typing import Any, Annotated

import isodate
import pydantic_core
from pydantic import BeforeValidator, PlainSerializer


def serialize_duration(v: datetime.timedelta | isodate.Duration) -> str:
    """
    Serializes a duration to an ISO format string

    :param v: Either a ``datetime.timedelta`` or an ``isodate.Duration`` instance
    :return: ISO duration formatted string
    """
    return isodate.duration_isoformat(v)


def deserialize_duration(v: Any) -> datetime.timedelta | isodate.Duration:
    """
    Deserializes an ISO duration formatted string

    :param v: ISO duration formatted string
    :return: ``isodate.Duration`` instance if duration string has years/months or an ``datetime.timedelta`` instance if
             not
    """
    if isinstance(v, datetime.timedelta):
        return v
    if isinstance(v, str):
        return isodate.parse_duration(v)
    raise ValueError(f"Cannot parse type '{type(v)}' as ISO duration: {repr(v)}")


class _PydanticIsodateDuration(isodate.Duration):
    """
    Wrapper class for ``isodate.Duration`` to allow ``pydantic`` to deserialize to instances of this type
    """

    @classmethod
    def __get_pydantic_core_schema__(
        cls, *_, **__
    ) -> pydantic_core.core_schema.CoreSchema:
        return pydantic_core.core_schema.no_info_plain_validator_function(
            lambda v: isodate.parse_duration(v) if isinstance(v, str) else v,
            serialization=pydantic_core.core_schema.plain_serializer_function_ser_schema(
                isodate.duration_isoformat
            ),
        )


IsoDuration = Annotated[
    datetime.timedelta | _PydanticIsodateDuration,
    BeforeValidator(deserialize_duration),
    PlainSerializer(serialize_duration, return_type=str, when_used="always"),
]
