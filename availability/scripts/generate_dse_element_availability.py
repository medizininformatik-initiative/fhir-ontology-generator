import argparse
import json
from collections.abc import Mapping
from datetime import datetime, UTC
from typing import List

from fhir.resources.R4B.measure import Measure
from fhir.resources.R4B.meta import Meta

from availability.core.element_availability import (
    generate_measure,
    update_stratifier_ids,
)
from common.util.collections.functions import first
from common.util.log.functions import get_logger
from common.util.project import Project
from data_selection_extraction.model.detail import ProfileDetail, FieldDetail

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
    project.package_manager.restore(inflate=True)
    return project


def _flatten_fields(detail: ProfileDetail | FieldDetail) -> List[FieldDetail]:
    """
    Returns a flat list containing all field details listed in the provided tree

    :param detail: Field details tree
    :return: List of `FieldDetail` instances
    """
    if "children" in detail:
        return [
            detail,
            *[
                fd_fd
                for fd in detail.get("children", [])
                for fd_fd in _flatten_fields(fd)
            ],
        ]
    elif "fields" in detail:
        return [
            fd_fd
            for fd in [*detail.get("fields", []), *detail.get("references", [])]
            for fd_fd in _flatten_fields(fd)
        ]
    else:
        raise ValueError(f"Unexpected type {type(detail)}")


def generate_element_availability_for_dse(project: Project) -> Measure:
    _logger.info("Generating Measure resource")
    measure = generate_measure(
        project.package_manager,
        id="DseElementAvailabilityMeasure",
        meta=Meta(
            profile=[
                "http://hl7.org/fhir/us/cqfmeasures/StructureDefinition/cv-measure-cqfm"
            ]
        ),
        url="https://medizininformatik-initiative.de/fhir/fdpg/Measure/DseElementAvailabilityMeasure",
        name="DseElementAvailabilityMeasure",
        title="DSE Element Availability Measure",
        status="active",
        experimental=False,
        date=datetime.now(UTC),
        publisher="FDPG-Plus",
        description="Measure for analyzing the availability of elements of supported by the DSE in a FHIR server",
    )

    _logger.info("Reducing groups and contained stratifiers to match DSE scope")
    _logger.debug("Loading profile details")
    with (project.output.dse / "profile_details_all.json").open(
        mode="r", encoding="utf-8"
    ) as details_f:
        profile_details: Mapping[str, Mapping[str, FieldDetail]] = {
            pd.get("url"): {fd.get("id"): fd for fd in _flatten_fields(pd)}
            for pd in json.load(details_f)
        }

    _logger.debug("Processing Measure resource")
    included_groups = []
    for group in measure.group:
        source_ext = first(
            lambda ext: ext.url
            == "http://hl7.org/fhir/StructureDefinition/elementSource",
            group.extension,
        )
        source_profile_url = (
            None if not source_ext else source_ext.valueUri.split("#")[0]
        )
        if not source_profile_url:
            _logger.warning(
                f"Failed to determine FHIR profile from which the measure group was generated [group_id='{group.id}'] => Dropping group from measure"
            )
            continue
        included_groups.append(group)
        if fds := profile_details.get(source_profile_url):
            included_stratifiers = []
            for strat in group.stratifier:
                strat_code = first(
                    lambda c: c.system == "http://fhir-data-evaluator/strat/system",
                    strat.code.coding,
                ).code
                if fds.get(strat_code):
                    included_stratifiers.append(strat)
                else:
                    _logger.debug(
                        f"No field details exists for stratifier '{strat_code}' => Dropping stratifier from group"
                    )
                    continue
            group.stratifier = included_stratifiers
        else:
            _logger.debug(
                f"No profile details exists for profile '{source_profile_url}' => Dropping group from measure"
            )
            continue
    measure.group = included_groups
    return update_stratifier_ids(measure)


if __name__ == "__main__":
    arg_parser = _configure_argparser()
    args = arg_parser.parse_args()

    project = _setup_project(args.project)

    _logger.info("Generating Availability Measure resource for DSE")
    element_measure = generate_element_availability_for_dse(project)

    measure_file_path = (
        project.output.availability / "Measure-DseElementAvailability.fhir.json"
    )
    _logger.info(f"Writing measure to file @ {measure_file_path}")
    with measure_file_path.open(mode="w", encoding="utf-8") as f:
        f.write(element_measure.model_dump_json())
