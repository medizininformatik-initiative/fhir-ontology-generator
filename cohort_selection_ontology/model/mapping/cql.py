from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Set, Optional, List, Annotated, Union, Any
from typing_extensions import Self

from fhir.resources.R4B.coding import Coding
from fhir.resources.R4B.element import Element
from pydantic import BaseModel, Field, conlist

from cohort_selection_ontology.model.mapping import (
    HasSimpleCardinality,
    SimpleCardinality,
    AttributeSearchParameter,
)
from cohort_selection_ontology.model.ui_data import TermCode
from common.model.pydantic import SerializeType
from common.typing.cql import RetrievableType
from common.typing.fhir import FHIRPath
from common.util.codec.json import JSONFhirOntoEncoder
from common.util.collections.functions import flatten
from common.util.fhir.enums import FhirDataType


class FixedCQLCriteria(HasSimpleCardinality):
    def __init__(
        self,
        types: Set[str],
        path: FHIRPath,
        cardinality: SimpleCardinality,
        value=None,
    ):
        HasSimpleCardinality.__init__(self, cardinality)
        if value is None:
            value = []
        self.types = types
        self.value = value
        self.path = path


@dataclass
class CQLAttributeSearchParameter(AttributeSearchParameter, HasSimpleCardinality):
    path: FHIRPath

    def __init__(
        self,
        types: Set[str],
        attribute_code: TermCode,
        path: FHIRPath,
        cardinality: SimpleCardinality,
    ):
        """
        CQLAttributeSearchParameter stores the information how to translate the attribute part of a criteria to a CQL
        query snippet
        :param types: Set of types the attribute supports
        :param attribute_code: Coding identifying the attribute
        :param path: FHIRPath expression used in CQL to address the location the value
        :param cardinality: Aggregated cardinality of the target element
        """
        AttributeSearchParameter.__init__(self, types, attribute_code)
        HasSimpleCardinality.__init__(self, cardinality)
        self.path = path


@dataclass
class CQLTypeParameter(HasSimpleCardinality):
    """
    Holds information about an element within a FHIR resources that a filter targets
    :param path: Path to the targeted element as a FHIRPath expression
    :param types: Set of types supported by this element which can be multiple if the element is polymorphic
    """

    path: FHIRPath
    types: Set[str]

    def __init__(self, path: FHIRPath, types: Set[str], cardinality: SimpleCardinality):
        super().__init__(cardinality)
        self.path = path
        self.types = types


@dataclass
class CQLTimeRestrictionParameter(CQLTypeParameter):
    """
    Represents a time restriction element in a CQL mapping entry. Since we expect the corresponding element in the
    instance data to never repeat (i.e. be a list of date/time values) its cardinality is fixed to `SINGLE`
    """

    def __init__(self, path: FHIRPath, types: Set[str]):
        CQLTypeParameter.__init__(self, path, types, SimpleCardinality.SINGLE)


@dataclass
class CQLMapping:
    """
    CQLMapping stores all necessary information to translate a structured query to a CQL query.
    :param name: name of the mapping acting as primary key
    """

    name: str
    resourceType: str | None = None
    termCode: Optional[CQLTypeParameter] = None
    value: Optional[CQLTypeParameter] = None
    timeRestriction: Optional[CQLTimeRestrictionParameter] = None
    attributes: List[Attribute] = field(default_factory=list)
    # only required for version 1 support
    key: Optional[str] = None

    def add_attribute(self, attribute: Attribute):
        self.attributes.append(attribute)

    @classmethod
    def from_json(cls, json_dict):
        return cls(**json_dict)

    def to_json(self):
        return json.dumps(self, cls=JSONFhirOntoEncoder, sort_keys=True, indent=4)

    # only required for version 1 support
    def __eq__(self, other):
        return self.key == other.key

    def __ne__(self, other):
        return not self.__eq__(other)

    def __lt__(self, other):
        return self.key < other.key

    def __hash__(self):
        return hash(self.key)


class AttributeComponent(SerializeType):
    """
    Translates to an expression in a CQL where clause
    """

    types: Annotated[
        conlist(FhirDataType, min_length=1),
        Field(description="FHIR datatype of the targeted element"),
    ]
    path: Annotated[str, Field(description="Relative path to the targeted element")]
    cardinality: Annotated[
        SimpleCardinality,
        Field(description="Aggregated cardinality of the targeted element"),
    ]
    values: Annotated[
        list[Union[str, bool, int, float, Element]],
        Field(
            description="List of values to match against. Is empty if the values are obtained from the CCDL query "
            "i.e. are user input"
        ),
    ]


class ContextGroup(SerializeType):
    """
    Translates to a CQL source clause
    """

    path: Annotated[
        str,
        Field(
            description="Relative path to the target element selected in an CQL source clause"
        ),
    ]
    components: Annotated[
        conlist(Union[ContextGroup, AttributeComponent], min_length=1),
        Field(
            description="List of additional context groups and attribute components evaluated in the context of the "
            "selected element"
        ),
    ]

    @classmethod
    def model_construct(
        cls, _fields_set: set[str] | None = None, **values: Any
    ) -> Self:
        # Remove ContextGroup nodes with empty or unchanging (e.g. '$this') path from tree
        if "components" in values:
            values["components"] = list(
                flatten(
                    [
                        (
                            c.components
                            if isinstance(c, ContextGroup)
                            and (not c.path or c.path == "$this")
                            else c
                        )
                        for c in values["components"]
                    ]
                )
            )
        return super().model_construct(_fields_set, **values)


# TODO: Parsing of `resolve` function invocations
class ReferenceGroup(ContextGroup):
    type: RetrievableType


Component = ContextGroup | AttributeComponent


class Attribute(BaseModel):
    key: Annotated[
        Coding,
        Field(
            description="Coded key used to map criterion attributes in a CCDL query to attributes entries in the CQL "
            "mapping"
        ),
    ]
    components: Annotated[
        conlist(Union[ContextGroup, AttributeComponent], min_length=1),
        Field(
            description="List of context groups and attribute components evaluated in the context composing the "
            "attribute"
        ),
    ]
