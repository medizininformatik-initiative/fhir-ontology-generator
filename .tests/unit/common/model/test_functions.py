import pytest
from fhir.resources.R4B.coverage import Coverage
from fhir.resources.R4B.immunization import Immunization
from fhir.resources.R4B.parameters import Parameters
from fhir.resources.R4B.patient import Patient

from common.model.fhir.functions import get_reference_fields


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
