import json
import os
import random
import shutil
import time
from collections import defaultdict
from os import PathLike
from typing import Mapping, Union

from _pytest.config import Parser
from _pytest.python import Metafunc

import util.requests
import util.test.docker
import logging
import pytest

from model.ResourceQueryingMetaData import ResourceQueryingMetaData
from model.UiDataModel import TermCode
from util.http.auth.authentication import OAuthClientCredentials
from util.http.backend.FeasibilityBackendClient import FeasibilityBackendClient
from util.http.terminology.FhirTerminologyClient import FhirTerminologyClient
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
    # Copy elastic files over such that they can be mounted
    tmp_path = os.path.join(__test_dir(), "tmp")
    os.makedirs(tmp_path, exist_ok=True)
    shutil.copyfile(os.path.join(pytestconfig.rootpath, "example", "fdpg-ontology", "elastic.zip"),
                    os.path.join(tmp_path, "elastic.zip"))
    yield os.path.join(__test_dir(), "docker-compose.yml")
    util.test.docker.save_docker_logs()


@pytest.fixture(scope="session")
def docker_setup(pytestconfig) -> Union[list[str], str]:
    return ["up --build -d --wait"]


@pytest.fixture(scope="session")
def backend_ip(docker_services) -> str:
    dataportal_backend_name = "dataportal-backend"
    port = docker_services.port_for(dataportal_backend_name, 8090)
    url = f"http://127.0.0.1:{port}"
    url_health_test=url+"/actuator/health"

    logger.info(f"Waiting for service '{dataportal_backend_name}' to become responsive at {url_health_test}...")
    docker_services.wait_until_responsive(
        timeout=180.0,
        pause=5,
        check=lambda: util.requests.is_responsive(url_health_test)
    )
    #time.sleep(10)
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
        pause=5,
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
        pause=5,
        check=lambda: util.requests.is_responsive(url)
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
    if download:
        download_and_unzip_kds_test_data(target_folder=test_dir)
    return os.path.join(test_dir, "testdata")


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


