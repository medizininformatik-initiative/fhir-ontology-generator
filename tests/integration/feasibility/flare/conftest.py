import json
import os
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest
import requests
from _pytest.python import Metafunc
from fhir.resources.R4B.bundle import Bundle
from pytest_docker.plugin import Services, get_docker_services
from requests import RequestException

from common.util.fhir.package.manager import FhirPackageManager
from common.util.log.functions import get_logger
from common.util.test.docker import save_docker_logs
from tests.integration.feasibility.conftest import CCDLTestdataEntry

_logger = get_logger(__name__)


def __test_dir() -> str:
    return os.path.dirname(os.path.realpath(__file__))


@pytest.fixture(scope="module")
def test_dir() -> str:
    return __test_dir()


@pytest.fixture(scope="module")
def docker_compose_command(copy_and_unpack_project_output: Path) -> str:
    mapping_zip_file_path = copy_and_unpack_project_output / "mapping.zip"
    if not mapping_zip_file_path.exists() or not mapping_zip_file_path.is_file():
        raise FileNotFoundError(
            f"Missing mapping archive file @ {mapping_zip_file_path!r}"
        )
    return (
        f"TEST_INTEGRATION_MAPPING_ZIP={mapping_zip_file_path.absolute()} "
        f"docker compose"
    )


@pytest.fixture(scope="module")
def docker_compose_file() -> str:
    return os.path.join(__test_dir(), "docker-compose.yml")


@pytest.fixture(scope="module")
def docker_compose_project_name() -> str:
    return "test_integration_feasibility_flare"


@pytest.fixture(scope="module")
def docker_setup(pytestconfig) -> list[str]:
    return ["up --build -d --wait"]


@pytest.fixture(scope="module")
def docker_cleanup() -> list[str]:
    return ["down -v"]


@pytest.fixture(scope="module")
def docker_services(
    docker_compose_command: str,
    docker_compose_file: list[str] | str,
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


@pytest.fixture(scope="module", autouse=True)
def search_param_bundle(package_manager: FhirPackageManager):
    bundle_id = "mii-exa-meta-searchparam-transaction-bundle"
    bundle = package_manager.find(
        index_pattern={"resourceType": "Bundle", "id": bundle_id}
    )
    if not bundle:
        raise FileNotFoundError(f"Cannot find MII CDS search parameter bundle '{bundle_id}'")
    tmp_dir = Path(__test_dir(), ".tmp")
    tmp_dir.mkdir(exist_ok=True, parents=True)
    with (tmp_dir / "search_param_bundle.json").open(mode="w", encoding="utf-8") as fd:
        fd.write(bundle.model_dump_json())


@pytest.fixture(scope="module")
def fhir_server_url(
    docker_ip, docker_services, cds_test_data_bundles: list[Bundle]
) -> str:
    port = docker_services.port_for("fhir-server", 8080)
    base_url = f"http://{docker_ip}:{port}/fhir"
    _logger.info(f"Uploading MII CDS test data bundles to {base_url}")
    try:
        for b in cds_test_data_bundles:
            _logger.info(f"Uploading bundle {b.id!r}")
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


@pytest.fixture(scope="module")
def flare_url(docker_ip, docker_services) -> str:
    port = docker_services.port_for("flare", 8080)
    return f"http://{docker_ip}:{port}"


def pytest_generate_tests(metafunc: Metafunc):
    """
    Generates tests dynamically based on the collected querying metadata files within the project directory
    """
    feasibility_test_dir = Path(__test_dir()).parent
    if "test_run_ccdl_query" == metafunc.definition.name:
        with open(
            feasibility_test_dir / "ModuleTestDataConfig.json",
            mode="r",
            encoding="utf-8",
        ) as f:
            test_data_mapping = json.load(f)
        test_data = []
        for entry in map(
            lambda e: CCDLTestdataEntry.model_validate(e), test_data_mapping
        ):
            marks = []
            query_content = None
            if entry.status.disabled:
                marks = [pytest.mark.xfail(reason=entry.status.reason)]
            else:
                with (feasibility_test_dir / "test_queries" / entry.query).open(
                    mode="r", encoding="utf-8"
                ) as f:
                    query_content = f.read()
            test_data.append(
                pytest.param(
                    query_content,
                    entry.expected,
                    marks=marks,
                    id=entry.query,
                )
            )
        metafunc.parametrize(
            argnames=("ccdl_query", "expected"),
            argvalues=test_data,
        )