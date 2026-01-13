import functools
from pathlib import Path

import cachetools
import pytest
from _pytest.fixtures import FixtureRequest, FixtureLookupError
from fhir.resources.R4B.elementdefinition import ElementDefinition
from fhir.resources.R4B.structuredefinition import StructureDefinition

from common.util.fhir.package.manager import FhirPackageManager
from common.util.project import Project


__PROJECT_INDICATORS__ = {"config.yml", "config.yaml", "package.json"}


def __repository_root_dir(request) -> str:
    return request.config.rootpath


@pytest.fixture(scope="session")
def repository_root_dir(request) -> str:
    return __repository_root_dir(request)


@functools.cache
def _global_project() -> Project:
    p = Project(path=Path(__file__).parent)
    p.package_manager.restore(inflate=True)
    return p


@cachetools.cached(cache={}, key=lambda mp: mp.abolute())
def _module_project(module_path: Path) -> Project:
    p = Project(path=module_path)
    p.package_manager.restore(inflate=True)
    return p


@pytest.fixture(scope="module")
def project(request: FixtureRequest) -> Project:
    try:
        resolution_mode = request.getfixturevalue("project")
    except FixtureLookupError:
        resolution_mode = getattr(request.module, "PROJECT_RESOLUTION", "default")

    if resolution_mode == "module" or resolution_mode == "default":
        mod_dir = request.path.parent
        if resolution_mode == "module" or any(
            [f.name in __PROJECT_INDICATORS__ for f in mod_dir.iterdir()]
        ):
            return _module_project(path=mod_dir)
    if resolution_mode == "ancestor" or resolution_mode == "default":
        mod_dir = request.path.parent.parent
        root_mod_dir = Path(__file__).parent
        while mod_dir != root_mod_dir:
            # Check if there is some form of project config in the module
            if any([f.name in __PROJECT_INDICATORS__ for f in mod_dir.iterdir()]):
                return _module_project(mod_dir)
            mod_dir = mod_dir.parent
    if resolution_mode == "global" or resolution_mode == "default":
        return _global_project()

    raise ValueError(
        f"Unknown project resolution mode '{resolution_mode}'. Expected one of 'default', 'global', 'module', 'ancestor'"
    )


@pytest.fixture(scope="module")
def package_manager(project: Project) -> FhirPackageManager:
    return project.package_manager


@pytest.fixture
def profile(request, package_manager: FhirPackageManager):
    """
    Fixture that can be used for indirect parameters named 'profile' to resolve any `string` typed value as a
    profile URL or pass on any `StructureDefinition` typed parameters
    """
    match request.param:
        case str() as profile_url:
            return package_manager.find({"url": profile_url})
        case StructureDefinition() as struct_def:
            return struct_def
        case _ as param:
            raise ValueError(
                f"Fixture 'profile' does not support indirect parameters of type {type(param)} [supported_types=[{type(str)}, {type(StructureDefinition)}]]"
            )


@pytest.fixture
def elem_def(request, profile):
    """
    Fixture that can be used for indirect parameters named 'elem_def' to resolve any `string` typed value as a
    profile URL or pass on any `ElementDefinition` typed parameters
    """
    match request.param:
        case str() as elem_id:
            return profile.get_element_by_id(elem_id)
        case ElementDefinition() as elem_def:
            return elem_def
        case _ as param:
            raise ValueError(
                f"Fixture 'elem_def' does not support indirect parameters of type {type(param)} [supported_types=[{type(str)}, {type(ElementDefinition)}]]"
            )