'''
@pytest.fixture(scope="session")
def snapshot_list() -> list[Mapping[str, any]]:
    modules_dir_path = os.path.join(project_path, "CDS_Module")
    snapshot_list = []
    for module_dir in os.listdir(modules_dir_path):  # ../CDS_Modules/*
        if os.path.isdir(module_dir):
            metadata_dir_path = os.path.join(modules_dir_path, module_dir, "differential", "package")
            for file in metadata_dir_path:  # ../CDS_Modules/*/differential/package/*snapshot.json
                if file.endswith("snapshot.json"):
                    with open(os.path.join(modules_dir_path, file), "r", encoding="utf8") as f:
                        snapshot_list.append(json.load(f))
    return snapshot_list


def pytest_generate_tests(metafunc: Metafunc):
    """
    Generates tests dynamically based on the collected querying metadata files within the project directory
    """
    qm_list = __querying_metadata_list()

    if "test_criterion_definition_validity" == metafunc.definition.name:
        schema = __querying_metadata_schema(__test_dir())
        metafunc.parametrize(argnames=("querying_metadata", "querying_metadata_schema"),
                             argvalues=[(instance, schema) for instance in qm_list],
                             ids=[querying_metadata_id_fn(it) for it in qm_list], scope="session")

    if "test_criterion_term_code_search" == metafunc.definition.name:
        backend_client = __backend_client()
        terminology_client = __terminology_client(__term_server_(metafunc.config))
        metafunc.parametrize(argnames=("querying_metadata", "backend_client", "terminology_client"),
                             argvalues=[(instance, backend_client, terminology_client) for instance in qm_list],
                             ids=[querying_metadata_id_fn(it) for it in qm_list], scope="session")


def pytest_addoption(parser: Parser):
    # Certificate used to authenticate with the terminology server
    parser.addoption("--tsc", dest="term_server_certificate", action="store", default="certificate.pem")
    # Private key used to authenticate with the terminology server
    parser.addoption("--tsk", dest="term_server_private_key", action="store", default="private-key.pem")


def load_snapshots_for_querying_metadata(querying_metadata: ResourceQueryingMetaData) -> list[Mapping[str, any]]:
    module_snapshot_dir_path = os.path.join(project_path, "CDS_Module", querying_metadata.backend.display, "differential",
                                            "package")
    if not os.path.isdir(module_snapshot_dir_path):
        raise NotADirectoryError(f"Missing directory @{module_snapshot_dir_path}")
    else:
        snapshots = []
        for file_name in os.listdir(module_snapshot_dir_path):
            if file_name.endswith("snapshot.json"):
                with open(os.path.join(module_snapshot_dir_path, file_name), mode="r", encoding="utf8") as f:
                    snapshots.append(json.load(f))
        return snapshots


def get_binding_value_set_url(element_defining_id: str, snapshot: Mapping[str, any]) -> str | None:
    """
    Get the binding value set URL for an element defined by the passed element ID and contained in the snapshot

    :param element_defining_id: ID of the element to retrieve the binding for
    :param snapshot: Profile snapshot to search the element in
    :return: Either the URL of the binding value set or None if there is no such element or binding
    """
    from core import StructureDefinitionParser
    try:
        elem = StructureDefinitionParser.get_element_from_snapshot(snapshot, element_defining_id)
        return StructureDefinitionParser.get_binding_value_set_url(elem)
    except Exception as exc:
        raise LookupError(f"Could not find binding value set URL for element [id='{element_defining_id}']", exc)


def get_random_concept_set_for_value_set(url: str, client: FhirTerminologyClient,
                                         max_size: int = 5) -> list[Mapping[str, any]]:
    expanded_vs = client.expand_value_set(url=url)
    if "expansion" not in expanded_vs:
        raise KeyError(f"Expected value set '{url}' to be in expanded form but found no element 'expansion'")
    expansion = expanded_vs.get("expansion", []).get("contains", [])
    return random.choices(expansion, k=min(max_size, len(expansion)))


def get_term_code_set_for_querying_metadata(querying_metadata: ResourceQueryingMetaData,
                                            client: FhirTerminologyClient, max_size: int = 5) -> list[TermCode]:
    """
    There are three cases to consider for any querying metadata profile:

    - If it has a 'term_codes' attribute then the entire code list is used regardless of 'max_size'
    - Else if it has a 'term_code_defining_id' attribute then the process is more complex. First the corresponding
      snapshot is loaded and the 'term_code_defining_id' is resolved to the element with the same ID in the snapshot.
      Afterward the value set binding defined by the ElementDefinition instance is retrieved to expand the value set
      using a FHIR terminology server. From the expanded value set a random set of codings is extracted and returned.
      The logic does support multiple snapshots matching with multiple value sets defining the value range. In such
      cases the results are aggregated and codings randomly selected from the aggregate respecting the limit set by
      'max_size'
    - Else
    """
    if querying_metadata.term_codes:
        return querying_metadata.term_codes
    elif querying_metadata.term_code_defining_id:
        snapshots = load_snapshots_for_querying_metadata(querying_metadata)
        term_codes = set()
        vs_urls = set([get_binding_value_set_url(querying_metadata.term_code_defining_id, snapshot)
                              for snapshot in snapshots])
        for vs_url in vs_urls:
            term_codes.update([TermCode(c['system'], c['code'], c['display'])
                               for c in get_random_concept_set_for_value_set(vs_url, client, max_size)])

        return random.choices(list(term_codes), k=max_size)
    else:
        raise KeyError("Expected one of {'term_codes', 'term_code_defining_id'} to be present in querying metadata "
                       f"profile '{querying_metadata.backend.code}#{querying_metadata.name}'. This should have been "
                       f"caught by schema validation")
'''