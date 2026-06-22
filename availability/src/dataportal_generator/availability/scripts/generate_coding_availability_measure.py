import argparse
import logging
import shutil
import subprocess
import sys

from dataportal_generator.common.log.functions import get_logger
from dataportal_generator.common.model.project import Project

__logger: logging.LoggerAdapter


def __parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="generate-coding-availability-measure.py",
        description="Generates a Measure resource for analyzing coding variance",
    )
    parser.add_argument(
        "-p", "--project",
        required=True,
        help="Specify project to generate for (required)",
    )
    return parser.parse_args()


def run(project: Project):
    """
    Non-script entrypoint the CDS Coding Availability measure generation

    :param project: ``Project`` instance to run CDS Coding Availability measure generation with
    """
    try:
        sushi_project_dir = project.input.availability / "coding_availability"
        sushi_output_dir = project.output.availability.mkdirs(".tmp")

        __logger.info(f"Generating CDS Coding Availability measure using SUSHI project @ {repr(sushi_project_dir)}")
        subprocess.run(
            ["sushi", "build", "--out", str(sushi_output_dir.absolute()), str(sushi_project_dir)],
            check=True,
        )

        target_dir = project.output.availability
        tgt_measure_file = target_dir / "Measure-CdsCodingAvailability.fhir.json"
        src_measure_file = (
                sushi_output_dir
                / "fsh-generated"
                / "resources"
                / "Measure-CdsCodingAvailabilityMeasure.json"
        )
        context_mapping_file = sushi_project_dir / "stratum-to-context.json"

        __logger.info(f"Copying generated measure file and context mapping")
        if not src_measure_file.exists():
            raise FileNotFoundError(f"Missing generated measure file @ {repr(src_measure_file)}")
        if not context_mapping_file.exists():
            raise FileNotFoundError(f"Missing context mapping file @ {repr(context_mapping_file)}")
        shutil.copy(src_measure_file, tgt_measure_file)
        shutil.copy(context_mapping_file, target_dir / "stratum-to-context.json")
    except Exception as exc:
        raise Exception(f"CDS Coding Availability measure generation failed: {exc}") from exc


def __main():
    args = __parse_args()
    project = Project(name=args.project)
    global __logger
    __logger = get_logger(__name__)

    try:
        run(project)
    except:
        __logger.exception("")
        sys.exit(1)


if __name__ == "__main__":
    __main()
