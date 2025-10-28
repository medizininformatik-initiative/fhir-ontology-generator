from pydantic import Field
from typing import Annotated, Any, Dict

from pydantic import BaseModel


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
        Dict[str, Any],
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
        int,
        Field(
            frozen=True, default=30, description="Time after which to retry in seconds"
        ),
    ]
    retries: Annotated[
        int | None,
        Field(frozen=True, default=5, description="Number of retries, None => infinity"),
    ]
    backoff_factor: Annotated[
        float,
        Field(frozen=True, default=2, description="Retry backoff factor in seconds"),
    ]


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
