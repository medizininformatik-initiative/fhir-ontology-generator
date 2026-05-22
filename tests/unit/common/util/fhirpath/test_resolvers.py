from typing import List, Tuple

import pytest
from fhir.resources.R4B.elementdefinition import ElementDefinition

from common.model.fhir.structure_definition import StructureDefinitionSnapshot
from common.util.fhirpath.resolvers import FHIRPathResolver


def chain_repr(
    chain: List[Tuple[StructureDefinitionSnapshot, ElementDefinition]],
) -> List[Tuple[str, str]]:
    return [(sd.url, ed.id) for sd, ed in chain]


class TestFHIRPathResolver:
    @pytest.mark.parametrize(
        ["profile", "expr", "chain"],
        [
            pytest.param(
                "https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Specimen",
                "Specimen.type.coding.slice(%profile, 'sct')",
                [
                    (
                        "https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Specimen",
                        "Specimen.type.coding:sct",
                    )
                ],
                id="mii-cds-specimen-type-sct-slice",
            ),
            pytest.param(
                "https://www.medizininformatik-initiative.de/fhir/core/modul-medikation/StructureDefinition/MedicationAdministration",
                "MedicationAdministration.medication.slice(%profile, 'medicationReference').resolve().code.coding.slice(%profile, 'atcClassDe')",
                [
                    (
                        "https://www.medizininformatik-initiative.de/fhir/core/modul-medikation/StructureDefinition/MedicationAdministration",
                        "MedicationAdministration.medication[x]:medicationReference",
                    ),
                    (
                        "https://www.medizininformatik-initiative.de/fhir/core/modul-medikation/StructureDefinition/Medication",
                        "Medication.code.coding:atcClassDe",
                    ),
                ],
                id="mii-cds-medicationAdministration-slice-ref",
            ),
            pytest.param(
                "https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Specimen",
                "Specimen.extension.slice(%profile, 'festgestellteDiagnose').value.ofType(Reference).resolve().code.coding.slice('https://www.medizininformatik-initiative.de/fhir/core/modul-diagnose/StructureDefinition/Diagnose', 'icd10-gm')",
                [
                    (
                        "https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Specimen",
                        "Specimen.extension:festgestellteDiagnose",
                    ),
                    (
                        "https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Diagnose",
                        "Extension.value[x]",
                    ),
                    (
                        "https://www.medizininformatik-initiative.de/fhir/core/modul-diagnose/StructureDefinition/Diagnose",
                        "Condition.code.coding:icd10-gm",
                    ),
                ],
                id="mii-cds-specimen-festgestellteDiagnose-slice-ext-ref",
            ),
        ],
        indirect=["profile"],
    )
    def test_resolve_path(
        self,
        resolver: FHIRPathResolver,
        profile: StructureDefinitionSnapshot,
        expr: str,
        chain,
    ):
        assert chain_repr(resolver.resolve_path(profile, expr)) == chain
