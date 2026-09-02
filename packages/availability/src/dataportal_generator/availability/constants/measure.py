from fhir.resources.R4B.codeableconcept import CodeableConcept
from fhir.resources.R4B.coding import Coding

CC_IN_INITIAL_POPULATION = CodeableConcept(
    coding=[
        Coding(
            system="http://terminology.hl7.org/CodeSystem/measure-population",
            code="initial-population",
            display="Initial Population",
        )
    ]
)

CC_MEASURE_POPULATION = CodeableConcept(
    coding=[
        Coding(
            system="http://terminology.hl7.org/CodeSystem/measure-population",
            code="measure-population",
            display="Measure Population",
        )
    ]
)

CC_MEASURE_OBSERVATION = CodeableConcept(
    coding=[
        Coding(
            system="http://terminology.hl7.org/CodeSystem/measure-population",
            code="measure-observation",
            display="Measure Observation",
        )
    ]
)
