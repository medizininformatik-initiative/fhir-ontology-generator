import pathlib
from datetime import datetime, UTC
from typing import Callable

from _pytest.fixtures import FixtureRequest
from fhir.resources.R4B.measure import Measure
from fhir.resources.R4B.meta import Meta

from dataportal_generator.availability.core.element_availability import make_stratifier_codes_fde_compatible
from dataportal_generator.availability.core.element_availability import generate_measure
from dataportal_generator.availability_test.contracts import MeasureContractTests


def element_availability_measure(request: FixtureRequest) -> Measure:
    project = request.getfixturevalue("project")
    measure = generate_measure(
        project.package_manager,
        id="TestElementAvailabilityMeasure",
        meta=Meta(
            profile=[
                "http://hl7.org/fhir/us/cqfmeasures/StructureDefinition/cv-measure-cqfm"
            ]
        ),
        url="https://medizininformatik-initiative.de/fhir/fdpg/Measure/TestElementAvailabilityMeasure",
        name="TestElementAvailabilityMeasure",
        title="Test Element Availability Measure",
        status="active",
        experimental=False,
        date=datetime.now(UTC),
        publisher="FDPG-Plus",
        description="Test FHIR Element Availability Measure for running integration tests",
    )
    make_stratifier_codes_fde_compatible(request.getfixturevalue("package_manager"), measure)
    with pathlib.Path("/home/confi/Projects/fhir-ontology-generator/.tmp/measure.json").open(mode="w+", encoding="utf-8") as f:
        f.write(measure.model_dump_json(indent=2))
    return measure


class TestAvailabilityMeasureGeneration(MeasureContractTests):
    @classmethod
    def measures(cls) -> list[Callable[[FixtureRequest], Measure]]:
        return [element_availability_measure]