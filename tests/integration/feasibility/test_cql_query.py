import requests
from fhir.resources.R4B.measurereport import MeasureReport


def test_evaluate_cql_measure(
    prepared_measure_uri: str, expected, fhir_server_url: str
):
    response = requests.get(
        f"{fhir_server_url}/Measure/$evaluate-measure",
        params={
            "periodStart": "1900-01-01",
            "periodEnd": "2100-01-01",
            "measure": prepared_measure_uri,
            "reportType": "population",
        },
        headers={"Accept": "application/fhir+json"},
    )
    response.raise_for_status()

    measure_report = MeasureReport.model_validate(response.json())
    assert measure_report.group[0].population[0].count == expected
