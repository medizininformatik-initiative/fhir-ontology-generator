import argparse

import yaml

from common.util.http.terminology.client import FhirTerminologyClient
from common.util.log.functions import get_logger
from common.util.project import Project
from dimp_dup_config.core.dimp_config_functions import generate_dimp_config

_logger = get_logger(__file__)


def _setup_project(project_name: str) -> Project:
    """
    Setup function for the scripts project context

    :param project_name: Name of the project to generate for
    :return: `Project` instance representing the project context
    """
    project = Project(project_name)
    _logger.info("Preparing packages")
    project.package_manager.restore(inflate=True)
    return project


def _configure_argparser() -> argparse.ArgumentParser:
    """
    Configures the argument parser instance for this script

    :return: Configured `argparse.ArgumentParser` instance
    """
    parser = argparse.ArgumentParser(
        description="Generates the DIMP config for any given project using its package scope and "
        "the profiles and elements actually supported in the DSE"
    )
    parser.add_argument(
        "-p",
        "--project",
        required=True,
        help="Project to generate DIMP config for. It will include information for all profiles of DSE"
    )
    return parser


if __name__ == "__main__":
    arg_parser = _configure_argparser()
    args = arg_parser.parse_args()

    project = _setup_project(args.project)
    client = FhirTerminologyClient.from_project(project)

    dimp_config = generate_dimp_config(manager=project.package_manager, client=client)

    with open(
        project.output.dimp_config / "dimp_config.yaml", mode="w", encoding="utf-8"
    ) as f:
        yaml.safe_dump(
            dimp_config.to_dimp_format(),
            f,
            sort_keys=False,
            default_flow_style=False,
            width=1000,
        )
