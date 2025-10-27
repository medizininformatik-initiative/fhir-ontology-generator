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
