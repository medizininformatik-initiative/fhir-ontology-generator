import json
import os
from typing import Mapping

from _pytest.python import Metafunc

import util.requests
import util.test.docker
import logging
import pytest

from model.ResourceQueryingMetaData import ResourceQueryingMetaData
from util.auth.authentication import OAuthClientCredentials
from util.backend.FeasibilityBackendClient import FeasibilityBackendClient

logger = logging.getLogger(__name__)

project_path = os.path.join("example", "mii_core_data_set")
generated_profile_tree_path = os.path.join("example", "fdpg-ontology", "profile_tree.json")


@pytest.fixture(scope="session")
def test_dir() -> str:
    return os.path.dirname(os.path.realpath(__file__))


@pytest.fixture(scope="session")
def docker_compose_file(test_dir: str) -> str:
    yield os.path.join(test_dir, "docker-compose.yml")
    util.test.docker.save_docker_logs()


@pytest.fixture(scope="session")
def backend_ip(docker_services) -> str:
    dataportal_backend_name = "dataportal-backend"
    port = docker_services.port_for(dataportal_backend_name, 8090)
    url = f"http://127.0.0.1:{port}"
    url_health_test=url+"/actuator/health"

    logger.info(f"Waiting for service '{dataportal_backend_name}' to become responsive at {url_health_test}...")
    docker_services.wait_until_responsive(
        timeout=180.0,
        pause=0.1,
        check=lambda: util.requests.is_responsive(url_health_test)
    )
    return url


@pytest.fixture(scope="session")
def fhir_ip(docker_services, test_dir: str) -> str:
    fhir_name = "blaze"
    port = docker_services.port_for(fhir_name, 8080)
    url = f"http://127.0.0.1:{port}"
    url_health_test = url+"/fhir/metadata"

    logger.info(f"Waiting for service '{fhir_name}' to become responsive at {url_health_test}...")
    docker_services.wait_until_responsive(
        timeout=90.0,
        pause=0.1,
        check=lambda: util.requests.is_responsive(url_health_test)
    )

    # upload testdata for fhir server for testing
    #get_and_upload_test_data(url, test_dir)
    return url


@pytest.fixture(scope="session")
def elastic_ip(docker_services) -> str:
    elastic_name="dataportal-elastic"
    port = docker_services.port_for(elastic_name, 9200)
    url = f"http://127.0.0.1:{port}"

    logger.info(f"Waiting for service '{elastic_name}' to be responsive at {url}...")
    docker_services.wait_until_responsive(
        timeout=90.0,
        pause=0.1,
        check=lambda: util.requests.is_responsive(url)
    )
    return url


@pytest.fixture(scope="session")
def backend_client() -> FeasibilityBackendClient:
    auth = OAuthClientCredentials(
        client_credentials=(os.environ['CLIENT_ID'], os.environ['CLIENT_SECRET']),
        user_credentials=(os.environ['USERNAME'], os.environ['PASSWORD']),
        token_access_url=os.environ['TOKEN_ACCESS_URL']
    )
    return FeasibilityBackendClient(
        base_url="http://localhost:8091/api/v4",
        auth=auth
    )


@pytest.fixture(scope="session")
def querying_metadata_files() -> list[ResourceQueryingMetaData]:
    modules_dir_path = os.path.join(project_path, "CDS_Module")
    metadata_list = []
    for module_dir in os.listdir(modules_dir_path): # ../CDS_Modules/*
        if os.path.isdir(module_dir):
            metadata_dir_path = os.path.join(modules_dir_path, module_dir, "QueryingMetaData")
            for file in metadata_dir_path: # ../CDS_Modules/*/QueryingMetaData/*.json
                if file.endswith(".json"):
                    with open(os.path.join(modules_dir_path, file), "r", encoding="utf8") as f:
                        metadata_list.append(json.load(f))
    return metadata_list


@pytest.fixture(scope="session")
def profile_tree() -> Mapping[str, any]:
    try:
        with open(file=generated_profile_tree_path, mode='r', encoding='utf8') as file:
            return json.load(file)
    except Exception as exc:
        logger.error(f"Failed to load generated profile tree file @{generated_profile_tree_path}. Reason: {exc}",
                     exc_info=exc)


def pytest_prepare_module_tests(metafunc: Metafunc, querying_metadata_files: list[ResourceQueryingMetaData]):
    log_str = ', '.join(map(lambda x: str(x.module) + "-" + str(x.name), querying_metadata_files))
    logger.info(f"Detected {len(querying_metadata_files)} Querying Metadata files [{log_str}]")
    metafunc.parametrize("querying_metadata", querying_metadata_files)