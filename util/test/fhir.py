import json
import os
import logging
import zipfile

import requests

from util.fhir.FhirUtil import create_bundle, BundleType

logger = logging.getLogger(__name__)

def download_and_unzip_kds_test_data(target_folder="testdata",download_url="https://github.com/medizininformatik-initiative/mii-testdata/releases/download/v1.0.1/kds-testdata-2024.0.1.zip")->bool:
    """
    Downloads testdata from GitHub repository and stores it in the specified location.
    :param target_folder: The folder to save the downloaded zip files.
    :param download_url: The url to download the zip files from.
    """

    # TODO: make the output folder independent:
    # instead of: testdata -> kds-testdata-2024.0.1 -> resources -> [files]
    # rather do: testdata -> resources -> [files]
    response = requests.get(download_url, timeout=5)
    zip_path = "kds-testdata-2024.0.1.zip"
    with open(zip_path, 'wb') as file:
        file.write(response.content)
    os.makedirs(target_folder, exist_ok=True)
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(target_folder)
    os.remove(zip_path)
    print("Downloaded testdata successfully")
    return True

def load_bundle_onto_fhir_server(fhir_api: str, bundle: dict) -> bool:
    """
    Loads given bundle onto the FHIR server.
    :param fhir_api: The FHIR API endpoint. example= http://localhost:8083/fhir
    :param bundle: The bundle to load.
    """
    try:
        response = requests.post(
            f"{fhir_api}",
            headers={"Content-Type": "application/fhir+json"},
            data=json.dumps(bundle).encode("utf-8"),
            timeout=10)
        if response.status_code == 200:
            return True

        print(f"Request failed with status code: {response.status_code} because {response.reason}")
        return False
    except Exception as e:
        print(e)
    return False

def load_list_of_resources_onto_fhir_server(fhir_api:str, files:list[str], testdata_folder:str):
    resource_bundle = create_bundle(BundleType.TRANSACTION)
    for resource_file in files:
        with open(os.path.join(testdata_folder,resource_file), "r", encoding="utf-8") as f:
            json_data = json.loads(f.read())

        resource_url = json_data.get("resourceType")+"/"+json_data.get("id")
        resource_bundle["entry"].append({
            "resource": json_data,
            "request": {
                "method": "PUT",
                "url": resource_url
            }
        })
    return load_bundle_onto_fhir_server(fhir_api, resource_bundle)


def delete_list_of_resources_from_fhir_server(fhir_api:str, fhir_resources:list[str]):
    resource_bundle = create_bundle(BundleType.TRANSACTION)
    for resource in fhir_resources:
        resource_type = resource.split("-")[0]
        resource_id = resource.split("-",1)[-1].split(".")[0]

        resource_url = resource_type+"/"+resource_id
        resource_bundle["entry"].append({
            "request": {
                "method": "DELETE",
                "url": resource_url
            }
        })
    return load_bundle_onto_fhir_server(fhir_api, resource_bundle)


def delete_from_fhir_server(fhir_api: str, resource_type:str ,resource_id: str):
    url = f"{fhir_api}/{resource_type}/{resource_id}"
    try:
        response = requests.delete(url, timeout=5)
        if response.status_code == 204:
            print(f"Deleted {url}")
        else:
            print(f"Error while deleting: {resource_type}-{resource_id}: {response.status_code}. Reason: {response.reason}")
    except Exception as e:
        print(f"Error while deleting {url}: {e}")
    return False