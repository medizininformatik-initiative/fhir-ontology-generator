import argparse

from dataportal_generator.common.model.project import Project
from dataportal_generator.common.log.functions import get_logger

_logger = get_logger(__file__)


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


def _setup_project(project_name: str) -> Project:
    """
    Setup function for the scripts project context

    :param project_name: Name of the project to generate for
    :return: `Project` instance representing the project context
    """
    project = Project(project_name)
    _logger.info("Preparing packages")
    project.package_manager.restore(inflate=True, lenient=True)
    return project


def run(project: Project) -> Measure:
    """
    Generates the Cohort Selection Coding Availability measure resource for the given project

    :param project: ``Project`` object representing the project to generate for
    :return: FHIR ``Measure`` resource
    """
    global _logger
    if not _logger:
        _logger = get_logger(__name__)

    return None


def __main():
    arg_parser = _configure_argparser()
    args = arg_parser.parse_args()

    project = _setup_project(args.project)

    global _logger
    _logger = get_logger(__name__)

    _logger.info("Generating Coding Availability Measure resource for Cohort Selection")
    coding_measure = run(project)

    measure_file_path = (
        project.output.availability / "Measure-CsoCodingAvailability.fhir.json"
    )
    _logger.info(f"Writing measure to file @ {measure_file_path}")
    with measure_file_path.open(mode="w", encoding="utf-8") as f:
        f.write(coding_measure.model_dump_json())


if __name__ == "__main__":
    __main()