import os
import subprocess
from datetime import datetime
from subprocess import CalledProcessError
from types import ModuleType

from dataportal_generator.common.log.functions import get_logger
from dataportal_generator.common.model.project import Project

_logger = get_logger(__name__)


def save_docker_logs(project: Project, module: ModuleType, compose_project: str) -> None:
    """
    Saves logs of all running Docker containers of a compose project

    :param project: ``Project`` object providing logging location
    :param module: Relative location from the project logging location to write the docker logs to under
        ``<project_path>/<logs>/<module_path>/docker_logs/<compose_project_name>``
    :param compose_project: Docker Compose project name no filter container names for.
                         Pattern: <project_name>_<service_name>
    """
    output_folder = (
        project.logs / module.__name__.replace(".", "/") / "docker_logs" / compose_project
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
            f"name=^{compose_project}",
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
                    f"Found no running containers for compose project '{compose_project}'"
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
            f"Error while fetching logs for compose project '{compose_project}'. Details: "
            f"{err.stderr if isinstance(err, CalledProcessError) else err}",
            exc_info=err,
        )
