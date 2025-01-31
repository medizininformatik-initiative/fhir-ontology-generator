import json
import os.path
import time

from jsonpath_ng import parse
import pytest

from util.test.fhir import delete_from_fhir_server, load_list_of_resources_onto_fhir_server, \
    delete_list_of_resources_from_fhir_server
from util.test.docker import save_docker_logs

def resolve_ref(ref: str, ensemble=None, resolved=None, resolving=None) -> list[str]:
    """
    Resolves dependencies recursively in the correct order (dependencies first).
    :param ref: reference to be resolved
    :param ensemble: dictionary containing all files {file_name: file_content}
    :param resolved: list of already resolved dependencies (maintains correct order)
    :param resolving: set to track files being resolved to prevent circular references
    :return: ordered list of dependencies (dependencies first)
    """
    if resolved is None:
        resolved = []
    if resolving is None:
        resolving = set()

    if ref in resolving:  # Prevent circular dependencies
        return []

    resolving.add(ref)
    jsonpath_expr = parse('$..reference')

    refs_still_to_resolve = [
        reference.replace("/", "-", 1) + ".json"
        for match in jsonpath_expr.find(ensemble.get(ref, {}))
        for reference in [match.value]
        if reference.replace("/", "-", 1) + ".json" in ensemble
    ]

    for reference in refs_still_to_resolve:
        if reference not in resolved:
            resolve_ref(reference, ensemble, resolved, resolving)

    if ref not in resolved:
        resolved.append(ref)

    resolving.remove(ref)
    return resolved

def get_patient_files(patient_file: str, test_data_folder: str) -> list[str]:
    """
    Collects all FHIR resource files related to a given patient file in correct order.
    :param patient_file: The filename of the patient JSON file
    :param test_data_folder: The directory containing the test data JSON files
    :return: Ordered list of file names (dependencies first)
    """
    with open(os.path.join(test_data_folder, patient_file), "r", encoding="utf-8") as f:
        patient = json.load(f)

    patient_id = patient.get("id")
    if not patient_id:
        raise ValueError("Patient file does not contain an 'id' field.")

    # Load all JSON files into memory
    ensemble = {
        file: json.load(open(os.path.join(test_data_folder, file), "r", encoding="utf-8"))
        for file in os.listdir(test_data_folder) if file.endswith(".json")
    }

    # Find files referencing this patient
    patient_referenced_files = [
        file for file, content in ensemble.items()
        if content.get("subject", {}).get("reference") == f"Patient/{patient_id}"
        or content.get("patient", {}).get("reference") == f"Patient/{patient_id}"
    ]

    ordered_fhir_resources = []
    for patient_ref_file in patient_referenced_files:
        resolve_ref(patient_ref_file, ensemble, ordered_fhir_resources)

    return ordered_fhir_resources


with open("ModuleTestDataConfig.json", "r", encoding="utf-8") as f:
    test_data = json.load(f)

@pytest.mark.parametrize("data_resource_file, query_resource_path", test_data)
def test_module(data_resource_file, query_resource_path, backend_auth, fhir_testdata, fhir_ip):

    # create list with all referenced files - recursively?
    resource_folder = os.path.join("testdata", "kds-testdata-2024.0.1", "resources")
    fhir_resources = get_patient_files(data_resource_file, test_data_folder=resource_folder)

    # load fhir resource onto fhir server for patient
    if load_list_of_resources_onto_fhir_server(fhir_api=fhir_ip + "/fhir", files=fhir_resources, testdata_folder=resource_folder):
        print("Uploaded fhir data")

    # send ccdl to backend
    with open(os.path.join("test_querys",query_resource_path),"r",encoding="utf-8") as f:
        query = json.dumps(json.load(f))
    query_id = backend_auth.query(query).split("/")[-1]

    # get query result, check
    query_result = backend_auth.get_query_summary_result(query_id)
    assert int(query_result.get("totalNumberOfPatients")) >= 1

    if delete_list_of_resources_from_fhir_server(fhir_api=fhir_ip+"/fhir",fhir_resources=list(reversed(fhir_resources))):
        print("Deleted fhir data")

def test_upload_docker():
    save_docker_logs()