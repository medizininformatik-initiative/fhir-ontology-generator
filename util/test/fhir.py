import json
import os
import logging
import zipfile

import requests

from util.FhirUtil import create_bundle, BundleType

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
        zip_ref.extractall("testdata")
    print("Downloaded testdata successfully")
    return True

def load_bundle_onto_fhir_server(fhir_api: str, bundle: dict):
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
            return response
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

def load_single_resource_onto_fhir_server(fhir_api: str, file_path:str)->bool:
    """
    Uploads resource onto fhir server. In the process the resource is converted to a bundle
    :param fhir_api: The FHIR API endpoint.
    :param file_path: The path to the resource file.
    """
    with open(file_path,"r", encoding="utf-8") as f:
        data = f.read()
        json_data = json.loads(data)
    resource_type = json_data.get("resourceType")
    if resource_type != "Bundle":
        resource_url = resource_type
        resource_bundle = create_bundle(BundleType.TRANSACTION)
        resource_bundle["entry"] = {
            "resource": json_data,
            "request": {
                "method": "PUT",
                "url": resource_url
            }
        }
        data = resource_bundle
    return load_bundle_onto_fhir_server(fhir_api, data)

def upload_bundles_from_dir(fhir_api: str,testdata_folder: str):
    """
    Uploads all resources from specified folder to FHIR server.
    :param fhir_api: The FHIR API endpoint.
    :param testdata_folder: Location of testdata folder. (not the resources folder, but 2 level higher up)
    """
    resource_dir = os.path.join(testdata_folder, "kds-testdata-2024.0.1", "resources")
    for file_name in os.listdir(resource_dir):
        if file_name.endswith(".json"):
            load_single_resource_onto_fhir_server(fhir_api, os.path.join(resource_dir, file_name))

def delete_from_fhir_server(fhir_api: str, resource_type:str ,resource_id: str):
    url = f"{fhir_api}/{resource_type}/{resource_id}"
    try:
        response = requests.delete(url, timeout=5)
        if response.status_code == 204:
            logger.info(f"Deleted {url}")
    except Exception as e:
        logger.info(f"Error while deleting {url}: {e}")
    return False