import os.path
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from common.model.fhir.structure_definition import StructureDefinitionSnapshot
from common.util.project import Project


def __test_dir() -> Path:
    return Path(os.path.dirname(os.path.realpath(__file__))).resolve()


@pytest.fixture(scope="session")
def test_dir() -> Path:
    return __test_dir()


@pytest.fixture(scope="session")
def fdpg_project(repository_root_dir: Path) -> Project:
    return Project(path=repository_root_dir / "projects" / "fdpg-ontology")


@pytest.fixture(scope="module")
def sample_snapshot_bioprobe(project: Project) -> StructureDefinitionSnapshot:
    snapshot = project.package_manager.find(
        {
            "url": "https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Specimen"
        }
    )
    return snapshot


@pytest.fixture(scope="module")
def sample_snapshot_bioprobe_json(sample_snapshot_bioprobe) -> Mapping[str, Any]:
    return sample_snapshot_bioprobe.model_dump()


@pytest.fixture(scope="module")
def sample_snapshot_diagnose(project: Project) -> StructureDefinitionSnapshot:
    snapshot = project.package_manager.find(
        {
            "url": "https://www.medizininformatik-initiative.de/fhir/core/modul-diagnose/StructureDefinition/Diagnose"
        }
    )
    return snapshot


# @pytest.fixture
# def project(request) -> Project:
#    project_name = "fdpg-ontology"
#    if project_name is None:
#        raise ValueError(
#            "Command line option '--project' has to provided with a proper project name as its value"
#        )
#    return Project(name=project_name)
