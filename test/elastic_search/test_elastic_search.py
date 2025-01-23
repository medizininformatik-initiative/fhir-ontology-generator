import os
import subprocess
import requests


def test_backend_connection(backend_ip):
    health_endpoint = backend_ip + "/actuator/health"
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

def test_save_docker_logs():
    """
    Test to save logs of all running Docker containers to a logs folder.
    This should be the last test in the file to ensure all other tests are complete.
    """
    output_folder = "./docker_logs"
    os.makedirs(output_folder, exist_ok=True)

    try:
        # Get the list of running container IDs
        result = subprocess.run(
            ["docker", "ps", "-q"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        container_ids = result.stdout.strip().split("\n")

        if not container_ids or container_ids == ['']:
            print("No running containers found.")
            return

        # Save logs for each container
        for container_id in container_ids:
            log_file = os.path.join(output_folder, f"{container_id}_logs.txt")
            with open(log_file, "w") as f:
                subprocess.run(
                    ["docker", "logs", container_id],
                    stdout=f,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=True
                )
            print(f"Logs saved for container {container_id} in {log_file}")
    except subprocess.CalledProcessError as e:
        print(f"Error while fetching logs: {e.stderr}")
