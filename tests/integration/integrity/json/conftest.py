import json
import os
from pathlib import Path
from os import PathLike
from cohort_selection_ontology.model.query_metadata import ResourceQueryingMetaData
from typing import Mapping, Union, Iterator, Optional

import pytest
from _pytest.python import Metafunc

from common.util.project import Project
from ...conftest import project
from common.util.log.functions import get_logger

logger = get_logger(__file__)


def __test_dir() -> Path:
    return Path(os.path.dirname(os.path.realpath(__file__))).resolve()


@pytest.fixture(scope="session")
def test_dir() -> Path:
    return __test_dir()


def _schema_store(test_dir) -> dict:
    store = {}
    base_path = os.path.join(test_dir, "schemata", "common")
    logger.info(os.listdir(base_path))

    for schema in os.listdir(base_path):
        if schema.endswith(".json"):
            with open(os.path.join(base_path, schema), "r", encoding="UTF-8") as f:
                schema = json.load(f)
                if "$id" in schema:
                    store[schema["$id"]] = schema
    return store


@pytest.fixture(scope="session")
def schema_store(test_dir) -> dict:
    return _schema_store(test_dir)


def __querying_metadata_schema(test_dir: Union[str, PathLike]) -> dict:
    with open(
        file=os.path.join(test_dir, "schemata", "querying_metadata.schema.json"),
        mode="r",
        encoding="utf8",
    ) as file:
        return json.load(file)


@pytest.fixture(scope="session")
def querying_metadata_schema(test_dir: Union[str, PathLike]) -> Mapping[str, any]:
    return __querying_metadata_schema(test_dir)


def __querying_metadata_list(project: Project) -> list[ResourceQueryingMetaData]:
    modules_dir_path = project.input.cso.mkdirs("modules")
    metadata_list = []
    for module_dir in os.listdir(modules_dir_path):  # ../modules/*
        metadata_dir_path = modules_dir_path / module_dir / "QueryingMetaData"
        for file in os.listdir(
            metadata_dir_path
        ):  # ../modules/*/QueryingMetaData/*.json
            if file.endswith(".json"):
                with open(metadata_dir_path / file, mode="r", encoding="utf8") as f:
                    metadata_list.append(ResourceQueryingMetaData.from_json(f))
    return metadata_list


def querying_metadata_list(project: Project) -> list[ResourceQueryingMetaData]:
    return __querying_metadata_list(project)


def querying_metadata_id_fn(val):
    """
    Generates tests IDs for QueryingMetadata tests parameters based on their backend and name
    """
    if isinstance(val, ResourceQueryingMetaData):
        return f"{val.module.code}::{val.name}"


def pytest_generate_tests(metafunc: Metafunc):
    qm_list = __querying_metadata_list(
        Project(name=metafunc.config.getoption("--project"))
    )

    if "test_json_integrity_elastic_file" == metafunc.definition.name:
        config = metafunc.config
        # project = project
        test_dir = __test_dir()

        project_name = metafunc.config.getoption("--project")
        if project_name is None:
            raise ValueError(
                "Command line option '--project' has to provided with a proper project name as its value"
            )
        project = Project(name=project_name)

        elastic_folder = project.output / "merged_ontology" / "elastic"
        list_of_id_to_be_tested = os.listdir(elastic_folder)
        list_to_be_tested = [
            elastic_folder / elastic_file for elastic_file in os.listdir(elastic_folder)
        ]

        metafunc.parametrize(
            argnames=("json_file", "test_dir", "schema_store"),
            argvalues=[
                (instance, test_dir, _schema_store(test_dir))
                for instance in list_to_be_tested
            ],
            ids=[it for it in list_of_id_to_be_tested],
            scope="session",
        )

    if "test_criterion_definition_validity" == metafunc.definition.name:
        schema = __querying_metadata_schema(__test_dir())
        metafunc.parametrize(
            argnames=("querying_metadata", "querying_metadata_schema"),
            argvalues=[(instance, schema) for instance in qm_list],
            ids=[querying_metadata_id_fn(it) for it in qm_list],
            scope="session",
        )
