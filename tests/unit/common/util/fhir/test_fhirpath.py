import pytest

from common.util.fhir.fhirpath import fhirpath_filter_for_slice
from common.util.fhir.package.manager import FhirPackageManager


@pytest.mark.parametrize(
    argnames="elem_def, profile, expected",
    argvalues=[
        (
            "Specimen.extension:festgestellteDiagnose",
            "https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Specimen",
            "extension('https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Diagnose')",
        ),
        (
            "Observation.component:gene-studied",
            "https://www.medizininformatik-initiative.de/fhir/ext/modul-molgen/StructureDefinition/variante",
            "where(code.coding.exists(system = 'http://loinc.org' and code = '48018-6'))",
        ),
        (
            "Condition.onset[x]:onsetPeriod",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-diagnose/StructureDefinition/Diagnose",
            "ofType(Period)",
        ),
    ],
    ids=["extension-filter", "component-where-filter", "type-filter"],
    indirect=["elem_def", "profile"],
)
def test_fhirpath_filter_for_slice(
    elem_def, profile, expected, package_manager: FhirPackageManager
):
    result = fhirpath_filter_for_slice(elem_def, profile, package_manager)
    assert result == expected
