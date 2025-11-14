import json
import os.path
from pathlib import Path

import pytest

from common.model.structure_definition import StructureDefinitionSnapshot
from common.util.project import Project


def __test_dir() -> Path:
    return Path(os.path.dirname(os.path.realpath(__file__))).resolve()


@pytest.fixture(scope="session")
def test_dir() -> Path:
    return __test_dir()


def __sample_snapshot_bioprobe_str() -> str:
    with open(
        os.path.join(__test_dir(), "testdata", "FDPG_Bioprobe-snapshot.json"),
        "r",
        encoding="UTF-8",
    ) as f:
        return f.read()


def __sample_snapshot_diagnose_str() -> str:
    rel_path = os.path.join(__test_dir(), "testdata", "FDPG_Diagnose-snapshot.json")
    print(os.scandir("."))

    with open(rel_path, "r", encoding="UTF-8") as f:
        return f.read()


@pytest.fixture(scope="session")
def sample_snapshot_bioprobe_json() -> StructureDefinitionSnapshot:
    return json.loads(__sample_snapshot_bioprobe_str())


@pytest.fixture(scope="session")
def sample_snapshot_bioprobe() -> StructureDefinitionSnapshot:
    return StructureDefinitionSnapshot.model_validate_json(
        __sample_snapshot_bioprobe_str()
    )


@pytest.fixture(scope="session")
def sample_snapshot_diagnose() -> StructureDefinitionSnapshot:
    return StructureDefinitionSnapshot.model_validate_json(
        __sample_snapshot_diagnose_str()
    )


@pytest.fixture
def project() -> Project:
    # project_name = request.config.getoption("-p")
    project_name = "fdpg-ontology"
    if project_name is None:
        raise ValueError(
            "Command line option '--project' has to provided with a proper project name as its value"
        )
    return Project(name=project_name)
