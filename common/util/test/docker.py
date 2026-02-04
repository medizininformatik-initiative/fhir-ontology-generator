import json
import os
import subprocess
from datetime import datetime
from sys import stderr
from tabnanny import check

from typing import Optional

from common.util.log.functions import get_logger


logger = get_logger(__file__)


def save_docker_logs(dir_path: str, project_name: Optional[str] = None) -> None:
    """
    Saves logs of all running Docker containers to a logs folder.
    This should be the last test in the file to ensure all other tests are complete.
    :param dir_path: Location (directory) in which to save the directory containing the container logs
    :param project_name: Optional Docker project name no filter container names for.
                         Pattern: <project_name>_<service_name>
    """
    # Directory of the (this) test file
    output_folder = os.path.join(dir_path, "docker_logs")
    os.makedirs(output_folder, exist_ok=True)

    try:
        # Get the list of running container IDs
        args = ["docker", "ps", "-a", "--format", "{{.ID}} {{.Names}}"]
        if project_name:
            args.extend(["-f", f"name=^{project_name}"])
        result = subprocess.run(
            args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True
        )
        stdout = result.stdout.strip()
        if stdout:
            containers = [
                (s[0], s[1])
                for s in [c.split(" ") for c in result.stdout.strip().split("\n")]
            ]

            if not containers:
                logger.warning("Found no running containers")
                return

            now = datetime.now()
            current_time = now.strftime("%H_%M_%S")

            # Save logs for each container
            for container_id, container_name in containers:
                inspect_file = os.path.join(
                    output_folder, f"{container_name}_{current_time}_state.json"
                )
                log_file = os.path.join(
                    output_folder, f"{container_name}_{current_time}_logs.txt"
                )
                with open(inspect_file, "w") as f:
                    subprocess.run(
                        [
                            "docker",
                            "container",
                            "inspect",
                            "--format='{{json .State}}'",
                            container_id,
                        ],
                        stdout=f,
                        stderr=subprocess.PIPE,
                        text=True,
                        check=True,
                    )
                with open(log_file, "w") as f:
                    subprocess.run(
                        ["docker", "logs", "-t", container_id],
                        stdout=f,
                        stderr=subprocess.PIPE,
                        text=True,
                        check=True,
                    )
                logger.info(
                    f"Logs saved for container {container_name} [id={container_id}] in {log_file}, {inspect_file}"
                )
    except subprocess.CalledProcessError as err:
        logger.error(
            f"Error while fetching container data. Reason: {err.stderr}", exc_info=err
        )
    except Exception as exc:
        logger.error(
            f"Error while fetching container data. Reason: {exc}", exc_info=exc
        )
