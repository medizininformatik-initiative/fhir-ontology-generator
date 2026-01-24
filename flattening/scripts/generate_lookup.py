from common.util.http.terminology.client import FhirTerminologyClient
from common.util.log.functions import get_logger
from common.util.project import Project
from flattening.core.flattening import generate_flattening_lookup

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


if __name__ == '__main__':
    project = _setup_project("fdpg-ontology")
    generate_flattening_lookup(
        project.package_manager,
        FhirTerminologyClient.from_project(project)
    )
