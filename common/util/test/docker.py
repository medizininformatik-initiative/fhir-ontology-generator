import os
import subprocess
from datetime import datetime
from pathlib import Path
from subprocess import CalledProcessError

from common.constants.project import PROJECT_ROOT
from common.util.log.functions import get_logger

_logger = get_logger(__file__)


def save_docker_logs(dir_path: Path, project_name: str) -> None:
    """
    Saves logs of all running Docker containers of a compose project to some directory. The actual path under which the
    log files can be found is: ::

    <repo_path>/logs/<dir_path>/docker/<project_name>
    :param dir_path: Relative location to the global logs directory to save the logs at
    :param project_name: Docker Compose project name no filter container names for.
                         Pattern: <project_name>_<service_name>
    """
    # Directory of the (this) test file
    logs_dir = PROJECT_ROOT / "logs"
    output_folder = (
        logs_dir / dir_path.relative_to(PROJECT_ROOT) / "docker" / project_name
    )
    output_folder.mkdir(parents=True, exist_ok=True)

    try:
        # Get the list of running container IDs
        args = [
            "docker",
            "ps",
            "-a",
            "--format",
            "{{.ID}} {{.Names}}",
            "-f",
            f"name=^{project_name}",
        ]
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
                _logger.warning(
                    f"Found no running containers for compose project '{project_name}'"
                )
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
                _logger.info(
                    f"Saved logs of container '{container_name}' ({container_id}) @ '{log_file}'"
                )
    except Exception as err:
        _logger.error(
            f"Error while fetching logs for compose project '{project_name}'. Details: "
            f"{err.stderr if isinstance(err, CalledProcessError) else err}",
            exc_info=err,
        )
