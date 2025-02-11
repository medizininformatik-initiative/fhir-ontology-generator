import json
import logging
import os
from typing import Mapping

import jsonschema
import pytest
from jsonpath_ng import parse

from model.ResourceQueryingMetaData import ResourceQueryingMetaData
from util.http.backend.FeasibilityBackendClient import FeasibilityBackendClient
from util.test.fhir import load_list_of_resources_onto_fhir_server, delete_list_of_resources_from_fhir_server
from util.test.functions import mismatch_str


logger = logging.getLogger(__name__)


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


#@pytest.mark.parametrize("data_resource_file, query_resource_path", test_data)
def test_ccdl_query(data_resource_file, query_resource_path, backend_client, fhir_ip, backend_ip, test_dir,
                    fhir_testdata):

    # create list with all referenced files - recursively?
    resource_folder = os.path.join(test_dir, "testdata", "kds-testdata-2024.0.1", "resources")
    fhir_resources = get_patient_files(data_resource_file, test_data_folder=resource_folder)

    # load fhir resource onto fhir server for patient
    if load_list_of_resources_onto_fhir_server(fhir_api=fhir_ip + "/fhir", files=fhir_resources, testdata_folder=resource_folder):
        logger.debug("Uploaded fhir data")

    # send ccdl to backend
    with open(os.path.join(test_dir, "test-queries", query_resource_path), "r", encoding="utf-8") as f:
        query = json.dumps(json.load(f))
    query_id = backend_client.query(query).split("/")[-1]

    # get query result, check
    query_result = backend_client.get_query_summary_result(query_id)
    assert int(query_result.get("totalNumberOfPatients")) == 1

    if delete_list_of_resources_from_fhir_server(fhir_api=fhir_ip+"/fhir", fhir_resources=list(reversed(fhir_resources))):
        logger.debug("Deleted fhir data")


# TODO: Should this be moved to the unit tests?
def test_criterion_definition_validity(querying_metadata: ResourceQueryingMetaData,
                                    querying_metadata_schema: Mapping[str, any]):
    try:
        jsonschema.validate(instance=json.loads(querying_metadata.to_json()), schema=querying_metadata_schema)
    except jsonschema.exceptions.ValidationError:
        pytest.fail(f"JSON schema validation failed for file")


def test_criterion_term_code_search(expected_responses: list[Mapping[str, any]],
                                    backend_client: FeasibilityBackendClient, backend_ip, elastic_ip):
    for expected_response in expected_responses:
        expected_entry = expected_response['results'][0]
        response = backend_client.search_terminology_entries(search_term=expected_entry['termcode'],
                                                             contexts=[expected_entry['context']],
                                                             terminologies=[expected_entry['terminology']],
                                                             kds_modules=[expected_entry['kdsModule']])
        assert len(response.get('results', [])) > 0, "Expected at least one match for the search query"
        response_entry = response.get('results')[0]

        actual_id = response_entry.get('id')
        expected_id = expected_entry.get('id')
        assert actual_id == expected_id, mismatch_str("hash ID", actual_id, expected_id)

        actual_display = response_entry.get('display')
        expected_display = expected_entry.get('display')
        assert actual_display == expected_display, mismatch_str("display", actual_display, expected_display)

        actual_context = response_entry.get('context')
        expected_context = response_entry.get('context')
        assert actual_context == expected_context, mismatch_str("context", actual_context, expected_context)

        actual_terminology = response_entry.get('terminology')
        expected_terminology = expected_entry.get('terminology')
        assert actual_terminology == expected_terminology, mismatch_str("terminology", actual_terminology,
                                                                        expected_terminology)

        actual_termcode = response_entry.get('termcode')
        expected_termcode = expected_entry.get('termcode')
        assert actual_termcode == expected_termcode, mismatch_str("termcode", actual_termcode, expected_termcode)

        actual_kds_module = response_entry.get('kdsModule')
        expected_kds_module = expected_entry.get('kdsModule')
        assert actual_kds_module == expected_kds_module, mismatch_str("kdsModule", actual_kds_module,
                                                                      expected_kds_module)

        actual_selectable = response_entry.get('selectable')
        expected_selectable = expected_entry.get('selectable')
        assert actual_selectable == expected_selectable, mismatch_str("selectable", actual_selectable,
                                                                      expected_selectable)
