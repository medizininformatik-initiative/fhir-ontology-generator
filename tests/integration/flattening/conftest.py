import os
import shutil
import subprocess
import tarfile
from pathlib import Path
from typing import Union, Iterator

import requests
from _pytest.fixtures import FixtureRequest
from _pytest.python import Metafunc
from fhir.resources.R4B.bundle import Bundle
from pytest_docker.plugin import Services, get_docker_services

import pytest
from requests import RequestException

import platform

from common.util.log.functions import get_logger
from common.util.project import Project
from common.util.test.docker import save_docker_logs

_logger = get_logger(__name__)


_AETHER_TOOL_PATH = Path(
    os.environ.get("AETHER_TOOL_PATH", Path(__file__).parent / ".tmp" / "aether")
)


def __test_dir() -> str:
    return os.path.dirname(os.path.realpath(__file__))


@pytest.fixture(scope="session")
def test_dir() -> str:
    return __test_dir()


@pytest.fixture(scope="session")
def docker_command() -> str:
    resources_dir = Path(__test_dir()) / "resources"

    dimp_file = resources_dir / "dimp_dup_base.yaml"
    if not dimp_file.exists() or not dimp_file.is_file():
        raise FileNotFoundError(f"Missing dimp_dup_base.yaml file @ {repr(dimp_file)}")

    search_params_file = resources_dir / "custom-search-parameters.json"
    if not search_params_file.exists() or not search_params_file.is_file():
        raise FileNotFoundError(
            f"Missing custom-search-parameters.json @ {repr(search_params_file)}"
        )

    return (
        f"TEST_INTEGRATION_FLATTENING_DIMP_DUP_BASE_FILE={dimp_file.absolute()} "
        f"TEST_INTEGRATION_FLATTENING_CUSTOM_SEARCH_PARAMS_FILE={search_params_file.absolute()} "
        f"docker compose"
    )


@pytest.fixture(scope="session")
def docker_compose_file() -> str:
    return os.path.join(__test_dir(), "docker-compose.yml")


@pytest.fixture(scope="session")
def docker_compose_project_name() -> str:
    return "test_integration_flattening"


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


@pytest.fixture(scope="module")
def pipeline_config(request: FixtureRequest) -> Path:
    """
    Checks if the pipeline config file exits and returns its filesystem path.

    :return: ``pathlib.Path`` object pointing to the pipeline config file
    """
    path = request.path.parent / "resources" / "pipeline-config.yml"
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Missing pipeline config file @ {repr(path)}")
    return path


@pytest.fixture(scope="module")
def aether(request: FixtureRequest) -> Path:
    """
    Checks if `aether` tool is present and downloads it if not

    :return: ``pathlib.Path`` object pointing to the executable
    """
    if _AETHER_TOOL_PATH.exists() and _AETHER_TOOL_PATH.is_file():
        _logger.info(f"Tool aether already present @ {repr(_AETHER_TOOL_PATH)}")
        return _AETHER_TOOL_PATH
    aether_arch = None
    match platform.system():
        case "Linux":
            _logger.info("On Linux 'amd64' is assumed to be the system architecture")
            aether_arch = "linux-amd64"
        case "Darwin":
            match platform.processor():
                case "arm64":
                    aether_arch = "darwin-arm64"
                case _:
                    aether_arch = "darwin-amd64"
        case "Windows":
            if "AETHER_TOOL_PATH" not in os.environ:
                raise KeyError(
                    "There is no release artifact of aether for Windows. You have to compile it yourself and provide a "
                    "path to it via environment variable 'AETHER_TOOL_PATH'"
                )
    if aether_arch:
        aether_tool_url = (
            f"https://github.com/medizininformatik-initiative/aether/releases/download"
            f"/v{os.environ['AETHER_VERSION']}"
            f"/aether-{os.environ['AETHER_VERSION']}-{aether_arch}.tar.gz"
        )
        _logger.info(
            f"Missing aether tool. Downloading executable from {aether_tool_url}"
        )
        with requests.get(aether_tool_url) as response:
            response.raise_for_status()
            _AETHER_TOOL_PATH.parent.mkdir(parents=True, exist_ok=True)
            archive_path = _AETHER_TOOL_PATH.parent / "aether.tar.gz"
            with archive_path.open("wb") as f:
                for chunk in response.iter_content(chunk_size=8096):
                    f.write(chunk)
        with tarfile.open(archive_path, mode="r|gz") as f:
            f.extractall(path=_AETHER_TOOL_PATH.parent, filter="data")
        archive_path.unlink(missing_ok=True)
        aether_tool_path = _AETHER_TOOL_PATH.parent / f"aether-{aether_arch}"
        aether_tool_path = aether_tool_path.rename(
            (_AETHER_TOOL_PATH.parent / f"aether").absolute()
        )
        return aether_tool_path
    else:
        raise FileNotFoundError(
            f"No aether executable exists @ {repr(_AETHER_TOOL_PATH)}"
        )


