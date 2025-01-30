import json
import os.path
from jsonpath_ng import parse
import pytest

from util.test.fhir import delete_from_fhir_server, load_list_of_resources_onto_fhir_server


def resolve_ref(ref: str, ensemble=None)->list[str]:
    """
    Creates a list of all dependencies of a test data file, resolving references recursively.
    :param ref: reference to be resolved
    :param first: indicator whether the ensemble should be initialized
    :param ensemble: dct that contains all files {file_name: file_content}
    :param test_data_folder: folder where test data files are located
    :return: list of dependencies(file_names.json) of initial given reference
    # TODO: fix test_data_folder default value shouldn't contain "kds-testdata-2024.0.1"
    """
    refs_to_upload = set()
    jsonpath_expr = parse('$..reference')

    refs_still_to_resolve = {
        reference.replace("/", "-", 1) + ".json"
        for match in jsonpath_expr.find(ensemble.get(ref, {}))
        for reference in [match.value]
    }

    refs_to_upload.update(refs_still_to_resolve)

    for reference in refs_still_to_resolve:
        if reference in ensemble and reference not in refs_to_upload:
            refs_to_upload.update(resolve_ref(reference, ensemble))

    return list(refs_to_upload)

def get_patient_files(patient_file:str, test_data_folder)->list[str]:

    with open(os.path.join(test_data_folder,patient_file), "r", encoding="utf-8") as f:
        patient = json.load(f)

    patient_id = patient.get("id")
    if not patient_id:
        raise ValueError("Patient file does not contain an 'id' field.")

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

    fhir_resources = set(patient_referenced_files)
    for patient_ref_file in patient_referenced_files:
        fhir_resources.update(resolve_ref(patient_ref_file, ensemble))

    return list(fhir_resources)


test_data=[
    ("Patient-mii-exa-test-data-patient-1.json", "BioprobeQueryPatient3.json"),
    ("Patient-mii-exa-test-data-patient-1.json", "BioprobeQueryPatient1.json")
]

@pytest.mark.parametrize("data_resource_file, query_resource_path", test_data)
def test_module(data_resource_file, query_resource_path, backend_auth, fhir_testdata, fhir_ip):

    print(data_resource_file)
    print(query_resource_path)
    print(backend_auth)
    print(fhir_ip)
    print(fhir_testdata)

    # create list with all referenced files - recursively?
    resource_folder = os.path.join("testdata", "kds-testdata-2024.0.1", "resources")
    fhir_resources = get_patient_files(data_resource_file, test_data_folder=resource_folder)
    print(fhir_resources)

    # load fhir resource onto fhir server for patient
    load_list_of_resources_onto_fhir_server(fhir_api=fhir_ip + "/fhir", files=fhir_resources, testdata_folder=resource_folder)
    print("Uploaded fhir data")

    # send ccdl to backend, check if patient is found
    with open(os.path.join("test_querys",query_resource_path),"r",encoding="utf-8") as f:
        query = json.dumps(json.load(f))


    print(backend_auth.validate_query(query))
    location = backend_auth.query(query)
    query_id = location.split("/")[-1]

    print(f"Uploaded query with id {query_id}")
    print(f"All querys: {backend_auth.get_current_querys()}")


    query_result = backend_auth.get_query_summary_result(query_id)
    print(query_result)
    assert int(query_result.get("totalNumberOfPatients")) >= 1

    # delete stored query on backend


    # delete uploaded files from fhir server
    for resource in fhir_resources:
        resource_id = resource.split("/")[-1].split(".")[0]
        resource_type = resource.split("/")[0]
        delete_from_fhir_server(fhir_api=fhir_ip+"/fhir",resource_type=resource_type, resource_id=resource_id)


