from typing import Tuple, List

import pytest
from fhir.resources.R4B.elementdefinition import ElementDefinition

from common.model.fhir.structure_definition import StructureDefinitionSnapshot
from common.util.fhir.package.manager import FhirPackageManager
from common.util.fhirpath.resolvers import FHIRPathResolver


@pytest.fixture(scope="module")
def resolver(package_manager: FhirPackageManager) -> FHIRPathResolver:
    return FHIRPathResolver(package_manager)