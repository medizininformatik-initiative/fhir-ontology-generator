import json
import os
from pathlib import Path
from urllib import request

import pytest
from _pytest.python import Metafunc

from common.util.project import Project
from ...conftest import project


def __test_dir() -> Path:
    return Path(os.path.dirname(os.path.realpath(__file__))).resolve()

@pytest.fixture(scope="session")
def test_dir() -> Path:
    return __test_dir()

def _schema_store(test_dir) -> dict:
    store = {}
    base_path = os.path.join(test_dir,"schemata","common")
    print(os.listdir(base_path))

    for schema in os.listdir(base_path):
        # schemas = os.path.join(base_path, schemas)
        if schema.endswith(".json"):
            with open(os.path.join(base_path, schema), 'r', encoding="UTF-8") as f:
                schema = json.load(f)
                if "$id" in schema:
                    store[schema["$id"]] = schema
    return store

@pytest.fixture(scope="session")
def schema_store(test_dir) -> dict:
    return _schema_store(test_dir)


def pytest_generate_tests(metafunc: Metafunc):
    """
    Generates tests dynamically based on the collected querying metadata files within the project directory
    """
    if "test_json_integrity_elastic_file" == metafunc.definition.name:
        config = metafunc.config
        # project = project
        test_dir = __test_dir()

        project_name = "fdpg-ontology"
        if project_name is None:
            raise ValueError("Command line option '--project' has to provided with a proper project name as its value")
        project = Project(name=project_name)


        elastic_folder = project.output / "merged_ontology" / "elastic"
        list_of_id_to_be_tested = os.listdir(elastic_folder)
        list_to_be_tested = [elastic_folder / elastic_file for elastic_file in os.listdir(elastic_folder)]


        metafunc.parametrize(
            argnames=("json_file", "test_dir", "schema_store"),
            argvalues=[(instance, test_dir, _schema_store(test_dir)) for instance in list_to_be_tested],
            ids=[it for it in list_of_id_to_be_tested],
            scope="session"
        )