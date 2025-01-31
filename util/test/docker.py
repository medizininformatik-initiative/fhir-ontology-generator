import json
import os
import subprocess
import logging
import zipfile
from datetime import datetime

import requests

from util.FhirUtil import create_bundle, BundleType


logger = logging.getLogger(__name__)


def save_docker_logs():
    """
    Test to save logs of all running Docker containers to a logs folder.
    This should be the last test in the file to ensure all other tests are complete.
    """
    # Directory of the (this) test file
    test_dir_path = os.path.dirname(os.path.realpath(__file__))
    output_folder = os.path.join(test_dir_path, "docker_logs")
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
            logger.info("No running containers found.")
            return

        now = datetime.now()
        current_time = now.strftime('%H_%M_%S')

        # Save logs for each container
        for container_id in container_ids:
            log_file = os.path.join(output_folder, f"{container_id}_{current_time}_logs.txt")
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