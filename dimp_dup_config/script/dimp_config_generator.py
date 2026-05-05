import argparse
from pathlib import Path

from ruamel.yaml import YAML

from common.util.log.functions import get_logger
from common.util.project import Project
from dimp_dup_config.core.dimp_config_functions import DimpConfig, DimpConfigGenerator

_logger = get_logger(__file__)


def _next_output_file(output_dir: Path) -> Path:
    base = output_dir / "dimp_config.yaml"
    if not base.exists():
        return base

    index = 1
    while (candidate := output_dir / f"dimp_config_{index}.yaml").exists():
        index += 1
    return candidate


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

    yaml = YAML()
    yaml.default_style = None
    yaml.width = 4096
    yaml.allow_unicode = True
    yaml.preserve_quotes = False

    dimp_config: DimpConfig = DimpConfigGenerator(project).generate_dimp_config()

    output_file = _next_output_file(project.output.dimp_config.path)
    with open(output_file, mode="x", encoding="utf-8") as f:
        yaml.dump(dimp_config.to_dimp_format(), f)

    _logger.info(f"Wrote DIMP config to {output_file}")
