import json
import os
import logging
import zipfile
from enum import Enum
from typing import List, Tuple, Optional

import requests
from fhir.resources.R4B.operationoutcome import OperationOutcome, OperationOutcomeIssue
from typing_extensions import TypedDict, Mapping
from urllib3 import add_stderr_logger

from util.fhir.bundle import create_bundle, BundleType

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
    logger.debug("Downloaded testdata successfully")
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
            response_bundle = response.json()
            # TODO: Use request specific checking of response status code, e.g. only 201 for POST requests
            result = check_response_bundle(response_bundle, {200, 201, 204})
            if not result[0]:
                oo_str = result[1].model_dump_json() if result[1] else ""
                logger.warning(f"Request failed (partially). Reason: {oo_str}")
                return False
            return True
        else:
            logger.warning(f"Request failed with status code: {response.status_code} because {response.reason}")
            return False
    except Exception as exc:
        logger.error(f"Bundle upload to server @ {fhir_api} failed", exc_info=exc)
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


def delete_list_of_resources_from_fhir_server(fhir_api:str, fhir_resources: list[str]):
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


def check_response_bundle(bundle: dict, expected_status_codes: set[int]) -> Tuple[bool, Optional[OperationOutcome]]:
    """
    Validates a response bundle received after submitting transaction or batch type Bundle resources to a FHIR server by
    iterating over the Bundle.entry.response elements and checking the status code as well as request outcome
    information provided by the server itself
    :param bundle: Response Bundle resource which has to be of type 'transaction-response' or 'batch-response'
    :param expected_status_codes: Range of expected response status codes for the individual requests
    :return: Tuple of a boolean indicating the request success as indicated by the response bundle and an
             OperationOutcome resource with the aggregated issues identified during validation
    """
    bundle_type = bundle.get('type', None)
    allowed_bundle_types = {"transaction-response", "batch-response"}
    if bundle_type not in allowed_bundle_types:
        logger.warning(f"Bundle type has to be one of {allowed_bundle_types} to be eligible for validation")
        return True, None
    entries = bundle.get('entry', [])
    if len(entries) == 0:
        logger.warning("Bundle has no entries to validate")
        return True, None
    valid = True
    oo = OperationOutcome(issue=[])
    for idx, entry in enumerate(bundle.get('entry', [])):
        response = entry.get('response', None)
        if response is None:
            oo.issue.append(OperationOutcomeIssue(
                severity="warning", code="processing", diagnostics="No 'response' element in bundle entry",
                location=[f"Bundle.entry[{idx}]"]
            ))
        else:
            status = int(response['status']) if 'status' in response else None
            if status not in expected_status_codes:
                valid = False
                oo.issue.append(OperationOutcomeIssue(
                    severity="error", code="value",
                    diagnostics=f"Status code not in expected range [status_code={status}, "
                                f"range={expected_status_codes}]",
                    location=[f"Bundle.entry[{idx}].response.status"]
                ))
        # The server itself might return information about the request outcome via OperationOutcome instances
        response_oo_json = response.get('outcome', None)
        if response_oo_json:
            response_oo = OperationOutcome.model_validate(response_oo_json)
            oo.issue.extend(response_oo.issue)
            if any(issue.severity in {"error", "fatal"} for issue in response_oo.issue): # Is any issue severe?
                valid = False
    return valid, oo