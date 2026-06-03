from common.exceptions import UnsupportedError


class UnsupportedTypingException(UnsupportedError):
    """
    This exception represent a mismatch between the present range of types supported by two different elements or
    objects in general.
    """

    pass


class InvalidValueTypeException(ValueError):
    pass
