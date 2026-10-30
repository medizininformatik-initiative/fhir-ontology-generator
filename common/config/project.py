from typing import Annotated, Any

import isodate
from pydantic import BaseModel, Field, field_validator


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


class TerminologyConfig(BaseModel):
    use_release: str | None = Field(
        default=None,
        description="The release of to reuse terminological data of if possible",
    )


class ProjectConfig(BaseModel):
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
    terminology: Annotated[
        TerminologyConfig,
        Field(
            frozen=True,
            default=TerminologyConfig(),
            description="Configuration options related to terminological data",
        ),
    ]
