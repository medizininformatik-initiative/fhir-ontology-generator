import importlib.resources
import os
import shutil
import time
from pathlib import Path
from pydoc import resolve
from typing import Union, Iterator

import docker
import psycopg2
import pytest
from docker.models.containers import Container
from psycopg2 import OperationalError
from psycopg2._psycopg import connection
from pytest_docker.plugin import Services, get_docker_services

from common.util.log.functions import get_logger
from common.util.project import Project
from common.util.test.docker import save_docker_logs

import common.resources.sql as sql_resources


logger = get_logger(__name__)


def __test_dir() -> Path:
    return Path(os.path.dirname(os.path.realpath(__file__))).resolve()


@pytest.fixture(scope="session")
def test_dir() -> Path:
    return __test_dir()


@pytest.fixture(scope="session")
def database_container_name() -> str:
    return "integrity-database-test_postgres"


@pytest.fixture(scope="session")
def docker_compose_file(pytestconfig) -> str:
    project = Project(name=pytestconfig.getoption("--project"))

    tmp_path = Path(__test_dir(), "tmp")
    if os.path.exists(tmp_path):
        shutil.rmtree(tmp_path)
        os.makedirs(tmp_path, exist_ok=True)

    # Unpack backend archive and keep SQL dump files
    backend_archive_path = project.output.generated_ontology / "backend.zip"
    shutil.unpack_archive(backend_archive_path, tmp_path)
    for file_name in os.listdir(tmp_path):
        if not file_name.endswith(".sql"):
            path = Path(tmp_path, file_name)
            if path.is_dir(): path.rmdir()
            else: path.unlink(missing_ok=True)

    # Copy database init file
    with importlib.resources.path(sql_resources, 'init.sql') as init_script_path:
        shutil.copyfile(init_script_path, tmp_path / 'init.sql')

    yield os.path.join(__test_dir(), "docker-compose.yml")


@pytest.fixture(scope="session")
def docker_setup(pytestconfig) -> Union[list[str], str]:
    return ["up --build -d --wait"]


@pytest.fixture(scope="session")
def docker_cleanup() -> Union[list[str], str]:
    return ["down -v"]


@pytest.fixture(scope="session")
def docker_services(
    docker_compose_command: str,
    docker_compose_file: Union[list[str], str],
    docker_compose_project_name: str,
    docker_setup: str,
    docker_cleanup: str,
) -> Iterator[Services]:
    # We overwrite this fixture to allow for the Docker container logs to be saved before `pytest-docker` removes them
    with get_docker_services(
        docker_compose_command,
        docker_compose_file,
        docker_compose_project_name,
        docker_setup,
        docker_cleanup,
    ) as docker_service:
        yield docker_service
        save_docker_logs(str(__test_dir()), "integrity-database-test")


@pytest.fixture(scope="session")
def database_container(docker_services, database_container_name) -> Container:
    client = docker.from_env()
    return client.containers.get(database_container_name)


@pytest.fixture(scope="session")
def database_conn(docker_services) -> connection:
    dataportal_backend_name = "test-postgres"
    port = docker_services.port_for(dataportal_backend_name, 5432)

    def healthcheck():
        try:
            psycopg2.connect(
                dbname="database",
                user="admin",
                password="admin",
                host="localhost",
                port=port,
            ).close()
            return True
        except OperationalError as err:
            logger.debug(f"Connection failed. Reason: {err}")
            return False

    logger.info(f"Waiting for service '{dataportal_backend_name}' to become responsive at localhost:{port} ...")
    docker_services.wait_until_responsive(
        timeout=300.0,
        pause=5,
        check=lambda: healthcheck()
    )
    return psycopg2.connect(
        dbname="database",
        user="admin",
        password="admin",
        host="localhost",
        port=port,
    )


@pytest.fixture(scope="session")
def dse_profile_sql_import(docker_services, test_dir: Path) -> Path:
    return test_dir / "tmp" / "R__Load_latest_dse_profiles.sql"


@pytest.fixture(scope="session")
def ui_profile_sql_import(docker_services, test_dir: Path) -> Path:
    return test_dir / "tmp" / "R__Load_latest_ui_profiles.sql"


def import_sql_file(file_path: Path, conn: connection, cont: Container):
    logger.debug(f"Importing SQL data from {file_path}")
    cmd = f"sh -c 'psql -U {conn.info.user} -d {conn.info.dbname} < {file_path.as_posix()}'"
    result = cont.exec_run(cmd=cmd)
    if result.exit_code != 0:
        logger.warning(f"Import failed [exit_code={result.exit_code}, output='{result.output}']")
    else:
        logger.debug(f"Import completed [output='{str(result.output)}']")

@pytest.fixture(scope="session")
def database(database_conn, database_container) -> connection:
    logger.info("Initializing database")
    import_sql_file(Path('/tmp', 'sql', 'init.sql'), database_conn, database_container)

    logger.info("Importing DSE profile data")
    import_sql_file(Path('/tmp', 'sql', 'R__load_latest_dse_profiles.sql'), database_conn, database_container)

    logger.info("Importing UI profile data")
    import_sql_file(Path('/tmp', 'sql', 'R__Load_latest_ui_profile.sql'), database_conn, database_container)

    return database_conn
