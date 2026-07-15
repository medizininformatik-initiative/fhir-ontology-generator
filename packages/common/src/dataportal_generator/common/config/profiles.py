import abc
import re
from typing import Annotated, Any, ClassVar, override

import pydantic
from fhir.resources.R4B.structuredefinition import StructureDefinition
from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    ModelWrapValidatorHandler,
    ValidationError,
    model_validator,
)

from dataportal_generator.common.fhir.pattern import matches_pattern
from dataportal_generator.common.model.fhir.package import FhirPackage


class ProfileFilter(abc.ABC, BaseModel):
    _registry: ClassVar[dict[str, type["ProfileFilter"]]] = {}

    def __init_subclass__(cls, key: str | None = None, **kwargs):
        super().__init_subclass__(**kwargs)
        if key := getattr(cls, "__key__", None):
            cls._registry[key] = cls

    @model_validator(mode="wrap")
    @classmethod
    def  _dispatch(cls, data: Any, handler: ModelWrapValidatorHandler["ProfileFilter"]) -> "ProfileFilter":
        if cls is not ProfileFilter:
            return handler(data)
        if not isinstance(data, dict) or len(data) != 1:
            raise ValueError(f"Expected a single-key dict, got {data!r}")
        key, value = next(iter(data.items()))
        subcls = ProfileFilter._registry.get(key)
        if subcls is None:
            raise ValueError(f"Unknown profile filter type: {key!r}")
        return subcls.model_validate(value)

    def match(self, package: FhirPackage, profile: StructureDefinition): ...


class CanonicalProfileFilter(ProfileFilter):
    __key__ = "canonical"

    patternString: str | None
    patternRegex: re.Pattern | None

    @model_validator(mode="before")
    @classmethod
    def _validate_patterns(cls, data: Any):
        if not data.keys() and cls.model_fields.keys():
            raise KeyError(
                "Either 'patternString' or 'patternRegex' has to be provided"
            )
        return data

    @override
    def match(self, package: FhirPackage, profile: StructureDefinition):
        if not profile.url:
            return False
        if self.patternString:
            return self.patternString in profile.url
        else:
            return bool(self.patternRegex.match(profile.url))


class PatternProfileFilter(ProfileFilter):
    __key__ = "pattern"

    model_config = ConfigDict(extra="allow")

    __allowed_elements: ClassVar[set[str]] = {
        name
        for name in StructureDefinition.model_fields
        if not name.startswith(("differential", "snapshot"))
    }

    @pydantic.model_validator(mode="before")
    @classmethod
    def _validate_patterns(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            raise TypeError(
                f"Input data is expected to be of 'dict' but is instead '{type(data)}'"
            )
        if disallowed := [key for key in data if key not in cls.__allowed_elements]:
            raise ValidationError(
                f"Unsupported parameters {', '.join(repr(f) for f in disallowed)}. Supported parameters are "
                f"{', '.join(repr(f) for f in cls.__allowed_elements)}"
            )
        return data

    @override
    def match(self, package: FhirPackage, profile: StructureDefinition):
        for name, pattern in self.model_extra.items():
            if (value := getattr(profile, name)) is None:
                return False
            if not matches_pattern(value, pattern):
                return False
        return True


def _str_or_pattern_validator(value: Any) -> Any:
    match value:
        case str():
            return value
        case {"pattern": pattern}:
            return re.compile(pattern)
        case _:
            raise ValueError(
                f"Expected either instance of type 'str' or object with key 'pattern' but got '{type(value)}'"
            )


class PackageProfileFilter(ProfileFilter):
    __key__ = "package"

    name: Annotated[re.Pattern | str | None, BeforeValidator(_str_or_pattern_validator)]
    version: Annotated[
        re.Pattern | str | None, BeforeValidator(_str_or_pattern_validator)
    ]

    @override
    def match(self, package: FhirPackage, profile: StructureDefinition):
        match self.name:
            case str():
                name_matches = package.name == self.name
            case re.Pattern():
                name_matches = self.name.search(package.name) is not None
            case _:
                name_matches = True
        match self.version:
            case str():
                version_matches = package.version == self.version
            case re.Pattern():
                version_matches = self.version.match(package.version) is not None
            case _:
                version_matches = True
        return name_matches and version_matches


class AnyOfProfileFilter(ProfileFilter):
    __key__ = "any"

    filters: list[ProfileFilter] = Field(default_factory=list)

    @override
    def match(self, package: FhirPackage, profile: StructureDefinition):
        return any(f.match(package, profile) for f in self.filters)


class AllOfProfileFilter(ProfileFilter):
    __key__ = "all"

    filters: list[ProfileFilter] = Field(default_factory=list)

    @override
    def match(self, package: FhirPackage, profile: StructureDefinition):
        return all(f.match(package, profile) for f in self.filters)


class ProfilesConfig(BaseModel):
    include: list[ProfileFilter] = Field(default_factory=list)

    def is_included(self, profile: StructureDefinition) -> bool:
        return not self.include or any(f.match(profile) for f in self.include)
