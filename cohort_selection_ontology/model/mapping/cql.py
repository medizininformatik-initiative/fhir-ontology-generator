from __future__ import annotations

from dataclasses import field

from enum import Enum
from typing import (
    Union,
    Set,
    List,
    Optional,
    ClassVar,
    Collection,
    override,
    Callable,
    Any,
)

from pydantic import field_validator

from cohort_selection_ontology.model.mapping import (
    AttributeSearchParameter,
    DenormalizedMapping,
    Mapping,
)
from cohort_selection_ontology.model.ui_data import TermCode
from common.model.fhir.types import FHIRDataTypeStr
from common.model.pydantic.mixins import (
    StandardBaseModel,
)
from common.typing.fhir import FHIRPath


class SimpleCardinality(str, Enum):
    SINGLE = "single"
    MANY = "many"

    def __mul__(self, other: SimpleCardinality) -> SimpleCardinality:
        if self == SimpleCardinality.MANY or other == SimpleCardinality.MANY:
            return SimpleCardinality.MANY
        else:
            return SimpleCardinality.SINGLE

    @staticmethod
    def from_fhir_cardinality(fhir_card: Union[int, str]) -> SimpleCardinality:
        """
        Maps the cardinality value of an ElementDefinition instance in a FHIR StructureDefinition resource instance to a
        member of this enum. Note that the value '0' will be mapped to 'SINGLE'
        :param fhir_card: Cardinality value (either of 'min' or 'max' element) to map
        :return: Member of this enum class corresponding to the provided cardinality value
        """
        match fhir_card:
            case 0 | 1 | "0" | "1":
                return SimpleCardinality.SINGLE
            case _:
                return SimpleCardinality.MANY


class FixedCQLCriteria(StandardBaseModel):
    types: Set[FHIRDataTypeStr["R4B"]]
    value: List[TermCode]
    path: FHIRPath
    cardinality: SimpleCardinality


class CQLTypeParameter(StandardBaseModel):
    """
    Holds information about an element within a FHIR resources that a filter targets
    """

    _allowed_types: ClassVar[Collection[str]] = set()

    path: FHIRPath
    types: List[FHIRDataTypeStr["R4B"]]
    cardinality: SimpleCardinality
    reference_target_type: Optional[str] = None

    @field_validator("types", mode="after")
    @classmethod
    def __validate_types(cls, types: List[str]) -> List[str]:
        if not types:
            raise ValueError("At least one type must be specified")
        if cls._allowed_types:
            if diff := [t for t in types if t not in cls._allowed_types]:
                raise ValueError(
                    f"Illegal time type(s) {diff}. Allowed type range is {cls._allowed_types}"
                )
        return types


class CQLAttributeSearchParameter(AttributeSearchParameter, CQLTypeParameter):
    """
    CQLAttributeSearchParameter stores the information how to translate the attribute part of a criteria to a CQL
    query snippet
    """

    @classmethod
    def __sort_key__(cls) -> Callable[[dict[str, Any]], Any]:
        return lambda x: repr(x.get("key"))


class CQLTimeRestrictionParameter(CQLTypeParameter):
    """
    Represents a time restriction element in a CQL mapping entry. Since we expect the corresponding element in the
    instance data to never repeat (i.e. be a list of date/time values) its cardinality is fixed to `SINGLE`
    """

    _allowed_types: ClassVar[Collection[str]] = frozenset(
        [
            "instant",
            "date",
            "time",
            "dateTime",
            "Period",
        ]
    )


class CQLMapping(Mapping):
    """
    CQLMapping stores all necessary information to translate a structured query to a CQL query. If the
    ``key_attribute`` is not set then the targeted attribute is assumed to be the primary code filter of the
    corresponding ELM FHIR ModelInfo type and there will be no explicit mapping for this attribute.
    """

    PRIMARY_ATTR_KEY: ClassVar[TermCode] = TermCode(
        system="https://www.medizininformatik-initiative.de/fdpg-plus/ccdl/attribute",
        code="primary-attribute",
        display="Primary criterion attribute",
    )

    key_attribute: Optional[CQLTypeParameter] = None
    time_restriction: Optional[CQLTimeRestrictionParameter] = None
    attributes: List[CQLAttributeSearchParameter] = field(default_factory=list)

    @override
    def denormalize(self, context: TermCode, key: TermCode) -> DenormalizedCQLMapping:
        """
        Builds the denormalized version of the generic CQL mapping object uniquely identified by the provided context
        and key

        :param context: Context coding to associate with the denormalized version
        :param key: Key coding to associate with the denormalized version
        :return: ``DenormalizedCQLMapping`` object
        """
        key_attr = self.key_attribute
        return DenormalizedCQLMapping(
            name=self.name,
            resource_type=self.resource_type,
            context=context,
            key=key,
            time_restriction=self.time_restriction,
            attributes=[
                CQLAttributeSearchParameter(
                    key=self.PRIMARY_ATTR_KEY.model_copy(deep=True),
                    path=key_attr.path,
                    cardinality=key_attr.cardinality,
                    types=key_attr.types,
                    reference_target_type=key_attr.reference_target_type,
                ),
                *self.attributes,
            ],
        )


class DenormalizedCQLMapping(DenormalizedMapping):
    time_restriction: Optional[CQLTimeRestrictionParameter] = None
    attributes: List[CQLAttributeSearchParameter] = field(default_factory=list)
