from abc import abstractmethod
from enum import unique, Enum, EnumMeta
from typing_extensions import Self


class PrimitiveFhirTypeMeta(EnumMeta):
    def __contains__(cls, item: str | Self) -> bool:
        import builtins
        match type(item):
            case cls.__class__:
                return item in cls.__members__.keys()
            case builtins.str:
                return item in cls.__members__.values()
            case _:
                raise TypeError(f"Argument type not supported [provided='{type(item)}', "
                                f"allowed={ {type(str), type(cls.__class__)} }]")


@unique
class PrimitiveFhirType(Enum, metaclass=PrimitiveFhirTypeMeta):
    INSTANT = 'instant'
    TIME = 'time'
    DATE = 'date'
    DATE_TIME = 'dateTime'
    BASE_64_BINARY = 'base64Binary'
    DECIMAL = 'decimal'
    BOOLEAN = 'boolean'
    URI = 'uri'
    URL = 'url'
    CANONICAL = 'canonical'
    CODE = 'code'
    STRING = 'string'
    INTEGER = 'integer'
    MARKDOWN = 'markdown'
    ID = 'id'
    OID = 'oid'
    UUID = 'uuid'
    UNSIGNED_INT = 'unsignedInt'
    POSITIVE_INT = 'positiveInt'