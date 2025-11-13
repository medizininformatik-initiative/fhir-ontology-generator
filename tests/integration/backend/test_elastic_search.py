import requests


def test_backend_connection(backend_ip):
    health_endpoint = backend_ip + "/api/v5/actuator/health"
    response = requests.get(health_endpoint, timeout=5)
    assert response.status_code == 200
    assert response.text == '{"status":"UP"}'


def test_elastic_search_connection(elastic_ip):
    health_endpoint = elastic_ip + "/_cluster/health"
    response = requests.get(health_endpoint, timeout=5)
    assert response.status_code == 200
    assert response.json().get("timed_out") is False


def test_fhir_connection(fhir_ip):
    health_endpoint = fhir_ip + "/fhir/metadata"
    response = requests.get(health_endpoint, timeout=5)
    assert response.status_code == 200
