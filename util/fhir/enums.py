from enum import unique, Enum, EnumMeta

from typing_extensions import Self


class PrimitiveFhirTypeMeta(EnumMeta):
    def __contains__(cls, item: str | Self) -> bool:
        try:
            cls(item)
        except ValueError:
            return False
        return True


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