import functools
import os.path
from pathlib import Path

import pytest
from fhir.resources.R4B.elementdefinition import (
    ElementDefinition,
)
from fhir.resources.R4B.structuredefinition import StructureDefinition

from common.exceptions import NotFoundError
from common.model.fhir.structure_definition import StructureDefinitionSnapshot
from common.util.fhir.package.manager import FhirPackageManager
from common.util.project import Project

TEST_PROFILE_URL = "https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Specimen"


def _project() -> Project:
    return Project(path=Path(os.path.dirname(__file__)))


@pytest.fixture(scope="session")
def project() -> Project:
    return _project()


@functools.cache
def _package_manager() -> FhirPackageManager:
    pm = _project().package_manager
    pm.restore(inflate=True, lenient=True)
    return pm


@pytest.fixture(scope="session")
def package_manager() -> FhirPackageManager:
    return _package_manager()


@pytest.fixture(scope="session")
def resources_dir() -> Path:
    return Path(__file__).parent / "resources"


@pytest.fixture(scope="session")
def test_profile(package_manager: FhirPackageManager) -> StructureDefinitionSnapshot:
    idx_pattern = {"url": TEST_PROFILE_URL}
    if p := package_manager.find(idx_pattern) is not None:
        return p
    else:
        raise NotFoundError(
            f"Cannot find structure definition of test profile '{idx_pattern['url']}'"
        )


@pytest.fixture
def profile(request, package_manager: FhirPackageManager, resources_dir: Path):
    """
    Fixture that can be used for indirect parameters named 'profile' to resolve any `string` typed value as a
    profile URL or pass on any `StructureDefinition` typed parameters
    """
    match request.param:
        case str(profile_url):
            return package_manager.find({"url": profile_url})
        case Path() as profile_f:
            f_path = resources_dir / profile_f
            return StructureDefinitionSnapshot.model_validate_json(f_path.read_text(encoding="utf-8"))
        case StructureDefinition() as struct_def:
            return struct_def
        case _ as param:
            raise ValueError(
                f"Fixture 'profile' does not support indirect parameters of type {type(param)} "
                f"[supported_types=[{type(str)}, {type(Path)}, {type(StructureDefinition)}]]"
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


