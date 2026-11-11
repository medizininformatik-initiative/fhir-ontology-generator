from abc import ABC
from collections.abc import Mapping

from pydantic import BaseModel

from dataportal_generator.common.model.terminology import TermCode


"""
Type description between contextualized term codes appearing in CCDL queries and the actual mapping entries for any
query language supported by the generator. This separation is separation is introduced to reduce redundancy and file 
size.
The value of each key-value pair shall correspond to the value of the `name` attribute of a :class:`MappingEntry` 
instance.
"""
type ContextualizedMapping = Mapping[tuple[TermCode, TermCode], str]


class MappingEntry(BaseModel, ABC):
    """
    Abstract query language mapping entry base class. The value of `name` shall be unique
    """

    name: str


class AttributeSearchParameter(BaseModel):
    """
    AttributeSearchParameter the information how to translate the attribute part of a criteria to a FHIR query snippet
    :param key: Defines the code of the attribute and acts as unique identifier within the ui_profile
                           (Required)
    :param types: Set of types the attribute supports
    """

    key: TermCode
    types: set[str]
