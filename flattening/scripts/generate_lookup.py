import argparse
import json
from typing import List

from common.util.http.terminology.client import FhirTerminologyClient
from common.util.log.functions import get_logger
from common.util.project import Project
from flattening.core.flattening import generate_flattening_lookup, FlatteningLookup

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
        description="Generates the DSE element availability measure for any given project using its package scope and "
        "the profiles and elements actually supported in the DSE"
    )
    parser.add_argument(
        "-p",
        "--project",
        required=True,
        help="Project to generate DSE element availability for. The measure will include the profiles it depends on",
    )
    return parser


if __name__ == "__main__":
    arg_parser = _configure_argparser()
    args = arg_parser.parse_args()

    project = _setup_project(args.project)
    lookup_file: List[FlatteningLookup] = generate_flattening_lookup(
        project.package_manager, FhirTerminologyClient.from_project(project)
    )

    with open(
        project.output.flattening / "FlatteningLookup.json", mode="w", encoding="utf-8"
    ) as f:
        json.dump([x.model_dump(exclude_none=True) for x in lookup_file], f, indent=2)
