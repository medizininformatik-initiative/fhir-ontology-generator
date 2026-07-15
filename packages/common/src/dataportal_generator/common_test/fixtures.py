import os
import shutil
import zipfile
from pathlib import Path
from types import ModuleType
from typing import Tuple, Optional

import cachetools
import pytest
import requests
from _pytest.fixtures import FixtureRequest, FixtureLookupError
from fhir.resources.R4B.bundle import Bundle
from fhir.resources.R4B.elementdefinition import ElementDefinition

from dataportal_generator.common.model.fhir.idx_structure_definition import IdxStructureDefinition
from dataportal_generator.common.util.collections import first
from dataportal_generator.common.fhir.package_manager import FhirPackageManager
from dataportal_generator.common.util.http.terminology.client import FhirTerminologyClient
from dataportal_generator.common.log.functions import get_logger
from dataportal_generator.common.model.project import Project

_logger = get_logger(__file__)


_PROJECT_TEMPLATE_REL_PATH = Path("resources", "project")

_MII_CDS_TEST_DATA_PREFIX = "kds-testdata"
_MII_CDS_TEST_DATA_BUNDLES_PREFIX = "testdata-bundles-ndjson"


def __repository_root_dir(request) -> str:
    return request.config.rootpath


@pytest.fixture(scope="session")
def repository_root_dir(request) -> str:
    return __repository_root_dir(request)


def __validate_project_template(template_dir: Path):
    try:
        if not template_dir.exists() or template_dir.is_dir():
            raise FileNotFoundError("Missing project template directory")
        conf_file_path = template_dir / "config.yml"
        conf_file_path = (
            conf_file_path
            if conf_file_path.exists()
            else (template_dir / "config.yaml")
        )
        if not conf_file_path.exists() and conf_file_path.is_file():
            raise FileNotFoundError("Could not find config file")
        package_file_path = template_dir / "package.json"
        if not package_file_path.exists() and package_file_path.is_file():
            raise FileNotFoundError("Could not find package.json file")
    except Exception as exc:
        raise Exception(f"Invalid project template @ {repr(template_dir)}") from exc


def __tmp_project(target_location: Path, template: Optional[Path] = None) -> Project:
    p_path = target_location / ".tmp" / "project"
    shutil.rmtree(p_path, ignore_errors=True)
    if template:
        shutil.copytree(template, p_path)
    else:
        p_path.mkdir(parents=True, exist_ok=True)
    p = Project(path=p_path)
    p.package_manager.restore(inflate=True, lenient=True)
    return p


@cachetools.cached(cache={}, key=lambda mp: mp.absolute())
def _module_project(module_path: Path) -> Project:
    _logger.debug(f"Creating project for module {repr(module_path)}")
    project_template_path = module_path / _PROJECT_TEMPLATE_REL_PATH
    return __tmp_project(module_path, project_template_path)


def _rootpath_tests_dir(request_path: Path) -> Path:
    curr_dir = request_path.parent
    while curr_dir.name != "tests":
        if curr_dir == curr_dir.parent:
            raise FileNotFoundError(
                f"No directory test root directory 'tests' on path {repr(request_path)}"
            )
        curr_dir = curr_dir.parent
    return curr_dir
    

@pytest.fixture(scope="module")
def rootpath_tests_dir(request: FixtureRequest) -> Path:
    """
    Provides module test dir path (e.g. ``packages/<module_name>/tests``) as ``pathlib.Path`` object
    """
    return _rootpath_tests_dir(request.path)


@pytest.fixture(scope="module")
def project(request: FixtureRequest) -> Project:
    """
    Provides a ``Project`` object for the given fixture request depending on the resolution mode defined in it
    """
    try:
        resolution_mode = request.getfixturevalue("project")
    except FixtureLookupError:
        resolution_mode = getattr(request.module, "PROJECT_RESOLUTION", "default")

    if resolution_mode == "module" or resolution_mode == "default":
        mod_dir = request.path.parent
        if resolution_mode == "module":
            return _module_project(mod_dir)
    if resolution_mode == "ancestor" or resolution_mode == "default":
        mod_dir = request.path.parent.parent
        root_mod_dir = _rootpath_tests_dir(request.path)
        while mod_dir != root_mod_dir:
            if (mod_dir / _PROJECT_TEMPLATE_REL_PATH).exists():
                return _module_project(mod_dir)
            mod_dir = mod_dir.parent
    if resolution_mode == "global" or resolution_mode == "default":
        root_mod_dir = _rootpath_tests_dir(request.path)
        try:
            return _module_project(root_mod_dir)
        except FileNotFoundError as err:
            raise FileNotFoundError(f"Missing default test project for module @ {repr(root_mod_dir.parent)}") from err

    raise ValueError(
        f"Unknown project resolution mode '{resolution_mode}'. Expected one of 'default', 'global', 'module', 'ancestor'"
    )


@pytest.fixture(scope="module")
def package_manager(project: Project) -> FhirPackageManager:
    """
    Provides the ``FhirPackageManager`` object of the ``Project`` object provided by the ``project`` fixture
    """
    return project.package_manager


@pytest.fixture(scope="module")
def current_module(request: FixtureRequest) -> ModuleType:
    return request.module


