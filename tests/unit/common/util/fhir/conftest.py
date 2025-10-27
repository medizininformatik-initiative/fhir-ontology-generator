import functools
import os
from pathlib import Path

import pytest
from fhir.resources.R4B.elementdefinition import ElementDefinition
from fhir.resources.R4B.structuredefinition import StructureDefinition

from common.util.fhir.package.manager import FhirPackageManager, GitHubPackageManager
from common.util.project import Project


def _project() -> Project:
    return Project(path=Path(os.path.dirname(__file__)))


@pytest.fixture(scope="session")
def project() -> Project:
    return _project()


@functools.cache
def _package_manager() -> FhirPackageManager:
    pm = GitHubPackageManager(
        _project().path,
        org="medizininformatik-initiative",
        repo="fhir-package-store",
        branch="main",
        path="package-tarballs",
    )
    pm.restore(inflate=True)
    return pm


@pytest.fixture(scope="session")
def package_manager() -> FhirPackageManager:
    return _package_manager()


@pytest.fixture
def profile(request, package_manager: FhirPackageManager):
    """
    Fixture that can be used for indirect parameters named 'profile' to resolve any `string` typed value as a
    profile URL or pass on any `StructureDefinition` typed parameters
    """
    match request.param:
        case str() as profile_url:
            return package_manager.find({"url": profile_url})
        case StructureDefinition() as struct_def:
            return struct_def
        case _ as param:
            raise ValueError(
                f"Fixture 'profile' does not support indirect parameters of type {type(param)} "
                f"[supported_types=[{type(str)}, {type(StructureDefinition)}]]"
            )


@pytest.fixture
def elem_def(request, profile):
    """
    Fixture that can be used for indirect parameters named 'elem_def' to resolve any `string` typed value as a
    profile URL or pass on any `ElementDefinition` typed parameters
    """
    match request.param:
        case str() as elem_id:
            return profile.get_element_by_id(elem_id)
        case ElementDefinition() as elem_def:
            return elem_def
        case _ as param:
            raise ValueError(
                f"Fixture 'elem_def' does not support indirect parameters of type {type(param)} "
                f"[supported_types=[{type(str)}, {type(ElementDefinition)}]]"
            )
