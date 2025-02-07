import json
import os
import shutil
from collections import defaultdict
from os import PathLike, mkdir
from typing import Mapping, Union, Iterator

from _pytest.python import Metafunc
from pytest_docker.plugin import Services, get_docker_services, containers_scope

import util.http.requests
import util.test.docker
import logging
import pytest

from model.ResourceQueryingMetaData import ResourceQueryingMetaData
from util.http.auth.authentication import OAuthClientCredentials
from util.http.backend.FeasibilityBackendClient import FeasibilityBackendClient
from util.test.fhir import download_and_unzip_kds_test_data

logger = logging.getLogger(__name__)

#generated_profile_tree_path = os.path.join("example", "fdpg-ontology", "profile_tree.json")
#project_path = os.path.join("example", "mii_core_data_set")


def __test_dir() -> str:
    return os.path.dirname(os.path.realpath(__file__))


@pytest.fixture(scope="session")
def test_dir() -> str:
    return __test_dir()


def __project_root_dir(request) -> str:
    return request.config.rootpath


@pytest.fixture(scope="session")
def project_root_dir(request) -> str:
    return __project_root_dir(request)


@pytest.fixture(scope="session")
def docker_compose_file(pytestconfig) -> str:
    tmp_path = os.path.join(__test_dir(), "tmp")
    if os.path.exists(tmp_path):
        shutil.rmtree(tmp_path)
    ontology_dir_path = os.path.join(tmp_path, "ontology")
    os.makedirs(ontology_dir_path, exist_ok=True)

    # Copy and unpack ontology archives
    backend_path = os.path.join(tmp_path, "backend.zip")
    shutil.copyfile(os.path.join(pytestconfig.rootpath, "example", "fdpg-ontology", "backend.zip"), backend_path)
    shutil.unpack_archive(backend_path, ontology_dir_path)

    migration_path = os.path.join(ontology_dir_path, "migration")
    os.makedirs(migration_path, exist_ok=True)
    for file_name in os.listdir(ontology_dir_path):
        if file_name.endswith(".sql"):
            shutil.move(os.path.join(ontology_dir_path, file_name), migration_path)

    dse_dir_path = os.path.join(ontology_dir_path, "dse")
    os.makedirs(dse_dir_path)
    shutil.move(os.path.join(ontology_dir_path, "profile_tree.json"), dse_dir_path)

    mapping_path = os.path.join(tmp_path, "mapping.zip")
    shutil.copyfile(os.path.join(pytestconfig.rootpath, "example", "fdpg-ontology", "mapping.zip"), mapping_path)
    shutil.unpack_archive(mapping_path, ontology_dir_path)

    unpacked_dir_path = os.path.join(ontology_dir_path, "mapping")
    shutil.move(os.path.join(unpacked_dir_path, "cql", "mapping_cql.json"),
                os.path.join(ontology_dir_path, "mapping_cql.json"))
    shutil.move(os.path.join(unpacked_dir_path, "fhir", "mapping_fhir.json"),
                os.path.join(ontology_dir_path, "mapping_fhir.json"))
    shutil.move(os.path.join(unpacked_dir_path, "dse_mapping_tree.json"),
                os.path.join(ontology_dir_path, "dse_mapping_tree.json"))
    shutil.move(os.path.join(unpacked_dir_path, "mapping_tree.json"),
                os.path.join(ontology_dir_path, "mapping_tree.json"))
    shutil.rmtree(unpacked_dir_path)

    # Copy elastic archive
    shutil.copyfile(os.path.join(pytestconfig.rootpath, "example", "fdpg-ontology", "elastic.zip"),
                    os.path.join(tmp_path, "elastic.zip"))

    yield os.path.join(__test_dir(), "docker-compose.yml")
    #util.test.docker.save_docker_logs(__test_dir(), "integration-test")


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
        util.test.docker.save_docker_logs(__test_dir(), "integration-test")