@pytest.fixture(scope="module")
def jobs_dir(request: FixtureRequest) -> Path:
    """
    Resets the directory where `aether` writes to and provides the path to it.

    :return: ``pathlib.Path`` object pointing to the directory
    """
    path = request.path.parent / ".tmp" / "jobs"
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.fixture(scope="module")
def flattening_lookup(request: FixtureRequest) -> Path:
    """
    Creates a symlink to the flattening lookup file of the given project if it not already exists and returns the path.
    Creating a copy or symlink is required since a fixed location has to be configured in the pipeline config.

    :return: ``pathlib.Path`` object pointing to the flattening lookup file (or its symlink)
    """
    project = Project(request.config.getoption("--project"))
    path = request.path.parent / ".tmp" / "flatteningLookup.json"
    if not path.exists() or not path.is_symlink() or not path.is_file():
        project_path = project.output.flattening / "flatteningLookup.json"
        if not project_path.exists() or not project_path.is_file():
            raise FileNotFoundError(
                f"Missing flattening lookup file in project '{project.name}' @ {repr(project_path)}"
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(project_path, path)
    return path


def _expected_tables(job_dir_path: Path) -> list[Path]:
    if not job_dir_path.exists() or not job_dir_path.is_dir():
        raise FileNotFoundError(f"Missing job directory @ {repr(job_dir_path)}")
    csv_dir = job_dir_path / "csv"
    if csv_dir.exists() and csv_dir.is_dir():
        return [p for p in csv_dir.iterdir() if p.is_file()]
    else:
        return []


def _expected_view_definitions(job_dir_path: Path) -> list[Path]:
    if not job_dir_path.exists() or not job_dir_path.is_dir():
        raise FileNotFoundError(f"Missing job directory @ {repr(job_dir_path)}")
    view_def_dir = job_dir_path / "viewdefinitions"
    if view_def_dir.exists() and view_def_dir.is_dir():
        return [p for p in view_def_dir.iterdir() if p.is_file()]
    else:
        return []


def pytest_generate_tests(metafunc: Metafunc):
    if "test_extraction_pipeline" == metafunc.definition.name:
        jobs_dir = metafunc.definition.path.parent / "resources" / "jobs"
        if not jobs_dir.exists() or not jobs_dir.is_dir():
            raise FileNotFoundError(f"Missing jobs directory @ {repr(jobs_dir)}")
        test_parameters = []
        for job_dir in jobs_dir.iterdir():
            if job_dir.is_dir():
                crtdl_file_path = job_dir / "crtdl.json"
                if not crtdl_file_path.exists() or not crtdl_file_path.is_file():
                    raise FileNotFoundError(
                        f"Missing CRTDL file for job '{job_dir.name}' @ {repr(crtdl_file_path)}"
                    )
                test_parameters.append(
                    pytest.param(
                        crtdl_file_path,
                        (
                            _expected_tables(job_dir),
                            _expected_view_definitions(job_dir),
                        ),
                        id=job_dir.name,
                    )
                )
        metafunc.parametrize(
            argnames=["crtdl", "expected"],
            argvalues=test_parameters,
        )
