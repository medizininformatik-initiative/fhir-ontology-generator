import json
import os
import subprocess
import time
from pathlib import Path
from string import Template
from typing import Mapping, Union, Iterator, Optional, Any

from _pytest.python import Metafunc
from pydantic import BaseModel
from pytest_docker.plugin import Services, get_docker_services

import pytest

from common.util.log.functions import get_logger
from common.util.test.docker import save_docker_logs

_logger = get_logger(__file__)


class Status(BaseModel):
    disabled: bool = False
    reason: Optional[str] = None


class SearchResponseTestdataEntry(BaseModel):
    id: str
    results: list[Mapping[str, Any]]
    status: Status = Status()


def __test_dir() -> str:
    return os.path.dirname(os.path.realpath(__file__))


@pytest.fixture(scope="session")
def test_dir() -> str:
    return __test_dir()


@pytest.fixture(scope="session")
def docker_compose_file() -> str:
    return os.path.join(__test_dir(), "docker-compose.yml")


@pytest.fixture(scope="session")
def docker_compose_project_name() -> str:
    return "test-integration-elastic"


@pytest.fixture(scope="session")
def docker_setup(pytestconfig) -> list[str]:
    return ["up --build -d"]


@pytest.fixture(scope="session")
def docker_cleanup() -> list[str]:
    return ["down -v"]


@pytest.fixture(scope="session")
def docker_services(
    docker_compose_command: str,
    docker_compose_file: Union[list[str], str],
    docker_compose_project_name: str,
    docker_setup: list[str],
    docker_cleanup: list[str],
) -> Iterator[Services]:
    # We overwrite this fixture to allow for the Docker container logs to be saved before `pytest-docker` removes them
    try:
        with get_docker_services(
            docker_compose_command,
            docker_compose_file,
            docker_compose_project_name,
            docker_setup,
            [],  # No automatic clean up by pytest-docker
        ) as docker_service:
            yield docker_service
    finally:
        save_docker_logs(Path(__test_dir()), docker_compose_project_name)
        subprocess.check_output(
            " ".join(
                [
                    docker_compose_command,
                    "-f",
                    docker_compose_file,
                    "-p",
                    docker_compose_project_name,
                    *docker_cleanup,
                ]
            ),
            cwd=__test_dir(),
            shell=True,
        )


@pytest.fixture(scope="session")
def elastic_url(docker_ip, docker_services, docker_compose_project_name) -> str:
    service_name = "elastic-init"
    _logger.debug(f"Waiting for service '{service_name}' to exit")

    attempts = 0
    max_attempts = 60
    while attempts < max_attempts:
        status = (
            subprocess.check_output(
                f"docker ps --all --filter \"NAME={docker_compose_project_name}-{service_name}-1\" --format '{{{{json .State}}}}'",
                shell=True,
            )
            .decode("utf-8")
            .strip()
            .strip('"')
        )
        if status == "exited":
            break
        attempts += 1
        time.sleep(5)
    if attempts == max_attempts:
        raise Exception(f"Service '{service_name}' did not exit in time")

    _logger.debug("Upload of Elasticsearch documents is done")
    return f"http://{docker_ip}:{docker_services.port_for('elastic', 9200)}"


def search_response_id_fn(response: Mapping[str, Any]) -> str:
    entry = response["results"][0]
    return f"{entry['kdsModule']}#{entry['context']}#{entry['terminology']}"


def __load_search_responses() -> list[SearchResponseTestdataEntry]:
    data_file_path = Path(__test_dir(), "search_responses.json")
    test_data = []
    with open(data_file_path, mode="r", encoding="utf-8") as data_file:
        for entry in json.load(data_file):
            test_data.append(SearchResponseTestdataEntry.model_validate(entry))
    return test_data


@pytest.fixture(scope="session")
def query_templates() -> Mapping[str, Template]:
    templates_dir = Path(__test_dir(), "templates")
    templates = dict()
    for file_path in templates_dir.iterdir():
        with file_path.open(mode="r", encoding="utf-8") as template_file:
            templates[file_path.stem] = Template(template_file.read())
    return templates


@pytest.fixture
def query_template(request, query_templates: Mapping[str, Template]) -> Template:
    if not isinstance(request.param, str):
        raise TypeError(
            f"Fixture 'query_template' expects parameters of type 'str', but got '{type(request.param)}'"
        )
    return query_templates[request.param]


def pytest_generate_tests(metafunc: Metafunc):
    """
    Generates tests dynamically based on the collected querying metadata files within the project directory
    """

    if "test_criterion_term_code_search" == metafunc.definition.name:
        entries = __load_search_responses()
        params = []
        for entry in entries:
            marks = []
            if entry.status.disabled:
                marks.append(pytest.mark.xfail(reason=entry.status.reason))
            params.append(
                pytest.param(
                    "criterion_term_code_search",
                    entry.results[0],
                    marks=marks,
                    id=entry.id,
                )
            )
        metafunc.parametrize(
            argnames=("query_template", "expected"),
            argvalues=params,
            indirect=["query_template"],
        )
