import functools
import os.path
from pathlib import Path

import pytest
from fhir.resources.R4B.elementdefinition import ElementDefinition
from fhir.resources.R4B.structuredefinition import StructureDefinition

from common.exceptions import NotFoundError
from common.model.fhir.structure_definition import StructureDefinitionSnapshot
from common.util.fhir.package.manager import FhirPackageManager
from common.util.project import Project


def __test_dir() -> Path:
    return Path(os.path.dirname(os.path.realpath(__file__))).resolve()


@pytest.fixture(scope="session")
def test_dir() -> Path:
    return __test_dir()


def _project() -> Project:
    return Project(path=Path(os.path.dirname(__file__)) / "test-project")


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


@pytest.fixture(scope="session")
def sample_specimen_snapshot(
    package_manager: FhirPackageManager,
) -> StructureDefinitionSnapshot:
    package_name = "de.medizininformatikinitiative.kerndatensatz.biobank"
    profile_url = "https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Specimen"
    if profile := package_manager.find(
        package_pattern={"name": package_name},
        index_pattern={"url": profile_url},
    ):
        return profile
    else:
        raise NotFoundError(
            f"Could not find profile '{profile_url}' in package '{package_name}'"
        )


@pytest.fixture(scope="session")
def sample_specimen_snapshot_json(
    sample_specimen_snapshot: StructureDefinitionSnapshot,
) -> dict:
    return sample_specimen_snapshot.model_dump()


@pytest.fixture(scope="session")
def sample_specimen_snapshot_str(
    sample_specimen_snapshot: StructureDefinitionSnapshot,
) -> str:
    return sample_specimen_snapshot.model_dump_json()
