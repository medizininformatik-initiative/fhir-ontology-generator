import os
import shutil
from pathlib import Path

import pytest
from _pytest.python import Metafunc
from fhir.resources.R4B.bundle import Bundle
from fhir.resources.R4B.measure import Measure

from common.util.log.functions import get_logger
from common.util.fhir.package.manager import FhirPackageManager
from common.util.project import Project
from common.util.test.fhir import download_and_unzip_kds_test_data

_logger = get_logger(__name__)


_CODING_MEASURE_FILE_NAME = "Measure-CdsCodingAvailability.fhir.json"
_ELEMENT_MEASURE_FILE_NAME = "Measure-CdsElementAvailability.fhir.json"

_MEASURES = [_CODING_MEASURE_FILE_NAME, _ELEMENT_MEASURE_FILE_NAME]


def __test_dir() -> Path:
    return Path(os.path.dirname(os.path.realpath(__file__)))


@pytest.fixture(scope="session")
def test_dir() -> Path:
    return __test_dir()


@pytest.fixture(scope="session")
def package_manager(project: Project) -> FhirPackageManager:
    project.package_manager.restore(inflate=True)
    return project.package_manager


@pytest.fixture(scope="session")
def tmp_dir(test_dir: Path):
    mask = os.umask(0)
    tmp_dir = test_dir / ".tmp"
    try:
        tmp_dir.mkdir(mode=0o777, parents=True, exist_ok=True)
        (tmp_dir / "input").mkdir(mode=0o777, exist_ok=True)
        (tmp_dir / "output").mkdir(mode=0o777, exist_ok=True)
        yield tmp_dir
    finally:

        shutil.rmtree(tmp_dir, ignore_errors=True)
        os.umask(mask)


@pytest.fixture
def measure(request, project: Project) -> Measure:
    fp = project.output.availability / request.param
    if not fp.exists() and not fp.is_file():
        raise FileNotFoundError(f"Cannot find element measure file @ {fp}")
    with fp.open(mode="r", encoding="utf-8") as f:
        measure = Measure.model_validate_json(f.read())
    return measure


@pytest.fixture(scope="session")
def test_data_bundle(tmp_dir: Path) -> Bundle:
    data_dir = tmp_dir / "test_data"
    data_dir.mkdir(exist_ok=True, parents=True)
    download_and_unzip_kds_test_data(data_dir)
    bundle_file_name = "Bundle-mii-exa-test-data-bundle.json"
    bundle_path = next(data_dir.glob(f"**/{bundle_file_name}"), None)
    if not bundle_path:
        raise FileNotFoundError(
            f"Cannot find bundle file '{bundle_file_name}' in {data_dir}"
        )
    with bundle_path.open(mode="r", encoding="utf-8") as f:
        bundle = Bundle.model_validate_json(f.read())
    return bundle


def pytest_generate_tests(metafunc: Metafunc):
    if "test_stratifier_fhirpath_expression_validity" == metafunc.definition.name:
        params = [pytest.param(measure_fn) for measure_fn in _MEASURES]
        metafunc.parametrize(
            argnames=["measure"],
            argvalues=params,
            indirect=["measure"],
            ids=[measure_fn.split(".")[0] for measure_fn in _MEASURES],
            scope="session",
        )

    if "test_generating_measure_report" == metafunc.definition.name:
        params = [
            pytest.param(measure_fn, None, None, None) for measure_fn in _MEASURES
        ]
        metafunc.parametrize(
            argnames=["measure", "tmp_dir", "test_dir", "test_data_bundle"],
            argvalues=params,
            indirect=["measure", "tmp_dir", "test_dir", "test_data_bundle"],
            ids=[measure_fn.split(".")[0] for measure_fn in _MEASURES],
            scope="session",
        )
