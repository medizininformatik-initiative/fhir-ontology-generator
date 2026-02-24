import re
from abc import ABC
from logging import Logger
from typing import Annotated, List, Optional, Mapping, Any, Tuple

import cachetools
from fhir.resources.R4B.elementdefinition import ElementDefinition
from fhir.resources.R4B.structuredefinition import StructureDefinition
from pydantic import BaseModel, Field, field_validator

from common.model.fhir.pydantic import validate_partial_model
from common.model.pydantic.mixins import CamelCase
from common.util.fhir.package.manager import FhirPackageManager
from common.util.log.functions import get_class_logger

_POS_REGEX_IDENTIFIER = "?regex:"
_ALIAS_MAP = {
    (field.alias if field.alias else name): name
    for name, field in ElementDefinition.model_fields.items()
}

_FHIRPATH_EXT_PATTERN = re.compile(r"\(\?fhir:(?P<pattern>.+)\)")


def slices(pattern: Optional[str] = None) -> str:
    return rf":{pattern}" if pattern else r":[a-zA-Z0-9\/\-_\[\]@]+"


def slicesOrSelf(pattern: Optional[str] = None) -> str:
    return rf"({slices(pattern)})?"


def descendants() -> str:
    return r"(\.[a-z][A-Za-z0-9]*(\[x])?(:[a-zA-Z0-9\/\-_\[\]@]+)?)+"


def descendantsOrSelf() -> str:
    return rf"({descendants()})?"


def _compile_operator(matchobj: re.Match) -> str:
    pattern = matchobj.group("pattern")
    return "".join([eval(part) for part in pattern.split(";")])


def _compile_fhir_regex_extensions(regex: str) -> str:
    return _FHIRPATH_EXT_PATTERN.sub(repl=_compile_operator, string=regex)


def _matches_pattern(model: BaseModel, pattern: Mapping[str, Any]) -> bool:
    for key, val in pattern.items():
        if instance_val := getattr(model, _ALIAS_MAP[key], None):
            match val:
                case list():
                    match = all(
                        (
                            any((_matches_pattern(y, x) for y in instance_val))
                            for x in val
                        )
                    )
                case dict():
                    match = _matches_pattern(instance_val, val)
                case _:
                    match val:
                        case re.Pattern():
                            match = val.fullmatch(instance_val) is not None
                        case _:
                            match = val == instance_val
            if not match:
                return False
        else:
            return False
    return True


class FieldConfigEntry(BaseModel, CamelCase):
    pattern: Annotated[Mapping[str, Any], Field(default_factory=dict)]
    note: Annotated[Optional[str], Field(default=None)]

    @field_validator("pattern", mode="before")
    @classmethod
    def _validate_pattern(cls, data: dict[str, Any]) -> Any:
        # Do partial validation of pattern object
        validate_partial_model(ElementDefinition, data)
        # Identify and compile regex patterns
        return cls._compile_to_patterns(data)

    @classmethod
    def _compile_to_patterns(cls, data: dict[str, Any]) -> Any:
        for key, val in data.items():
            match val:
                case list():
                    data[key] = [cls._compile_to_patterns(x) for x in val]
                case dict():
                    data[key] = cls._compile_to_patterns(val)
                case _:
                    if isinstance(val, str) and val.startswith(_POS_REGEX_IDENTIFIER):
                        data[key] = re.compile(
                            _compile_fhir_regex_extensions(
                                val.lstrip(_POS_REGEX_IDENTIFIER)
                            )
                        )
        return data

    def matches(self, elem_def: ElementDefinition) -> bool:
        return _matches_pattern(elem_def, self.pattern)


class FieldConfigRecommendation(BaseModel):
    always: Annotated[List[FieldConfigEntry], Field(default=[])]
    never: Annotated[List[FieldConfigEntry], Field(default=[])]

    def is_recommended(self, elem_def: ElementDefinition) -> Optional[bool]:
        if self.never and any((e.matches(elem_def) for e in self.never)):
            return False
        elif self.always and any((e.matches(elem_def) for e in self.always)):
            return True
        else:
            return None


class FieldConfig(BaseModel, ABC):
    include: Annotated[List[FieldConfigEntry], Field(default=[])]
    exclude: Annotated[List[FieldConfigEntry], Field(default=[])]
    required: Annotated[List[FieldConfigEntry], Field(default=[])]
    recommend: Annotated[
        FieldConfigRecommendation,
        Field(default_factory=lambda: FieldConfigRecommendation()),
    ]

    def is_recommended(self, elem_def: ElementDefinition) -> Optional[bool]:
        return self.recommend.is_recommended(elem_def)

    def is_required(self, elem_def: ElementDefinition) -> Optional[bool]:
        if self.required:
            return any((e.matches(elem_def) for e in self.required))
        else:
            return None

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
    def _cache_key(*args, elem_def=None, profile=None, **kwargs) -> Tuple[str, str]:
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
    def is_required(
        self,
        elem_def: ElementDefinition,
        profile: StructureDefinition,
        pm: FhirPackageManager,
    ) -> Optional[bool]:
        try:
            profiles = [profile, *pm.dependencies_of(profile)]
        except Exception as exc:
            self.__logger.warning(
                f"Failed to resolve profile hierarchy for profile '{profile.url}' => Cannot determine if element represented by element def '{elem_def.id}' is required via config"
            )
            self.__logger.debug("Details:", exc_info=exc)
            return None
        profile_urls = [p.url for p in profiles]
        # Ensure order of the returned structure definitions starts at the most restrictive profile
        matching_urls = filter(lambda url: url in self.profiles.keys(), profile_urls)
        matching_entries = [self.profiles[url] for url in matching_urls]
        for entry in matching_entries:
            is_required = entry.is_required(elem_def)
            if is_required is None:
                # If pattern applies to the element definition then rules defined for parent profiles will be applied
                continue
            return is_required
        # Since no profile-specific rule applies to the element definition, the default one will be applied
        return self.default.is_required(elem_def)

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
