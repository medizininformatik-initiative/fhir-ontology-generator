import json
from string import Template
from typing import Mapping, Any

import pytest
import requests

from common.util.test.functions import mismatch_str


def test_criterion_term_code_search(
    query_template: Template,
    expected: Mapping[str, Any],
    elastic_url,
):
    query = query_template.substitute(
        context_code=expected["context"]["code"],
        cds_module=expected["kds_module"],
        terminology=expected["terminology"],
        termcode=expected["termcode"],
    )
    response = requests.post(f"{elastic_url}/ontology/_search", json=json.loads(query))
    response.raise_for_status()
    hits = response.json().get("hits", [])
    hits_total = hits.get("total", {}).get("value")

    assert hits_total > 0, "Expected at least one match for the search query"
    result = hits["hits"][0]["_source"]

    actual_id = result.get("id")
    expected_id = expected.get("id")
    assert actual_id == expected_id, mismatch_str("hash ID", actual_id, expected_id)

    # Disabled for since changes in the display values are common between different versions and lead the test to
    # fail
    # actual_display = result.get("display")
    # expected_display = expected_entry.get("display")
    # assert actual_display == expected_display, mismatch_str(
    #    "display", actual_display, expected_display
    # )

    actual_context = result.get("context")
    expected_context = result.get("context")
    assert actual_context == expected_context, mismatch_str(
        "context", actual_context, expected_context
    )

    actual_terminology = result.get("terminology")
    expected_terminology = expected.get("terminology")
    assert actual_terminology == expected_terminology, mismatch_str(
        "terminology", actual_terminology, expected_terminology
    )

    actual_termcode = result.get("termcode")
    expected_termcode = expected.get("termcode")
    assert actual_termcode == expected_termcode, mismatch_str(
        "termcode", actual_termcode, expected_termcode
    )

    actual_kds_module = result.get("kdsModule")
    expected_kds_module = expected.get("kdsModule")
    assert actual_kds_module == expected_kds_module, mismatch_str(
        "kdsModule", actual_kds_module, expected_kds_module
    )

    actual_selectable = result.get("selectable")
    expected_selectable = expected.get("selectable")
    assert actual_selectable == expected_selectable, mismatch_str(
        "selectable", actual_selectable, expected_selectable
    )


def _query_es(url: str, query: Mapping[str, Any]) -> tuple[int, list[Any]]:
    response = requests.post(f"{url}/_search", json=query)
    response.raise_for_status()
    hits = response.json().get("hits", [])
    hits_total = hits.get("total", {}).get("value")
    return hits_total, hits


@pytest.mark.parametrize(
    argnames=["resource_type"],
    argvalues=[pytest.param("Condition")],
)
def test_profile_search_by_resource_type(
    resource_type: str,
    elastic_url,
):
    query = {"query": {"term": {"resource_type.original": resource_type}}}
    hits_total, hits = _query_es(f"{elastic_url}/profile", query)

    assert hits_total > 0, "Expected at least one match for the search query"
    assert hits["hits"][0]["_source"]["resource_type"]["original"] == resource_type


@pytest.mark.parametrize(
    argnames=["module"],
    argvalues=[
        pytest.param("modul-medikation", id="medication"),
    ],
)
def test_profile_search_by_module(
    module: str,
    elastic_url,
):
    query = {
        "query": {
            "term": {
                "module.original": module,
            }
        }
    }
    hits_total, hits = _query_es(f"{elastic_url}/profile", query)

    assert hits_total > 0, "Expected at least one match for the search query"
    assert hits["hits"][0]["_source"]["module"]["original"] == module


@pytest.mark.parametrize(
    argnames=["name"],
    argvalues=[pytest.param("MII_PR_Fall_KontaktGesundheitseinrichtung")],
)
def test_profile_search_by_name(
    name: str,
    elastic_url,
):
    query = {"query": {"match": {"name": name}}}
    hits_total, hits = _query_es(f"{elastic_url}/profile", query)

    assert hits_total > 0, "Expected at least one match for the search query"
    assert hits["hits"][0]["_source"]["name"] == name


@pytest.mark.parametrize(
    argnames=["description", "best_match"],
    argvalues=[
        pytest.param(
            "Medikation, die angesetzt, geplant oder verabreicht",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-medikation/StructureDefinition/Medication",
            id="medication-de",
        ),
        pytest.param(
            "drug or formulation",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-medikation/StructureDefinition/Medication",
            id="medication-en",
        ),
    ],
)
def test_profile_search_by_description(
    description: str,
    best_match: str,
    elastic_url,
):
    query = {
        "query": {
            "multi_match": {
                "fields": [
                    "description.original",
                    "description.localization.de-DE",
                    "description.localization.en-US",
                ],
                "query": description,
            }
        }
    }
    hits_total, hits = _query_es(f"{elastic_url}/profile", query)

    assert hits_total > 0, "Expected at least one match for the search query"
    assert hits["hits"][0]["_source"]["url"] == best_match
