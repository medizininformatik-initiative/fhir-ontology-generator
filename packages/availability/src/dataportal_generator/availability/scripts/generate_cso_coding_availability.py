import argparse
import shutil
import subprocess
from pathlib import Path
from subprocess import CalledProcessError

from dataportal_generator.common.model.project import Project
from dataportal_generator.common.log.functions import get_logger

_logger = get_logger(__file__)


_MEASURE_OUTPUT_FILE_NAME = "Measure-CohortSelectionCodingAvailability.fhir.json"


def _configure_argparser() -> argparse.ArgumentParser:
    """
    Configures the argument parser instance for this script

    :return: Configured `argparse.ArgumentParser` instance
    """
    parser = argparse.ArgumentParser(
        description="Generates the cohort selection coding availability measure"
    )
    parser.add_argument(
        "-p",
        "--project",
        required=True,
        help="Project to generate cohort selection coding availability for",
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


def _preflight_checklist(cso_coding_availability: Path):
    errors = []
    if not shutil.which("sushi"):
        errors.append(FileNotFoundError("Cannot find required tool SUSHI on the system"))
    if not cso_coding_availability.exists() or not cso_coding_availability.is_dir():
        errors.append(FileNotFoundError(f"Project is missing measure input dir @ {repr(cso_coding_availability)}"))
    stratum_to_context_file = cso_coding_availability / "stratum_to_context.json"
    if not stratum_to_context_file.exists() or stratum_to_context_file.is_file():
        errors.append(FileNotFoundError(f"Cannot find stratum context mapping file @ {repr(stratum_to_context_file)}"))
    if errors:
        raise ExceptionGroup(
            "Cannot generate Cohort Selection Coding Availability measure since preflight checks failed",
            errors
        )


def run(project: Project) -> Path:
    """
    Generates the Cohort Selection Coding Availability measure resource for the given project

    :param project: ``Project`` object representing the project to generate for
    :return: ``pathlib.Path`` object pointing measure file
    """
    global _logger
    if not _logger:
        _logger = get_logger(__name__)

    sushi_project_dir = project.input.availability / "cso_coding_availability"
    _preflight_checklist(sushi_project_dir)

    _logger.info("Generating Measure resource")
    try:
        subprocess.check_output([
            "sushi", str(sushi_project_dir.absolute()),
        ], shell=True, stderr=subprocess.STDOUT)
    except CalledProcessError as err:
        raise Exception("Measure generation failed") from err

    output_file = sushi_project_dir / "fsh-generated" / "resources" / "Measure-CdsCodingAvailabilityMeasure.json"
    target_dir = project.output.availability
    target_file = target_dir / _MEASURE_OUTPUT_FILE_NAME
    _logger.info(f"Copying measure to file @ {target_file}")
    shutil.copy(output_file, target_file)

    return target_file


def main():
    """
    Entry point used both by ``python -m`` / direct execution and by the ``generate-cso-coding-availability``
    console script installed via this package's ``[project.scripts]`` entry.
    """
    arg_parser = _configure_argparser()
    args = arg_parser.parse_args()

    project = _setup_project(args.project)

    global _logger
    _logger = get_logger(__name__)

    _logger.info("Generating Coding Availability Measure resource for Cohort Selection")
    run(project)


if __name__ == "__main__":
    main()