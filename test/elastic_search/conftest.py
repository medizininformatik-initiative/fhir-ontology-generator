import pytest
import json
import os
import zipfile

import requests

from enum import Enum


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








def get_and_upload_test_data_to_fhir(fhir_url, repo_url="https://github.com/medizininformatik-initiative/mii-testdata/releases/download/v1.0.1/kds-testdata-2024.0.1.zip"):
    """
    Helper function which downloads the testdata from the specified repository, unpacks it and uploads it to the specified fhir_url server
    :param fhir_url: url of fhir which to upload the test data to
    :param repo_url: url of repository which to download the testdata from
    """

    # only here because importing doesn't work as expected
    class BundleType(Enum):
        DOCUMENT = "document"
        MESSAGE = "message"
        TRANSACTION = "transaction"
        TRANSACTION_RESPONSE = "transaction-response"
        BATCH = "batch"
        BATCH_RESPONSE = "batch-response"
        HISTORY = "history"
        SEARCHSET = "searchset"
        COLLECTION = "collection"
    def create_bundle(bundle_type: BundleType):
        return {
            "resourceType": "Bundle",
            "type": bundle_type.value,
            "entry": []
        }

    response = requests.get(repo_url, timeout=5)
    zip_path = "kds-testdata-2024.0.1.zip"
    with open(zip_path, 'wb') as file:
        file.write(response.content)
    os.makedirs("testdata", exist_ok=True)
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall("testdata")
    print("Downloaded testdata successfully")

    # will be replaced so it uses middleware in backend
    resource_dir = os.path.join("testdata","kds-testdata-2024.0.1","resources")
    for file_name in os.listdir(resource_dir):
        if file_name.endswith(".json"):
            with open(os.path.join(resource_dir, file_name), "r", encoding="utf-8") as f:
                data = f.read()
                json_data = json.loads(data)

            resource_type = json_data.get("resourceType")

            if resource_type != "Bundle":
                resource_url = resource_type
                resource_bundle = create_bundle(BundleType.TRANSACTION)
                resource_bundle["entry"] = {
                    "resource": json_data,
                    "request": {
                        "method": "POST",
                        "url": resource_url
                    }
                }
                data = json.dumps(resource_bundle)

            response = requests.post(
                f"{fhir_url}/fhir",
                headers={"Content-Type": "application/fhir+json"},
                data=data.encode("utf-8"),
                timeout=10)
            print(f"Uploaded {file_name} with status code:  {response.status_code}")
    return True