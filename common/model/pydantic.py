from pydantic import BaseModel
from pydantic.v1.utils import to_lower_camel


class CamelCaseBaseModel(BaseModel):
    """
    Base model class fi serialization of field in lower camel case is desired
    """
    class Config:
        alias_generator = to_lower_camel
