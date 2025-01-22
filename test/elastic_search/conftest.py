import pytest
import requests

from helper_functions import get_and_upload_test_data_to_fhir


@pytest.fixture(scope="session")
def docker_compose_file():
    return "docker-compose.yml"

def is_responsive(url) -> bool:
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return True
        print(f"Got Status-Code: {response.status_code} from url: {url}")
    except requests.RequestException:
        pass
    return False

@pytest.fixture(scope="session")
def backend_ip(docker_services):
    dataportal_backend_name = "dataportal-backend"
    port = docker_services.port_for(dataportal_backend_name, 8090)
    url = f"http://127.0.0.1:{port}"
    url_health_test=url+"/actuator/health"

    print(f"Waiting for service '{dataportal_backend_name}' to become responsive at {url_health_test}...")
    docker_services.wait_until_responsive(
        timeout=180.0,
        pause=0.1,
        check=lambda: is_responsive(url_health_test)
    )
    return url

@pytest.fixture(scope="session")
def fhir_ip(docker_services):
    fhir_name = "blaze"
    port = docker_services.port_for(fhir_name, 8080)
    url = f"http://127.0.0.1:{port}"
    url_health_test = url+"/fhir/metadata"

    print(f"Waiting for service '{fhir_name}' to become responsive at {url_health_test}...")
    docker_services.wait_until_responsive(
        timeout=90.0,
        pause=5,
        check=lambda: is_responsive(url_health_test)
    )
    # upload testdata for fhir server for testing
    get_and_upload_test_data_to_fhir(url)
    return url

@pytest.fixture(scope="session")
def elastic_ip(docker_services):
    elastic_name="dataportal-elastic"
    port = docker_services.port_for(elastic_name, 9200)
    url = f"http://127.0.0.1:{port}"

    print(f"Waiting for service '{elastic_name}' to be responsive at {url}...")
    docker_services.wait_until_responsive(
        timeout=90.0,
        pause=0.1,
        check=lambda: is_responsive(url)
    )
    return url

