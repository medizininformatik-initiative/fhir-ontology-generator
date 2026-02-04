import functools
import json
import os
from pathlib import Path
from typing import Dict

import pytest
from fhir.resources.R4B.elementdefinition import ElementDefinition
from fhir.resources.R4B.structuredefinition import StructureDefinition

from common.util.fhir.package.manager import FhirPackageManager
from common.util.project import Project


def __test_dir() -> Path:
    return Path(os.path.dirname(os.path.realpath(__file__))).resolve()


@pytest.fixture(scope="session")
def test_dir() -> Path:
    return __test_dir()


def _project() -> Project:
    return Project(path=Path(os.path.dirname(__file__)) / "test_project")


@pytest.fixture(scope="session")
def project() -> Project:
    return _project()


@functools.cache
def _package_manager() -> FhirPackageManager:
    pm = _project().package_manager
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
                f"Fixture 'profile' does not support indirect parameters of type {type(param)} [supported_types=[{type(str)}, {type(StructureDefinition)}]]"
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
                f"Fixture 'elem_def' does not support indirect parameters of type {type(param)} [supported_types=[{type(str)}, {type(ElementDefinition)}]]"
            )


@pytest.fixture
def load_json_file(request, test_dir) -> str:
    print(test_dir, "expected_out", request.param)
    with open(
        os.path.join(test_dir, "expected_out", request.param), mode="r", encoding="utf-8"
    ) as f:
        return json.load(f)
