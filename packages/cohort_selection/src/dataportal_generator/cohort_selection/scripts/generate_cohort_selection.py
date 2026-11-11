import argparse

from common.util.log.functions import get_logger
from common.util.project import Project
from dataportal_generator.cohort_selection.generators.cql_mapping import generate_cql_mapping
from dataportal_generator.cohort_selection.generators.mapping_link import generate_query_criterion_link, \
    contextualize_query_language_mappings
from dataportal_generator.cohort_selection.generators.ui_profile import generate_ui_profiles

_logger = get_logger(__file__)


def configure_args_parser() -> argparse.ArgumentParser:
    """
    Configures the argument parser for the script.
    :return: An ArgumentParser object.
    """
    parser = argparse.ArgumentParser(
        description="Generate cohort selection data"
    )
    parser.add_argument(
        "--project",
        required=True,
        help="Project to generate cohort selection data for",
    )
    parser.add_argument(
        "--ui-profiles", action="store_true", help="Generate UI profiles"
    )
    parser.add_argument(
        "--mapping", action="store_true", help="Generate mappings"
    )
    parser.add_argument(
        "--module", nargs="+", help="Specific modules to generate the cohort selection for"
    )
    return parser


def main(project: Project, generate_ui_profiles: bool = True, generate_mappings: bool = True, modules: list[str] | None = None):
    _logger.info(f"Generating cohort selection data for project '{project.name}'")

    generate_concept_trees(project, remove_unused=True, modules=args.module)

    if args.ui_profiles:
        generate_ui_profiles(project, modules=args.module)

    if args.mapping:
        # Query language-specific mappings
        generate_cql_mapping(project, modules=args.module)
        # Query language mapping criterion linking
        contextualize_query_language_mappings(project)


if __name__ == "__main__":
    parser = configure_args_parser()
    args = parser.parse_args()

    project = Project(name=args.project)

    main(project, generate_ui_profiles=args.ui_profiles, generate_mappings=args.mapping, modules=args.module)
