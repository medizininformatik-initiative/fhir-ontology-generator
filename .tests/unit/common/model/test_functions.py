from typing import List

import pytest
from fhir.resources.R4B.coverage import Coverage
from fhir.resources.R4B.immunization import Immunization
from fhir.resources.R4B.parameters import Parameters
from fhir.resources.R4B.patient import Patient

from common.model.fhir.functions import get_reference_fields
from common.model.fhir.structure_definition import StructureDefinitionSnapshot
from common.util.structure_definition.functions import (
    get_available_slices,
    get_available_slice_names,
)


@pytest.mark.parametrize(
    argnames="fhir_model_cls, filter_types, expected",
    argvalues=[
        (Parameters, None, []),
        (Parameters, {"Patient"}, []),
        (Patient, None, ["managingOrganization"]),
        (Immunization, None, ["encounter", "location", "manufacturer", "patient"]),
        (Immunization, {"Patient"}, ["patient"]),
        (Coverage, None, ["beneficiary", "payor", "policyHolder", "subscriber"]),
        (Coverage, {"Patient"}, ["beneficiary", "payor", "policyHolder", "subscriber"]),
    ],
)
def test_get_reference_fields(fhir_model_cls, filter_types, expected):
    result = [fi.alias for fi in get_reference_fields(fhir_model_cls, filter_types)]
    assert result == expected


@pytest.mark.parametrize(
    argnames="profile, elem_id, expected_slices, expected_slice_names",
    argvalues=[
        (
            "https://www.medizininformatik-initiative.de/fhir/core/modul-diagnose/StructureDefinition/Diagnose",
            "Condition.code.coding",
            [
                "Condition.code.coding:icd10-gm",
                "Condition.code.coding:alpha-id",
                "Condition.code.coding:sct",
                "Condition.code.coding:orphanet",
            ],
            ["orphanet", "sct", "icd10-gm", "alpha-id"],
        ),
        (
            "https://www.medizininformatik-initiative.de/fhir/core/modul-labor/StructureDefinition/ObservationLab",
            "Observation.category.coding",
            [
                "Observation.category.coding:loinc-observation",
                "Observation.category.coding:observation-category",
            ],
            ["observation-category", "loinc-observation"],
        ),
        (
            "https://gematik.de/fhir/isik/StructureDefinition/ISiKBerichtBundle",
            "Bundle.entry",
            [
                "Bundle.entry:Composition",
            ],
            ["Composition"],
        ),
        (
            "https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Specimen",
            "Specimen.collection.bodySite.coding",
            [
                "Specimen.collection.bodySite.coding:sct",
                "Specimen.collection.bodySite.coding:icd-o-3",
            ],
            ["sct", "icd-o-3"],
        ),
        (
            "https://www.medizininformatik-initiative.de/fhir/ext/modul-icu/StructureDefinition/arterieller-blutdruck",
            "Observation.component:SystolicBP.code.coding",
            [
                "Observation.component:SystolicBP.code.coding:loinc",
                "Observation.component:SystolicBP.code.coding:sct",
                "Observation.component:SystolicBP.code.coding:IEEE-11073",
            ],
            ["loinc", "sct", "IEEE-11073"],
        ),
    ],
    ids=[
        "Test Condition.code.coding slices",
        "Test Observation.category",
        "Test Bundle.entry",
        "Test Specimen.collection.bodySite.coding",
        "Test nested slices Observation.component:SystolicBP.code.coding",
    ],
    indirect=["profile"],
)
def test_get_available_slices(
    profile: StructureDefinitionSnapshot,
    elem_id: str,
    expected_slices: List[str],
    expected_slice_names: List[str],
):
    assert sorted(expected_slices) == sorted(
        [slice_def.id for slice_def in get_available_slices(elem_id, profile)]
    )
    assert sorted(expected_slice_names) == sorted(
        get_available_slice_names(elem_id, profile)
    )
