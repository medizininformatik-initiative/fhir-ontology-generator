import pytest
from fhir.resources.R4B.measure import Measure

from common.util.codec.json import load_json
from common.util.project import Project


MEASURE_FILE_NAME = "Measure-CdsElementAvailability.json"


@pytest.skip(reason="Requires FHIRPath utilities")
def test_element_availability(project: Project):
    with project.output.availability / MEASURE_FILE_NAME as measure_f:
        measure = Measure.model_validate_json(load_json(measure_f))

    for group in measure.group:
        for stratifier in group.stratifier:
            pass