@pytest.fixture(scope="session")
def cds_test_data(repository_root_dir: str) -> Tuple[Path, Path]:
    try:
        mii_cds_test_data_version = os.environ["MII_CDS_TEST_DATA_VERSION"]
    except KeyError as err:
        raise KeyError(
            "Provide a MII CDS test data version to use via environment variable 'MII_CDS_TEST_DATA_VERSION'") from err

    _logger.info(
        f"Setting up MII CDS test data with version {mii_cds_test_data_version}"
    )
    test_data_path = Path(repository_root_dir, ".tests", ".tmp", "mii_cds_test_data")
    if test_data_path.exists() and test_data_path.is_dir():
        _logger.debug("MII CDS test data is already present")
    else:
        try:
            _logger.debug(
                f"Resolving release ID from tag name '{mii_cds_test_data_version}'"
            )
            response = requests.get(
                "https://api.github.com/repos/medizininformatik-initiative/mii-testdata/releases",
                headers={"Accept": "application/vnd.github+json"},
            )
            response.raise_for_status()
            if release_entry := first(
                lambda e: e.get("tag_name") == mii_cds_test_data_version,
                response.json(),
            ):
                release_id = release_entry["id"]
            else:
                raise Exception(
                    f"No such release with tag name '{mii_cds_test_data_version}'"
                )

            _logger.debug(
                f"Retrieving release artifact data from release '{release_id}'"
            )
            url = f"https://api.github.com/repos/medizininformatik-initiative/mii-testdata/releases/{release_id}/assets"
            response = requests.get(
                url, headers={"Accept": "application/vnd.github+json"}
            )
            response.raise_for_status()
            assets_info = {
                asset.get("name"): asset.get("browser_download_url")
                for asset in response.json()
            }

            if not (
                test_data_entry := first(
                    lambda e: e[0].startswith(_MII_CDS_TEST_DATA_PREFIX),
                    assets_info.items(),
                )
            ):
                _logger.warning("No MII CDS test data archive found")
            if not (
                test_data_bundles_entry := first(
                    lambda e: e[0].startswith(_MII_CDS_TEST_DATA_BUNDLES_PREFIX),
                    assets_info.items(),
                )
            ):
                _logger.warning("No MII CDS test data bundles archive found")

            test_data_path.mkdir(parents=True, exist_ok=True)
            for entry in [test_data_entry, test_data_bundles_entry]:
                response = requests.get(entry[1], timeout=5)
                file_name = entry[0]
                file_path = test_data_path / file_name
                with file_path.open(mode="wb") as file:
                    file.write(response.content)
                with zipfile.ZipFile(file_path, "r") as zip_ref:
                    zip_ref.extractall(test_data_path)
                os.remove(file_path)
        except Exception as exc:
            raise Exception(f"Fetching of MII CDS test data. Details: {exc}") from exc

    dir_content = list(test_data_path.iterdir())
    test_data_path = first(
        lambda p: p.name.startswith(_MII_CDS_TEST_DATA_PREFIX), dir_content
    )
    assert test_data_path, "Missing test data"
    bundles_path = first(
        lambda p: p.name.startswith(_MII_CDS_TEST_DATA_BUNDLES_PREFIX), dir_content
    )
    if bundles_path:
        bundles_path = next(bundles_path.iterdir())
    assert bundles_path, "Missing test data bundles"

    return test_data_path, bundles_path


@pytest.fixture(scope="session")
def cds_test_data_bundles(cds_test_data: Tuple[Path, Path]) -> list[Bundle]:
    bundles = []
    for bundle_file_path in (cds_test_data[0] / "resources").iterdir():
        if bundle_file_path.is_file() and bundle_file_path.name.startswith("Bundle"):
            with bundle_file_path.open(mode="r", encoding="utf-8") as file:
                bundles.append(Bundle.model_validate_json(file.read(), strict=True))
    return bundles


@pytest.fixture(scope="session")
def cds_test_data_ndjson_bundles(cds_test_data: Tuple[Path, Path]) -> list[Bundle]:
    with cds_test_data[1].open(mode="r", encoding="utf-8") as file:
        return [
            Bundle.model_validate_json(line, strict=True)
            for line in file
            if line.strip()
        ]


@pytest.fixture
def struct_def(request, package_manager: FhirPackageManager) -> IdxStructureDefinition:
    """
    Fixture that can be used for indirect parameters named 'struct_def' to resolve any `string` typed value as a
    profile URL or pass on any `StructureDefinition` typed parameters
    """
    match request.param:
        case str(profile_url):
            return package_manager.find({"url": profile_url})
        case IdxStructureDefinition() as struct_def:
            return struct_def
        case _ as param:
            raise ValueError(
                f"Fixture 'struct_def' does not support indirect parameters of type {type(param)} [supported_types=[{repr(str)}, {repr(IdxStructureDefinition)}]]"
            )


@pytest.fixture
def elem_def(request, struct_def) -> ElementDefinition:
    """
    Fixture that can be used for indirect parameters named 'elem_def' to resolve any `string` typed value as a
    profile URL or pass on any `ElementDefinition` typed parameters
    """
    match request.param:
        case str(elem_id):
            return struct_def.get_element_by_id(elem_id)
        case ElementDefinition() as elem_def:
            return elem_def
        case _ as param:
            raise ValueError(
                f"Fixture 'elem_def' does not support indirect parameters of type {type(param)} [supported_types=[{repr(str)}, {repr(ElementDefinition)}]]"
            )


@pytest.fixture(scope="module")
def client(project: Project) -> FhirTerminologyClient:
    return FhirTerminologyClient.from_project(project)
