import os
import zipfile

import pytest
import requests
import logging

import util.test.docker
import util.requests


logger = logging.getLogger(__name__)


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


def get_and_upload_test_data(fhir_url, test_dir_path: str,
                             repo_url="https://github.com/medizininformatik-initiative/mii-testdata/releases/download/v1.0.1/kds-testdata-2024.0.1.zip"):
    """
    Helper function which downloads the testdata from the specified repository, unpacks it and uploads it to the specified fhir_url server
    :param fhir_url: url of fhir which to upload the test data to

    :param repo_url: url of repository which to download the testdata from
    """
    response = requests.get(repo_url, timeout=5)
    zip_path = os.path.join("kds-testdata-2024.0.1.zip")
    with open(zip_path, 'wb') as file:
        file.write(response.content)
    test_data_dir_path = os.path.join(test_dir_path, "testdata")
    os.makedirs(test_data_dir_path, exist_ok=True)
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(test_data_dir_path)
    logger.info("Downloaded testdata successfully")

    # will be replaced so it uses middleware in backend
    resource_dir = os.path.join(test_data_dir_path,"kds-testdata-2024.0.1","resources")
    for file_name in os.listdir(resource_dir):
        if file_name.endswith(".json"):
            with open(os.path.join(resource_dir, file_name), "r", encoding="utf-8") as f:
                data = f.read()
            response = requests.post(
                f"{fhir_url}",
                headers={"Content-Type": "application/fhir+json"},
                data=data.encode("utf-8"),
                timeout=10)
            logger.info(f"Uploaded {file_name} with status code:  {response.status_code}")
    return True


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
    get_and_upload_test_data(url, test_dir)
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
