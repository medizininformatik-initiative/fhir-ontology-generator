import os
import shutil
import subprocess
from pathlib import Path
from typing import Union, Iterator

import pytest
import requests
from _pytest.python import Metafunc
from fhir.resources.R4B.bundle import Bundle
from fhir.resources.R4B.measure import Measure
from pytest_docker.plugin import Services, get_docker_services
from requests import RequestException

from common.util.log.functions import get_logger
from common.util.fhir.package.manager import FhirPackageManager
from common.util.project import Project
from common.util.test.docker import save_docker_logs

_logger = get_logger(__name__)


_CODING_MEASURE_FILE_NAME = "Measure-CdsCodingAvailability.fhir.json"
_DSE_ELEMENT_MEASURE_FILE_NAME = "Measure-DseElementAvailability.fhir.json"

_MEASURES = [_CODING_MEASURE_FILE_NAME, _DSE_ELEMENT_MEASURE_FILE_NAME]

_FHIR_SERVER_SERVICE_NAME = "fhir-server"


def __test_dir() -> Path:
    return Path(os.path.dirname(os.path.realpath(__file__)))


@pytest.fixture(scope="module")
def test_dir() -> Path:
    return __test_dir()


@pytest.fixture(scope="module")
def package_manager(project: Project) -> FhirPackageManager:
    project.package_manager.restore(inflate=True, lenient=True)
    return project.package_manager


@pytest.fixture(scope="module")
def tmp_dir(test_dir: Path):
    mask = os.umask(0)
    tmp_dir = test_dir / ".tmp"
    try:
        tmp_dir.mkdir(mode=0o777, parents=True, exist_ok=True)
        (tmp_dir / "input").mkdir(mode=0o777, exist_ok=True)
        (tmp_dir / "output").mkdir(mode=0o777, exist_ok=True)
        yield tmp_dir
    finally:

        shutil.rmtree(tmp_dir, ignore_errors=True)
        os.umask(mask)


@pytest.fixture(scope="module")
def measure(request, availability_dir) -> Measure:
    fp = availability_dir / request.param
    if not fp.exists() and not fp.is_file():
        raise FileNotFoundError(f"Cannot find element measure file @ {fp}")
    with fp.open(mode="r", encoding="utf-8") as f:
        measure = Measure.model_validate_json(f.read())
    return measure


@pytest.fixture(scope="module")
def docker_compose_file() -> str:
    return os.path.join(__test_dir(), "docker-compose.yml")


@pytest.fixture(scope="module")
def docker_compose_project_name() -> str:
    return "test_integration_availability"


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


def pytest_generate_tests(metafunc: Metafunc):
    if ("test_stratifier_fhirpath_expression_validity" == metafunc.definition.name
            or "test_measure_compatability_with_fde" == metafunc.definition.name):
        params = [pytest.param(measure_fn) for measure_fn in _MEASURES]
        metafunc.parametrize(
            argnames=["measure"],
            argvalues=params,
            indirect=["measure"],
            ids=[measure_fn.split(".")[0] for measure_fn in _MEASURES],
            scope="module",
        )

    if "test_generating_measure_report" == metafunc.definition.name:
        metafunc.parametrize(
            argnames=["measure", "tmp_dir", "test_dir", "fhir_server_url"],
            argvalues=[
                pytest.param(measure_fn, None, None, None) for measure_fn in _MEASURES
            ],
            indirect=["measure", "tmp_dir", "test_dir", "fhir_server_url"],
            ids=[measure_fn.split(".")[0] for measure_fn in _MEASURES],
            scope="module",
        )
