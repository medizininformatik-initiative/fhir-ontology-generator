import json
import os
from typing import Mapping

import jsonschema
import pytest
from jsonpath_ng import parse

from model.ResourceQueryingMetaData import ResourceQueryingMetaData
from util.http.backend.FeasibilityBackendClient import FeasibilityBackendClient
from util.test.fhir import load_list_of_resources_onto_fhir_server, delete_list_of_resources_from_fhir_server


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
        print("Uploaded fhir data")

    # send ccdl to backend
    with open(os.path.join(test_dir, "test_querys", query_resource_path), "r", encoding="utf-8") as f:
        query = json.dumps(json.load(f))
    query_id = backend_client.query(query).split("/")[-1]

    # get query result, check
    query_result = backend_client.get_query_summary_result(query_id)
    assert int(query_result.get("totalNumberOfPatients")) >= 1

    if delete_list_of_resources_from_fhir_server(fhir_api=fhir_ip+"/fhir",fhir_resources=list(reversed(fhir_resources))):
        print("Deleted fhir data")


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
        entry = expected_response['results'][0]
        response = backend_client.search_terminology_entries(search_term=entry['termcode'], contexts=[entry['context']],
                                                             terminologies=[entry['terminology']],
                                                             kds_modules=[entry['kdsModule']])
        assert len(response.get('results', [])) > 0, "Expected at least one match for the search query"
        response_entry = response.get('results')[0]
        assert response_entry.get('id') == entry.get('id'), (f"Hash IDs mismatch [actual={response_entry}, "
                                                             f"expected={entry}]")
        assert response_entry.get('display') == entry.get('display'), (f"Display mismatch [actual={response_entry}, "
                                                                       f"expected={entry}]")
        assert response_entry.get('context') == entry.get('context'), (f"Context mismatch [actual={response_entry}, "
                                                                       f"expected={entry}]")
        assert response_entry.get('terminology') == entry.get('terminology'), (f"Code system mismatch "
                                                                               f"[actual={response_entry}, "
                                                                               f"expected={entry}]")
        assert response_entry.get('termcode') == entry.get('termcode'), (f"Term code mismatch "
                                                                         f"[actual={response_entry}, expected={entry}]")
        assert response_entry.get('kdsModule') == entry.get('kdsModule'), (f"Term code mismatch "
                                                                           f"[actual={response_entry}, "
                                                                           f"expected={entry}]")
        assert response_entry.get('selectable') == entry.get('selectable'), (f"Term code mismatch "
                                                                             f"[actual={response_entry}, "
                                                                             f"expected={entry}]")


'''
def test_criterion_term_code_search(querying_metadata: ResourceQueryingMetaData,
                                    backend_client: FeasibilityBackendClient,
                                    terminology_client: FhirTerminologyClient):
    try:
        term_codes = get_term_code_set_for_querying_metadata(querying_metadata, terminology_client)
    except Exception as exc:
        pytest.fail(f"Failed to retrieve term codes for testing. Reason: {exc}")

    contexts = [querying_metadata.context.code]
    modules = [querying_metadata.backend.display] # FIXME: Should be code in the future
    for term_code in term_codes:
        search_term = term_code.code
        terminologies = [term_code.system]
        result = backend_client.search_terminology_entries(search_term=search_term, contexts=contexts,
                                                           kds_modules=modules, terminologies=terminologies,
                                                           page_size=5)
        entries = result.get('results', [])
        for entry in entries:
            assert entry.get('context') == querying_metadata.context.code
            assert entry.get('kdsModule') == querying_metadata.context.display
            assert entry.get('name') == querying_metadata.context.display

        # Collect contextualized term code hashes (their IDs) for request
        ids = [entry['id'] for entry in entries]
        term_code_entries = backend_client.get_criteria_profile_data(criteria_ids=ids)
        assert len(term_code_entries) == len(ids)
        # All returned term codes should be associated with the UI profile corresponding to the querying metadata
        # profile since we restricted the search to its context, backend and defining term codes value set
        for entry in term_code_entries:
            context = entry.get('context')
            assert context, "A contextualized term code should have a context attribute that is not empty"
            assert context.get('system') == querying_metadata.context.system
            assert context.get('code') == querying_metadata.context.code
            assert context.get('display') == querying_metadata.context.display
            assert context.get('version') == querying_metadata.context.version

            ui_profile = entry.get('uiProfile')
            assert ui_profile, "A contextualized term code should be associated with at least one UI profile"



def check_criteria_profile_resolution(crit_profile_data: CriteriaProfileData,
                                      querying_metadata: ResourceQueryingMetaData):
    ui_profile = entry.get('uiProfile')
    assert ui_profile is not None, ("There should be at least one UI profile associated with the "
                                    f"contextualized term code [system='{term_code.system}', "
                                    f"code='{term_code.code}', version={term_code.version}]")

    if querying_metadata.value_defining_id is not None:
        val_def = ui_profile.get('valueDefinition')
        assert val_def is not None, ("A value definition should be present in the UI profile if there is a "
                                     "'value_defining_id' element defined in the querying metadata profile")
        assert val_def.get('type') == querying_metadata.value_type
        assert val_def.get('optional') == querying_metadata.value_optional

    if querying_metadata.attribute_defining_id_type_map:
        qm_attr_map = querying_metadata.attribute_defining_id_type_map
        attr_defs = ui_profile.get('attributeDefinition', [])
        assert len(qm_attr_map) == len(attr_defs)
        for attr_def in attr_defs:
            qm_attr
            assert attr_def.get('type') ==

    assert (ui_profile.get('timeRestrictionAllowed') ==
            (querying_metadata.time_restriction_defining_id is not None))
'''