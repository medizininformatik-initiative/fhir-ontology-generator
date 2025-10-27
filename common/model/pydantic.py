import abc

from pydantic import BaseModel, computed_field


class SerializeType(abc.ABC, BaseModel):
    """
    Abstract model class to provide type information after serialization. The original type (e.g. class name) will be
    present in the `_type` attribute after model serialization
    """

    @computed_field(alias="_type")
    def _type(self) -> str:
        return self.__class__.__name__
