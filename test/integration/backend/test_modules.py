import json
from typing import Mapping

import jsonschema
import pytest

from model.ResourceQueryingMetaData import ResourceQueryingMetaData
from util.http.backend.FeasibilityBackendClient import FeasibilityBackendClient


# TODO: Should this be moved to the unit tests?
def test_criterion_definition_validity(querying_metadata: ResourceQueryingMetaData,
                                    querying_metadata_schema: Mapping[str, any]):
    try:
        jsonschema.validate(instance=json.loads(querying_metadata.to_json()), schema=querying_metadata_schema)
    except jsonschema.exceptions.ValidationError:
        pytest.fail(f"JSON schema validation failed for file")


def test_criterion_term_code_search(expected_responses: list[Mapping[str, any]],
                                    backend_client: FeasibilityBackendClient):
    for expected_response in expected_responses:
        entry = expected_response['results'][0]
        response = backend_client.search_terminology_entries(search_term=entry['termcode'], contexts=[entry['context']],
                                                             terminologies=[entry['terminology']],
                                                             kds_modules=[entry['kdsModule']])
        assert len(response.get('results', [])) > 0
        response_entry = response.get('results')[0]
        assert response_entry.get('id') == entry.get('id')
        assert response_entry.get('display') == entry.get('display')
        assert response_entry.get('context') == entry.get('context')
        assert response_entry.get('terminology') == entry.get('terminology')
        assert response_entry.get('termcode') == entry.get('termcode')
        assert response_entry.get('kdsModule') == entry.get('kdsModule')
        assert response_entry.get('selectable') == entry.get('selectable')


'''
def test_criterion_term_code_search(querying_metadata: ResourceQueryingMetaData,
                                    backend_client: FeasibilityBackendClient,
                                    terminology_client: FhirTerminologyClient):
    try:
        term_codes = get_term_code_set_for_querying_metadata(querying_metadata, terminology_client)
    except Exception as exc:
        pytest.fail(f"Failed to retrieve term codes for testing. Reason: {exc}")

    contexts = [querying_metadata.context.code]
    modules = [querying_metadata.module.display] # FIXME: Should be code in the future
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
        # profile since we restricted the search to its context, module and defining term codes value set
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