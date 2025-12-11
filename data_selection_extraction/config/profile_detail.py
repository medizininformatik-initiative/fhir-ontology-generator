import re
from abc import ABC
from logging import Logger
from re import Pattern
from typing import Annotated, List, Optional, Self, Mapping, Literal, Any

import cachetools
from fhir.resources.R4B.element import Element
from fhir.resources.R4B.elementdefinition import ElementDefinition
from fhir.resources.R4B.structuredefinition import StructureDefinition
from pydantic import BaseModel, Field, model_validator, ValidationError, field_validator

from common.model.pydantic import CamelCaseBaseModel
from common.util.fhir.package.manager import FhirPackageManager
from common.util.log.functions import get_class_logger


class MatchEntry(BaseModel):
    target: Literal["id", "path", "base.path"]
    exact: Annotated[bool, Field(default=False)]
    pattern: Pattern

    __exact_trailing_expr = r"((:([^.]+$))|\.|$)"

    @field_validator("pattern", mode="before")
    @classmethod
    def _coerce_to_pattern(cls, data: Any) -> Any:
        if data and not isinstance(data, re.Pattern):
            data = re.compile(data)
        return data

    @model_validator(mode="after")
    def _modify_pattern(self) -> Self:
        if self.exact:
            self.pattern = re.compile(self.pattern.pattern + self.__exact_trailing_expr)
        return self

    def matches(self, elem_def: ElementDefinition) -> bool:
        match self.target:
            case "id":
                target = elem_def.id
            case "path":
                target = elem_def.path
            case _:
                target = elem_def.base.path
        if self.exact:
            return self.pattern.match(target) is not None
        else:
            return self.pattern.search(target) is not None


class FieldConfigRecommendationEntry(CamelCaseBaseModel):
    match: Annotated[MatchEntry, Field(default_factory=lambda: MatchEntry())]
    reason_for_selection: Annotated[Optional[str], Field(default=None)]
    note: Annotated[Optional[str], Field(default=None)]

    def matches(self, elem_def: Element) -> bool:
        return self.match.matches(elem_def)


class FieldConfigRecommendation(BaseModel):
    always: Annotated[List[FieldConfigRecommendationEntry], Field(default=[])]
    never: Annotated[List[FieldConfigRecommendationEntry], Field(default=[])]

    def is_recommended(self, elem_def: Element) -> Optional[bool]:
        if self.never and any((e.matches(elem_def) for e in self.never)):
            return False
        elif self.always and any((e.matches(elem_def) for e in self.always)):
            return True
        else:
            return None


class FieldConfig(BaseModel, ABC):
    include: Annotated[List[FieldConfigRecommendationEntry], Field(default=[])]
    exclude: Annotated[List[FieldConfigRecommendationEntry], Field(default=[])]
    recommend: Annotated[
        FieldConfigRecommendation,
        Field(default_factory=lambda: FieldConfigRecommendation()),
    ]

    def is_recommended(self, elem_def: ElementDefinition) -> Optional[bool]:
        return self.recommend.is_recommended(elem_def)

    def is_included(self, elem_def: ElementDefinition) -> Optional[bool]:
        if self.include and any((e.matches(elem_def) for e in self.include)):
            return True
        elif self.exclude and any((e.matches(elem_def) for e in self.exclude)):
            return False
        else:
            return None


class FieldsConfig(BaseModel):
    __logger: Logger = get_class_logger("FieldsConfig")

    default: Annotated[FieldConfig, Field(default_factory=lambda: FieldConfig())]
    profiles: Annotated[Mapping[str, FieldConfig], Field(default_factory=dict)]

    @staticmethod
    def _cache_key(*args, elem_def=None, profile=None, **kwargs) -> (str, str):
        if elem_def is None:
            elem_def = args[1]
        if profile is None:
            profile = args[2]
        return elem_def.id, profile.url

    @cachetools.cached(cache={}, key=_cache_key)
    def is_recommended(
        self,
        elem_def: ElementDefinition,
        profile: StructureDefinition,
        pm: FhirPackageManager,
    ) -> Optional[bool]:
        try:
            profiles = [profile, *pm.dependencies_of(profile)]
        except Exception as exc:
            self.__logger.warning(
                f"Failed to resolve profile hierarchy for profile '{profile.url}' => Cannot determine recommendation of element def '{elem_def.id}' via config",
            )
            self.__logger.debug("Details:", exc_info=exc)
            return None
        profile_urls = [p.url for p in profiles]
        # Ensure order of the returned structure definitions starts at the most restrictive profile
        matching_urls = filter(lambda url: url in self.profiles.keys(), profile_urls)
        matching_entries = [self.profiles[url] for url in matching_urls]
        for entry in matching_entries:
            recommendation = entry.is_recommended(elem_def)
            if recommendation is None:
                # If pattern applies to the element definition then rules defined for parent profiles will be applied
                continue
            return recommendation
        # Since no profile-specific rule applies to the element definition, the default one will be applied
        return self.default.is_recommended(elem_def)

    @cachetools.cached(cache={}, key=_cache_key)
    def is_included(
        self,
        elem_def: ElementDefinition,
        profile: StructureDefinition,
        pm: FhirPackageManager,
    ) -> Optional[bool]:
        try:
            profiles = [profile, *pm.dependencies_of(profile)]
        except Exception as exc:
            self.__logger.warning(
                f"Failed to resolve profile hierarchy for profile '{profile.url}' => Cannot determine inclusion of element def '{elem_def.id}' via config"
            )
            self.__logger.debug("Details:", exc_info=exc)
            return None
        profile_urls = [p.url for p in profiles]
        # Ensure order of the returned structure definitions starts at the most restrictive profile
        matching_urls = filter(lambda url: url in self.profiles.keys(), profile_urls)
        matching_entries = [self.profiles[url] for url in matching_urls]
        for entry in matching_entries:
            is_included = entry.is_included(elem_def)
            if is_included is None:
                # If pattern applies to the element definition then rules defined for parent profiles will be applied
                continue
            return is_included
        # Since no profile-specific rule applies to the element definition, the default one will be applied
        return self.default.is_included(elem_def)
