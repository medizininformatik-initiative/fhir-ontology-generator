import os
import shutil
from pathlib import Path

import pytest

from common.util.project import Project


def __test_dir() -> Path:
    return Path(os.path.dirname(os.path.realpath(__file__)))


@pytest.fixture(scope="session")
def test_dir() -> Path:
    return __test_dir()


def pytest_addoption(parser):
    parser.addoption("--project", action="store", default="fdpg-ontology")


@pytest.fixture(scope="session", autouse=True)
def copy_and_unpack_project_output(pytestconfig) -> Path:
    project = Project(name=pytestconfig.getoption("--project"))

    tmp_path = os.path.join(__test_dir(), ".tmp")
    ontology_dir_path = os.path.join(tmp_path, "ontology")
    if not os.path.exists(ontology_dir_path):
        # Only copy and unpack generator output if not already present to prevent unnecessary processing if multiple
        # workers call the fixture and to avoid race conditions
        os.makedirs(ontology_dir_path)

        # Copy and unpack ontology archives
        backend_path = os.path.join(tmp_path, "backend.zip")
        shutil.copyfile(
            project.output.mkdirs("merged_ontology") / "backend.zip", backend_path
        )
        shutil.unpack_archive(backend_path, ontology_dir_path)

        migration_path = os.path.join(ontology_dir_path, "migration")
        os.makedirs(migration_path, exist_ok=True)
        for file_name in os.listdir(ontology_dir_path):
            if file_name.endswith(".sql"):
                shutil.move(os.path.join(ontology_dir_path, file_name), migration_path)

        dse_dir_path = os.path.join(ontology_dir_path, "dse")
        os.makedirs(dse_dir_path, exist_ok=True)
        shutil.move(os.path.join(ontology_dir_path, "profile_tree.json"), dse_dir_path)

        mapping_path = os.path.join(tmp_path, "mapping.zip")
        shutil.copyfile(
            project.output.mkdirs("merged_ontology") / "mapping.zip", mapping_path
        )
        unpacked_dir_path = os.path.join(ontology_dir_path, "mapping")
        os.makedirs(unpacked_dir_path, exist_ok=True)
        shutil.unpack_archive(mapping_path, ontology_dir_path)

        shutil.move(
            os.path.join(unpacked_dir_path, "cql", "mapping_cql.json"),
            os.path.join(ontology_dir_path, "mapping_cql.json"),
        )
        shutil.move(
            os.path.join(unpacked_dir_path, "fhir", "mapping_fhir.json"),
            os.path.join(ontology_dir_path, "mapping_fhir.json"),
        )
        shutil.move(
            os.path.join(unpacked_dir_path, "dse_mapping_tree.json"),
            os.path.join(ontology_dir_path, "dse_mapping_tree.json"),
        )
        shutil.move(
            os.path.join(unpacked_dir_path, "mapping_tree.json"),
            os.path.join(ontology_dir_path, "mapping_tree.json"),
        )
        shutil.rmtree(unpacked_dir_path)

        # Copy elastic archive
        shutil.copyfile(
            project.output.mkdirs("merged_ontology") / "elastic.zip",
            os.path.join(tmp_path, "elastic.zip"),
        )

        # Copy availability output
        out_path = Path(tmp_path, "availability")
        out_path.mkdir(parents=True, exist_ok=True)
        shutil.copytree(project.output.availability.path, out_path, dirs_exist_ok=True)

    return Path(tmp_path)


@pytest.fixture(scope="session")
def cql_mapping_file(copy_and_unpack_project_output) -> Path:
    return copy_and_unpack_project_output / "ontology" / "mapping_cql.json"


@pytest.fixture(scope="session")
def mapping_tree_file(copy_and_unpack_project_output) -> Path:
    return copy_and_unpack_project_output / "ontology" / "mapping_tree.json"


@pytest.fixture(scope="session")
def availability_dir(copy_and_unpack_project_output) -> Path:
    return copy_and_unpack_project_output / "availability"
