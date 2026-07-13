import base64
import json
import os
import subprocess
import uuid
from pathlib import Path
from typing import Union, Iterator, Optional

import requests
from _pytest.python import Metafunc
from fhir.resources.R4B.attachment import Attachment
from fhir.resources.R4B.bundle import BundleEntry, BundleEntryRequest, Bundle
from fhir.resources.R4B.library import Library
from fhir.resources.R4B.measure import Measure
from fhir.resources.R4B.resource import Resource
from pydantic import BaseModel
from pytest_docker.plugin import Services, get_docker_services

import pytest
from requests import RequestException

from common.util.log.functions import get_logger
from common.util.test.docker import save_docker_logs

_logger = get_logger(__name__)


_MEASURE_TEMPLATE_FILE_NAME: str = "Measure.json"
_LIBRARY_TEMPLATE_FILE_NAME: str = "Library.json"

_TRANSLATOR_TOOL_PATH = Path(__file__).parent / ".tmp" / "cctb-cli.jar"
_TRANSLATOR_TOOL_URL = (
    f"https://github.com/medizininformatik-initiative/sq2cql/releases/download"
    f"/v{os.environ['CCTB_CLI_VERSION']}"
    f"/cctb-cli-{os.environ['CCTB_CLI_VERSION']}.jar"
)


class Status(BaseModel):
    disabled: bool = False
    reason: Optional[str] = None


class CCDLTestdataEntry(BaseModel):
    query: str
    expected: int = 1
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
    return "test_integration_feasibility"


@pytest.fixture(scope="session")
def docker_setup(pytestconfig) -> list[str]:
    return ["up --build -d --wait"]


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


def _create_library(cql_content: str) -> Library:
    with Path(__test_dir(), _LIBRARY_TEMPLATE_FILE_NAME).open(
        mode="r", encoding="utf-8"
    ) as file:
        data = file.read()
    library = Library.model_validate_json(data, strict=True)
    library.url = uuid.uuid4().urn
    library.content = [
        Attachment(
            contentType="text/cql", data=base64.b64encode(cql_content.encode("utf-8"))
        )
    ]
    return library


def _create_measure(library: Library) -> Measure:
    with Path(__test_dir(), _MEASURE_TEMPLATE_FILE_NAME).open(
        mode="r", encoding="utf-8"
    ) as file:
        data = file.read()
    measure = Measure.model_validate_json(data, strict=True)
    measure.url = uuid.uuid4().urn
    measure.library = [library.url]
    return measure


def _bundle_entry(resource: Resource, method: str) -> BundleEntry:
    return BundleEntry(
        resource=resource,
        request=BundleEntryRequest(method=method, url=resource.get_resource_type()),
    )


def _create_bundle(*entries: Resource) -> Bundle:
    return Bundle(type="transaction", entry=[_bundle_entry(e, "POST") for e in entries])


@pytest.fixture(scope="session")
def translator_tool_exists():
    if not _TRANSLATOR_TOOL_PATH.exists() and not _TRANSLATOR_TOOL_PATH.is_file():
        _logger.info(
            f"Missing translator tool. Downloading JAR file from {_TRANSLATOR_TOOL_URL}"
        )
        with requests.get(_TRANSLATOR_TOOL_URL) as response:
            response.raise_for_status()
            _TRANSLATOR_TOOL_PATH.parent.mkdir(parents=True, exist_ok=True)
            with _TRANSLATOR_TOOL_PATH.open("wb") as f:
                for chunk in response.iter_content(chunk_size=8096):
                    f.write(chunk)


def _translate_to_cql(
    sq_file_path: Path, cql_mapping_file: Path, mapping_tree_path: Path
) -> str:
    return (
        subprocess.check_output(
            [
                "java",
                "-jar",
                str(_TRANSLATOR_TOOL_PATH),
                *[
                    "translate",
                    "cql",
                    "-m",
                    str(cql_mapping_file.absolute()),
                    "-ct",
                    str(mapping_tree_path.absolute()),
                ],
                str(sq_file_path.absolute()),
            ],
            stderr=subprocess.STDOUT,
        )
        .decode("utf-8")
        .strip()
    )


def _prepare_measure_evaluation(
    sq_file_path: Path,
    fhir_server_url: str,
    cql_mapping_file: Path,
    mapping_tree_file: Path,
) -> str:
    cql_query = _translate_to_cql(sq_file_path, cql_mapping_file, mapping_tree_file)

    library = _create_library(cql_query)
    measure = _create_measure(library)
    bundle = _create_bundle(library, measure)
    try:
        response = requests.post(
            url=fhir_server_url,
            data=bundle.model_dump_json(),
            headers={"Content-Type": "application/fhir+json"},
        )
        response.raise_for_status()
        _logger.debug("Uploaded bundle for measure evaluation")
    except requests.exceptions.RequestException as exc:
        raise IOError(
            f"Failed to upload bundle for measure evaluation. Details: {exc}"
        ) from exc

    return measure.url


@pytest.fixture
def prepared_measure_uri(
    request,
    fhir_server_url: str,
    cql_mapping_file: Path,
    mapping_tree_file: Path,
    translator_tool_exists,
) -> str:
    if not isinstance(request.param, Path):
        raise ValueError(
            f"Fixture 'prepared_measure_uri' expects parameters of type '{type(Path)}', but got '{type(request.param)}'"
        )

    return _prepare_measure_evaluation(
        request.param, fhir_server_url, cql_mapping_file, mapping_tree_file
    )


def pytest_generate_tests(metafunc: Metafunc):
    """
    Generates tests dynamically based on the collected querying metadata files within the project directory
    """
    if "test_evaluate_cql_measure" == metafunc.definition.name:
        with open(
            os.path.join(__test_dir(), "ModuleTestDataConfig.json"),
            mode="r",
            encoding="utf-8",
        ) as f:
            test_data_mapping = json.load(f)
        test_data = []
        for entry in map(
            lambda e: CCDLTestdataEntry.model_validate(e), test_data_mapping
        ):
            marks = []
            if entry.status.disabled:
                marks = [pytest.mark.xfail(reason=entry.status.reason)]
            test_data.append(
                pytest.param(
                    Path(__test_dir(), "test_queries", entry.query),
                    entry.expected,
                    marks=marks,
                    id=entry.query,
                )
            )
        metafunc.parametrize(
            argnames=("prepared_measure_uri", "expected"),
            argvalues=test_data,
            indirect=["prepared_measure_uri"],
        )
