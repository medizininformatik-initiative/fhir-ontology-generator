from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from functools import cached_property
from typing import Set, Optional, List, Annotated, Union, Any, Callable

from typing_extensions import Self, Literal

from fhir.resources.R4B.element import Element
from pydantic import BaseModel, Field, conlist, field_validator, model_validator
from urllib3.util.ssl_match_hostname import match_hostname

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
from common.util.fhirpath.functions import find_common_root


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


_THIS_PATH_REGEX = re.compile(r"\.?\$this\.?")


class Component(BaseModel, ABC):
    path: Annotated[str, Field(default="$this", min_length=1)]

    @field_validator("path", mode="after")
    @classmethod
    def condense_path(cls, value: str):
        return value if value == "$this" else _THIS_PATH_REGEX.sub("", value)

    @cached_property
    def abs_path(self):
        return (f"{self.parent.abs_path}." if self.parent else "") + self.path

    @abstractmethod
    def __add__(self, other: Component) -> Component:
        pass


class AttributeComponent(Component):
    """
    Translates to an expression in a CQL where clause
    """

    type: Annotated[
        str,
        Field(description="FHIR datatype of the targeted element"),
    ]
    cardinality: Annotated[
        SimpleCardinality,
        Field(description="Aggregated cardinality of the targeted element"),
    ]
    operator: Annotated[
        Literal["=", "!=", "~", "!~"],
        Field(
            description="Comparison operator used to compare values with", default="eq"
        ),
    ]
    values: Annotated[
        list[Union[str, bool, int, float, Element]],
        Field(
            description="List of values to match against. Is empty if the values are obtained from the CCDL query "
            "i.e. are user input"
        ),
    ]

    def merge(self, c: Component):
        match c:
            case AttributeComponent() as ac:
                root = find_common_root(self.path, ac.path)
                prefix = root + "."
                return ContextGroup(
                    path=root if root else "$this",
                    components=[
                        self.model_copy(
                            update={"path": self.path.removeprefix(prefix)}
                        ),
                        c.model_copy(update={"path": self.path.removeprefix(prefix)}),
                    ],
                )
            case ContextGroup() as cg:
                return cg.merge(self)
            case _:
                raise ValueError(f"Cannot handle parameters of type '{type(c)}'")

    def __add__(self, other: Component) -> Component:
        match other:
            case ContextGroup() as cg:
                return ContextGroup(
                    path="$this",
                    components=[self, *(cg.components if cg.path == "$this" else cg)],
                )
            case _:
                return ContextGroup(path="$this", components=[self, other])


class ContextGroup(Component):
    """
    Translates to a CQL source clause
    """

    components: Annotated[
        List[Component],
        Field(
            description="List of additional context groups and attribute components evaluated in the context of the "
            "selected element"
        ),
    ]

    @field_validator("components", mode="after")
    @classmethod
    def condense_components(cls, value: List[Component]):
        # Remove ContextGroup nodes with empty or unchanging (e.g. '$this') path from tree
        # The parent references will be updated later by the corresponding validator that is run after as it is a model
        # validator and has mode 'after'
        value = list(
            flatten(
                [
                    (
                        c.components
                        if isinstance(c, ContextGroup)
                        and (not c.path or c.path == "$this")
                        else c
                    )
                    for c in value
                ]
            )
        )
        return value

    @model_validator(mode="after")
    def update_parents(self) -> Self:
        for c in self.components:
            c.parent = self
        return self

    def map(self, f: Callable[[Component], Component]) -> Self:
        components = []
        for c in self.components:
            r = f(c)
            r.parent = self
            components.append(r)
        self.components = components
        return self

    def merge(self, c: Component) -> Self:
        for idx, contained in enumerate(self.components):
            if root := find_common_root(c.path, contained.path):
                self.components[idx] = contained.merge(
                    c.model_copy(update={"path": c.path.removeprefix(root + ".")})
                )
                return self
        self.components.append(c)
        return self

    def append(self, c: Component) -> Self:
        if isinstance(c, ContextGroup) and c.path == "$this":
            for cc in c.componets:
                cc.parent = self
            self.components.extend(c.componets)
        else:
            c.parent = self
            self.components.append(c)
        return self

    def and_then(self, *cs: Component) -> Component:
        match cs:
            case []:
                return self
            case [x]:
                if self.path == "$this":
                    return x
                else:
                    x.path = f"{self.path}.{x.path}"
            case _:
                self.components.extend(cs)
                return self

    def __add__(self, other: Component) -> Component:
        components = [*self.components] if self.path == "$this" else [self]
        if isinstance(other, ContextGroup) and other.path == "$this":
            components.extend(other.components)
        return ContextGroup(
            path="$this",
            components=components
        )


class ReferenceGroup(ContextGroup):
    type: RetrievableType


class Attribute(BaseModel):
    key: Annotated[
        TermCode,
        Field(
            description="Coded key used to map criterion attributes in a CCDL query to attributes entries in the CQL "
            "mapping"
        ),
    ]
    composition: Annotated[
        Union[ContextGroup, AttributeComponent],
        Field(
            description="Tree of scoped attribute components defining the process of selecting the element to evaluate "
            "the attribute value"
        ),
    ]
