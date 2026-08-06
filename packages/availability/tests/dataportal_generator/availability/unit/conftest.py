from pathlib import Path

import pytest

from dataportal_generator.common.exceptions import NotFoundError
from dataportal_generator.common.model.fhir.idx_structure_definition import IdxStructureDefinition, index_struct_def
from dataportal_generator.common.fhir.package_manager import FhirPackageManager

TEST_PROFILE_URL = "https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Specimen"


@pytest.fixture(scope="session")
def resources_dir() -> Path:
    return Path(__file__).parent / "resources"


@pytest.fixture(scope="session")
def test_profile(package_manager: FhirPackageManager) -> IdxStructureDefinition:
    idx_pattern = {"url": TEST_PROFILE_URL}
    if p := package_manager.find(idx_pattern) is not None:
        return index_struct_def(p)
    else:
        raise NotFoundError(
            f"Cannot find structure definition of test profile '{idx_pattern['url']}'"
        )