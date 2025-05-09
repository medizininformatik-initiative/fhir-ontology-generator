import os

import pytest

from common.util.project import Project


def pytest_addoption(parser):
    parser.addoption(
        "--project", action="store", default="fdpg-ontology", help="Name of project to run these integration tests for"
    )


@pytest.fixture
def project(request) -> Project:
    project_name = request.config.getoption("--project")
    if project_name is None:
        raise ValueError("Command line option '--project' has to provided with a proper project name as its value")
    return Project(name=project_name)


def __repository_root_dir(request) -> str:
    return request.config.rootpath


@pytest.fixture(scope="session")
def repository_root_dir(request) -> str:
    return __repository_root_dir(request)