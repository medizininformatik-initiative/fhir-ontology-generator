from typing import Annotated, Any

import isodate
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)
from pydantic_core import InitErrorDetails

from dataportal_generator.common.config.profiles import ProfilesConfig
from dataportal_generator.common.log.functions import get_logger

_logger = get_logger(__file__)


_PROJECT_CONFIG_SECTION_MODELS: dict[str, type[BaseModel]] = {}


def _to_snake_case(name: str) -> str:
    return name.replace("-", "_")


def register_config_module(key: str, model_cls: type[BaseModel]):
    """
    Registers the provided model class under the provided key so that if the project config is loaded then the content
    under a top level key matching this key is parsed using the associated model class.
    
    Use this function to dynamically register config sections for external modules by calling this function during
    module initialization.

    :param key: Value to match the name of the top level elements against
    :param model_cls: Model class used to parse matching content
    :param aliases: (Optional) aliases to register
    """
    if not key:
        raise ValueError("Parameter 'key' cannot be empty")
    if model_cls is None:
        raise ValueError("Parameter 'model_cls' cannot be None")
    if key in _PROJECT_CONFIG_SECTION_MODELS:
        raise KeyError(f"Cannot register config module model class '{model_cls}'. Key {key!r} is already associated "
                       f"with class '{_PROJECT_CONFIG_SECTION_MODELS[key]}'")
    _PROJECT_CONFIG_SECTION_MODELS[key] = model_cls
    _logger.info(f"Registered config module '{key!r}' (model class: {model_cls})")


class FhirPackageManagerConfig(BaseModel):
    type: Annotated[
        str,
        Field(
            frozen=True,
            description="Type of the package manager to use",
            default="firely",
        ),
    ]
    params: Annotated[
        dict[str, Any],
        Field(
            frozen=True,
            init=True,
            default={},
            description="Parameters passed to manager instance constructor",
        ),
    ]


class FhirPackagesConfig(BaseModel):
    manager: Annotated[
        FhirPackageManagerConfig,
        Field(
            frozen=True,
            description="Config for the FHIR package manager instance used",
            default=FhirPackageManagerConfig(),
        ),
    ]


class HTTPConfig(BaseModel):
    timeout: Annotated[
        int | str,
        Field(
            frozen=True, default=30, description="Time after which to retry in seconds"
        ),
    ]
    retries: Annotated[
        int | None,
        Field(
            frozen=True, default=5, description="Number of retries, None => infinity"
        ),
    ]
    backoff_factor: Annotated[
        float,
        Field(frozen=True, default=2, description="Retry backoff factor in seconds"),
    ]

    @field_validator("timeout", mode="before")
    @classmethod
    def parse_iso_if_str(cls, value: Any) -> Any:
        if isinstance(value, str):
            return isodate.parse_duration(value).seconds
        return value


class ProjectConfig(BaseModel):
    model_config = ConfigDict(
        extra="allow"
    )

    fhir_packages: Annotated[
        FhirPackagesConfig,
        Field(
            frozen=True,
            alias="fhir-packages",
            default=FhirPackagesConfig(),
            description="Configuration options related to FHIR packages",
        ),
    ]
    http: Annotated[
        HTTPConfig,
        Field(
            frozen=True,
            default=HTTPConfig(),
            description="Configuration options related to HTTP clients",
        ),
    ]
    profiles: Annotated[
        ProfilesConfig,
        Field(
            frozen=True,
            default=ProfilesConfig(),
            description="Configuration options determining what FHIR StructureDefinitions are used by the generator. "
                        "Note that some components might still use FHIR StructureDefinitions from outside this scope "
                        "that are in the package cache if for instance an included profile reference them etc."
        )
    ]

    @model_validator(mode="before")
    @classmethod
    def _validate_extra(cls, data: Any) -> Any:
        """
        Validates the extra fields in the config data and parses them using the registered model classes if applicable.
        """
        if not isinstance(data, dict):
            return data
        for key, model_cls in _PROJECT_CONFIG_SECTION_MODELS.items():
            if key in data:
                try:
                    data[_to_snake_case(key)] = model_cls.model_validate(data[key])
                except ValidationError as err:
                    raise ValidationError.from_exception_data(
                        title=f"Invalid config section {key!r}",
                        input_type="python",
                        line_errors=[
                            InitErrorDetails(
                                type="invalid_config",
                                loc=(key,),
                                input=data[key]
                            )
                        ]
                    ) from err
        return data
