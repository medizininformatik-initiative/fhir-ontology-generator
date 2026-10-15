import requests


def test_run_ccdl_query(
    ccdl_query: str, expected, flare_url: str, fhir_server_url: str
):
    response = requests.post(
        f"{flare_url}/query/execute",
        data=ccdl_query,
        headers={"Content-Type": "application/sq+json"},
    )
    response.raise_for_status()

    population_size = int(response.text)
    assert population_size == expected