@pytest.fixture(scope="session")
def backend_ip(docker_services) -> str:
    dataportal_backend_name = "dataportal-backend"
    port = docker_services.port_for(dataportal_backend_name, 8090)
    url = f"http://127.0.0.1:{port}"
    url_health_test=url+"/actuator/health"

    logger.info(f"Waiting for service '{dataportal_backend_name}' to become responsive at {url_health_test}...")
    docker_services.wait_until_responsive(
        timeout=300.0,
        pause=5,
        check=lambda: util.http.requests.is_responsive(url_health_test)
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
        timeout=300.0,
        pause=5,
        check=lambda: util.http.requests.is_responsive(url_health_test)
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
        timeout=300.0,
        pause=5,
        check=lambda: util.http.requests.is_responsive(url)
    )
    return url


def __backend_client() -> FeasibilityBackendClient:
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
def backend_client() -> FeasibilityBackendClient:
    return __backend_client()


@pytest.fixture(scope="session")
def fhir_testdata(fhir_ip, test_dir, download=True):
    target_dir_path = os.path.join(test_dir, "testdata")
    if download:
        download_and_unzip_kds_test_data(target_dir_path)
    return target_dir_path


def __querying_metadata_schema(test_dir: Union[str, PathLike]) -> Mapping[str, any]:
    with open(file=os.path.join(test_dir, "querying_metadata.schema.json"), mode="r", encoding="utf8") as file:
        return json.load(file)


@pytest.fixture(scope="session")
def querying_metadata_schema(test_dir: Union[str, PathLike]) -> Mapping[str, any]:
    return __querying_metadata_schema(test_dir)


def __querying_metadata_list(project_root_dir: Union[str, PathLike]) -> list[ResourceQueryingMetaData]:
    modules_dir_path = os.path.join(project_root_dir, "example", "mii_core_data_set", "CDS_Module")
    metadata_list = []
    for module_dir in os.listdir(modules_dir_path): # ../CDS_Modules/*
        metadata_dir_path = os.path.join(modules_dir_path, module_dir, "QueryingMetaData")
        for file in os.listdir(metadata_dir_path): # ../CDS_Modules/*/QueryingMetaData/*.json
            if file.endswith(".json"):
                with open(os.path.join(metadata_dir_path, file), "r", encoding="utf8") as f:
                    metadata_list.append(ResourceQueryingMetaData.from_json(f))
    return metadata_list


def querying_metadata_list(project_root_dir: Union[str, PathLike]) -> list[ResourceQueryingMetaData]:
    return __querying_metadata_list(project_root_dir)


def querying_metadata_id_fn(val):
    """
    Generates test IDs for QueryingMetadata test parameters based on their backend and name
    """
    if isinstance(val, ResourceQueryingMetaData):
        return f"{val.module.code}::{val.name}"


def search_response_id_fn(response: Mapping[str, any]) -> str:
    entry = response['results'][0]
    return f"{entry['kdsModule']}#{entry['context']}#{entry['terminology']}"


def __load_search_responses() -> Mapping[str, list[Mapping[str, any]]]:
    data_path = os.path.join(__test_dir(), "search-responses")
    responses = defaultdict(list)
    for file_name in os.listdir(data_path):
        if file_name.endswith(".json"):
            with open(os.path.join(data_path, file_name), mode="r", encoding="utf8") as f:
                response = json.load(f)
                responses[search_response_id_fn(response)].append(response)
    return responses


def pytest_generate_tests(metafunc: Metafunc):
    """
    Generates tests dynamically based on the collected querying metadata files within the project directory
    """
    qm_list = __querying_metadata_list(metafunc.config.rootpath)


    if "test_ccdl_query" == metafunc.definition.name:
        with open(os.path.join(__test_dir(), "ModuleTestDataConfig.json"), "r", encoding="utf-8") as f:
            test_data = json.load(f)
        metafunc.parametrize(argnames=("data_resource_file", "query_resource_path"),
                             argvalues=test_data)

    if "test_criterion_definition_validity" == metafunc.definition.name:
        schema = __querying_metadata_schema(__test_dir())
        metafunc.parametrize(argnames=("querying_metadata", "querying_metadata_schema"),
                             argvalues=[(instance, schema) for instance in qm_list],
                             ids=[querying_metadata_id_fn(it) for it in qm_list], scope="session")

    if "test_criterion_term_code_search" == metafunc.definition.name:
        backend_client = __backend_client()
        responses_map = __load_search_responses()
        metafunc.parametrize(argnames=("expected_responses", "backend_client"),
                             argvalues=[(responses, backend_client) for responses in responses_map.values()],
                             ids=[key for key in responses_map.keys()], scope="session")
