import os
import shutil
import subprocess
from pathlib import Path
from typing import Union, Iterator, Any, Generator

import pytest
import requests
from _pytest.fixtures import FixtureRequest
from fhir.resources.R4B.bundle import Bundle
from fhir.resources.R4B.measure import Measure
from pytest_docker.plugin import Services, get_docker_services
from requests import RequestException

from dataportal_generator.common.model.project import Project
from dataportal_generator.common.log.functions import get_logger
from dataportal_generator.common.util.docker import save_docker_logs

from importlib.resources import files, as_file

_logger = get_logger(__name__)

_FHIR_SERVER_SERVICE_NAME = "fhir-server"


@pytest.fixture(scope="module")
def availability_tmp_dir(tmp_path_factory) -> Generator[Path, Any, None]:
    mask = os.umask(0)
    tmp_dir = tmp_path_factory.mktemp("availability")
    try:
        tmp_dir.mkdir(mode=0o777, parents=True, exist_ok=True)
        (tmp_dir / "input").mkdir(mode=0o777, exist_ok=True)
        (tmp_dir / "output").mkdir(mode=0o777, exist_ok=True)
        yield tmp_dir
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        os.umask(mask)


@pytest.fixture(scope="module")
def measure(request) -> Measure:
    """
    Gathers actual FHIR Measure resources from sources provided by the implementation of ``MeasureContractTests``
    """
    return request.param(request)


@pytest.fixture(scope="module")
def docker_compose_file(availability_tmp_dir: Path) -> str:
    with as_file(files("dataportal_generator.availability_test.resources").joinpath("docker-compose.yml")) as path:
        fp_str = shutil.copy2(path, availability_tmp_dir / path.name)
    return str(fp_str)


@pytest.fixture(scope="module")
def docker_compose_project_name() -> str:
    return "availability_integration_test"


@pytest.fixture(scope="module")
def docker_setup(pytestconfig) -> list[str]:
    return [f"up --build -d --wait {_FHIR_SERVER_SERVICE_NAME}"]


@pytest.fixture(scope="module")
def docker_cleanup() -> list[str]:
    return ["down -v"]


@pytest.fixture(scope="module")
def docker_services(
    docker_compose_command: str,
    docker_compose_file: Union[list[str], str],
    docker_compose_project_name: str,
    docker_setup: list[str],
    docker_cleanup: list[str],
    project: Project,
    request: FixtureRequest
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
        save_docker_logs(project, request.module, docker_compose_project_name)
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
            shell=True,
        )


@pytest.fixture(scope="module")
def fhir_server_url(
    docker_ip, docker_services, cds_test_data_bundles: list[Bundle]
) -> str:
    port = docker_services.port_for("fhir-server", 8080)
    base_url = f"http://{docker_ip}:{port}/fhir"
    _logger.info(f"Uploading MII CDS test data bundles to {base_url}")
    try:
        for b in cds_test_data_bundles:
            _logger.info(f"Uploading bundle {repr(b.id)}")
            response = requests.post(
                base_url,
                json=b.model_dump(mode="json"),
                headers={"Content-Type": "application/fhir+json"},
            )
            response.raise_for_status()
            # break # We could also use all test data bundles, but would need to adjust the expected patient count
    except Exception as exc:
        raise Exception(
            f"Upload of test data failed. Details: {exc.response.content if isinstance(exc, RequestException) else exc}"
        ) from exc
    return base_url
