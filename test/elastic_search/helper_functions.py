
import json
import os
import zipfile

import requests

from enum import Enum



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