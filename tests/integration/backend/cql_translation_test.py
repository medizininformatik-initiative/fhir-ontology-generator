import subprocess
from pathlib import Path
from textwrap import dedent

import pytest

_TRANSLATOR_TOOL_PATH = (
    Path(__file__).parent / "sq2cql-cli" / "target" / "sq2cql-cli.jar"
)

_GENERATOR_OUTPUT_DIR = Path(__file__).parent / "tmp" / "ontology"
_ALIASES_MAPPING = Path(__file__).parent / "aliases.json"
_FIXED_ARGS = [
    "-cm",
    str(_GENERATOR_OUTPUT_DIR / "mapping_cql.json"),
    "-ct",
    str(_GENERATOR_OUTPUT_DIR / "mapping_tree.json"),
    "-csa",
    str(_ALIASES_MAPPING),
]


def _translate(sq_file_path: Path) -> str:
    return (
        subprocess.check_output(
            [
                "java",
                "-jar",
                str(_TRANSLATOR_TOOL_PATH),
                *_FIXED_ARGS,
                str(sq_file_path),
            ]
        )
        .decode("utf-8")
        .strip()
    )


@pytest.mark.parametrize(
    argnames=["sq_file", "expected"],
    argvalues=[
        pytest.param(
            "BioprobeQuery1Patient1.json",
            """
            library Retrieve version '1.0.0'
            using FHIR version '4.0.0'
            include FHIRHelpers version '4.0.0'
            
            codesystem icd10: 'http://fhir.de/CodeSystem/bfarm/icd-10-gm'
            codesystem snomed: 'http://snomed.info/sct'
            
            context Patient
            
            define "Diagnose B05.3":
              [Condition: Code 'B05.3' from icd10]
            
            define Criterion:
              exists (from [Specimen: Code '122555007' from snomed] S
                with "Diagnose B05.3" C
                  such that S.extension.where(url='https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Diagnose').first().value.as(Reference).reference contains 'Condition/' + C.id
                where ToDate(S.collection.collected as dateTime) in Interval[@2023-11-15T, @2025-01-29T] or
                  S.collection.collected overlaps Interval[@2023-11-15T, @2025-01-29T]) or
              exists (from [Specimen: Code '119298005' from snomed] S
                with "Diagnose B05.3" C
                  such that S.extension.where(url='https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Diagnose').first().value.as(Reference).reference contains 'Condition/' + C.id
                where ToDate(S.collection.collected as dateTime) in Interval[@2023-11-15T, @2025-01-29T] or
                  S.collection.collected overlaps Interval[@2023-11-15T, @2025-01-29T]) or
              exists (from [Specimen: Code '703431007' from snomed] S
                with "Diagnose B05.3" C
                  such that S.extension.where(url='https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Diagnose').first().value.as(Reference).reference contains 'Condition/' + C.id
                where ToDate(S.collection.collected as dateTime) in Interval[@2023-11-15T, @2025-01-29T] or
                  S.collection.collected overlaps Interval[@2023-11-15T, @2025-01-29T])
            
            define InInitialPopulation:
              Criterion
            """,
            id="BioprobeQuery1Patient1",
        ),
        pytest.param(
            "BioprobeQuery2Patient1.json",
            """
            library Retrieve version '1.0.0'
            using FHIR version '4.0.0'
            include FHIRHelpers version '4.0.0'
            
            codesystem snomed: 'http://snomed.info/sct'
            
            context Patient
            
            define Criterion:
              exists [Specimen: Code '122555007' from snomed] or
              exists [Specimen: Code '119298005' from snomed] or
              exists [Specimen: Code '703431007' from snomed]
            
            define InInitialPopulation:
              Criterion
            """,
            id="BioprobeQuery2Patient1",
        ),
        pytest.param(
            "Consent_MiiConsent_Patient1_Q1.json",
            """
            library Retrieve version '1.0.0'
            using FHIR version '4.0.0'
            include FHIRHelpers version '4.0.0'
            
            codesystem consent: 'urn:oid:2.16.840.1.113883.3.1937.777.24.5.3'
            
            context Patient
            
            define Criterion:
              exists (from [Consent] C
                where exists (from C.provision.provision.code C
                    where C ~ Code '2.16.840.1.113883.3.1937.777.24.5.3.6' from consent))
            
            define InInitialPopulation:
              Criterion
            """,
            id="Consent_MiiConsent_Patient1_Q1",
        ),
        pytest.param(
            "Diagnose_AlphaID_Patient1_Q1.json",
            """
            library Retrieve version '1.0.0'
            using FHIR version '4.0.0'
            include FHIRHelpers version '4.0.0'
            
            codesystem alphaid: 'http://fhir.de/CodeSystem/bfarm/alpha-id'
            
            context Patient
            
            define Criterion:
              exists (from [Condition: Code 'I29578' from alphaid] C
                where ToDate(C.recordedDate as dateTime) in Interval[@2024-02-21T, @2024-02-21T])
            
            define InInitialPopulation:
              Criterion
            """,
            id="Diagnose_AlphaID_Patient1_Q1",
        ),
        pytest.param(
            "Diagnose_ICD10_Patient1_Q1.json",
            """
            library Retrieve version '1.0.0'
            using FHIR version '4.0.0'
            include FHIRHelpers version '4.0.0'
            
            codesystem icd10: 'http://fhir.de/CodeSystem/bfarm/icd-10-gm'
            
            context Patient
            
            define Criterion:
              exists (from [Condition: Code 'B05.3' from icd10] C
                where ToDate(C.recordedDate as dateTime) in Interval[@2024-02-21T, @2024-02-21T])
            
            define InInitialPopulation:
              Criterion
            """,
            id="Diagnose_ICD10_Patient1_Q1",
        ),
        pytest.param(
            "Diagnose_SCT_Patient1_Q1.json",
            """
            library Retrieve version '1.0.0'
            using FHIR version '4.0.0'
            include FHIRHelpers version '4.0.0'
            
            codesystem snomed: 'http://snomed.info/sct'
            
            context Patient
            
            define Criterion:
              exists (from [Condition: Code '13420004' from snomed] C
                where ToDate(C.recordedDate as dateTime) in Interval[@2024-02-21T, @2024-02-21T])
            
            define InInitialPopulation:
              Criterion
            """,
            id="Diagnose_SCT_Patient1_Q1",
        ),
        pytest.param(
            "Encounter_Patient1_Q1.json",
            """
            library Retrieve version '1.0.0'
            using FHIR version '4.0.0'
            include FHIRHelpers version '4.0.0'
            
            codesystem fachabteilungsschluessel: 'http://fhir.de/CodeSystem/dkgev/Fachabteilungsschluessel'
            codesystem kontaktart: 'http://fhir.de/CodeSystem/kontaktart-de'
            codesystem kontaktebene: 'http://fhir.de/CodeSystem/Kontaktebene'
            codesystem v3actcode: 'http://terminology.hl7.org/CodeSystem/v3-ActCode'
            
            context Patient
            
            define Criterion:
              exists (from [Encounter: class ~ Code 'IMP' from v3actcode] E
                where E.serviceType ~ Code '0100' from fachabteilungsschluessel and
                  exists (from E.type C
                    where C ~ Code 'einrichtungskontakt' from kontaktebene) and
                  exists (from E.type C
                    where C ~ Code 'normalstationaer' from kontaktart) and
                  E.period overlaps Interval[@2024-02-14T, @2024-02-22T])
            
            define InInitialPopulation:
              Criterion
            """,
            id="Encounter_Patient1_Q1",
        ),
        pytest.param(
            "ICU_ArteriellerBlutdruck_Patient1_Q1.json",
            """
            library Retrieve version '1.0.0'
            using FHIR version '4.0.0'
            include FHIRHelpers version '4.0.0'
            
            codesystem loinc: 'http://loinc.org'
            
            context Patient
            
            define Criterion:
              exists (from [Observation: Code '85354-9' from loinc] O
                where ToDate(O.effective as dateTime) in Interval[@2024-02-10T, @2024-02-25T] or
                  O.effective overlaps Interval[@2024-02-10T, @2024-02-25T])
            
            define InInitialPopulation:
              Criterion
            """,
            id="ICU_ArteriellerBlutdruck_Patient1_Q1",
        ),
        pytest.param(
            "ICU_Atemfrequenz_Patient1_Q1.json",
            """
            library Retrieve version '1.0.0'
            using FHIR version '4.0.0'
            include FHIRHelpers version '4.0.0'
            
            codesystem loinc: 'http://loinc.org'
            
            context Patient
            
            define Criterion:
              exists (from [Observation: Code '9279-1' from loinc] O
                where ToDate(O.effective as dateTime) in Interval[@2015-02-20T, @9999-12-31T] or
                  O.effective overlaps Interval[@2015-02-20T, @9999-12-31T])
            
            define InInitialPopulation:
              Criterion
            """,
            id="ICU_Atemfrequenz_Patient1_Q1",
        ),
        pytest.param(
            "ICU_Herzfrequenz_Patient1_Q1.json",
            """
            library Retrieve version '1.0.0'
            using FHIR version '4.0.0'
            include FHIRHelpers version '4.0.0'
            
            codesystem loinc: 'http://loinc.org'
            
            context Patient
            
            define Criterion:
              exists (from [Observation: Code '8867-4' from loinc] O
                where ToDate(O.effective as dateTime) in Interval[@2015-02-20T, @9999-12-31T] or
                  O.effective overlaps Interval[@2015-02-20T, @9999-12-31T])
            
            define InInitialPopulation:
              Criterion
            """,
            id="ICU_Herzfrequenz_Patient1_Q1",
        ),
        pytest.param(
            "ICU_Koepergewicht_Patient1_Q1.json",
            """
            library Retrieve version '1.0.0'
            using FHIR version '4.0.0'
            include FHIRHelpers version '4.0.0'
            
            codesystem loinc: 'http://loinc.org'
            
            context Patient
            
            define Criterion:
              exists (from [Observation: Code '29463-7' from loinc] O
                where ToDate(O.effective as dateTime) in Interval[@2024-02-10T, @2024-02-25T] or
                  O.effective overlaps Interval[@2024-02-10T, @2024-02-25T])
            
            define InInitialPopulation:
              Criterion
            """,
            id="ICU_Koerpergewicht_Patient1_Q1",
        ),
        pytest.param(
            "ICU_Koerpergroesse_Patient1_Q1.json",
            """
            library Retrieve version '1.0.0'
            using FHIR version '4.0.0'
            include FHIRHelpers version '4.0.0'
            
            codesystem loinc: 'http://loinc.org'
            
            context Patient
            
            define Criterion:
              exists (from [Observation: Code '8302-2' from loinc] O
                where ToDate(O.effective as dateTime) in Interval[@0001-01-01T, @2025-04-07T] or
                  O.effective overlaps Interval[@0001-01-01T, @2025-04-07T])
            
            define InInitialPopulation:
              Criterion
            """,
            id="ICU_Koerpergroesse_Patient1_Q1",
        ),
        pytest.param(
            "ICU_spo2-pulsoxymetrie_Patient1_Q1.json",
            """
            library Retrieve version '1.0.0'
            using FHIR version '4.0.0'
            include FHIRHelpers version '4.0.0'
            
            codesystem loinc: 'http://loinc.org'
            
            context Patient
            
            define Criterion:
              exists (from [Observation: Code '59408-5' from loinc] O
                where ToDate(O.effective as dateTime) in Interval[@2015-02-20T, @9999-12-31T] or
                  O.effective overlaps Interval[@2015-02-20T, @9999-12-31T])
            
            define InInitialPopulation:
              Criterion
            """,
            id="ICU_spo2-pulsoxymetrie_Patient1_Q1",
        ),
        pytest.param(
            "MedicationAdministration_Patient1_Q1.json",
            """
            library Retrieve version '1.0.0'
            using FHIR version '4.0.0'
            include FHIRHelpers version '4.0.0'
            
            codesystem atc: 'http://fhir.de/CodeSystem/bfarm/atc'
            
            context Unfiltered
            
            define J01XA04Ref:
              from [Medication: Code 'J01XA04' from atc] M
                return 'Medication/' + M.id
            
            context Patient
            
            define Criterion:
              exists (from [MedicationAdministration] M
                where M.medication.reference in J01XA04Ref and
                  (ToDate(M.effective as dateTime) in Interval[@2024-02-15T, @2024-02-17T] or
                  M.effective overlaps Interval[@2024-02-15T, @2024-02-17T]))
            
            define InInitialPopulation:
              Criterion
            """,
            id="MedicationAdministration_Patient1_Q1",
        ),
        pytest.param(
            "MedicationRequest_Patient1_Q1.json",
            """
            library Retrieve version '1.0.0'
            using FHIR version '4.0.0'
            include FHIRHelpers version '4.0.0'
            
            codesystem atc: 'http://fhir.de/CodeSystem/bfarm/atc'
            
            context Unfiltered
            
            define J01XA04Ref:
              from [Medication: Code 'J01XA04' from atc] M
                return 'Medication/' + M.id
            
            context Patient
            
            define Criterion:
              exists (from [MedicationRequest] M
                where M.medication.reference in J01XA04Ref and
                  ToDate(M.authoredOn as dateTime) in Interval[@2024-02-16T, @2024-02-16T])
            
            define InInitialPopulation:
              Criterion
            """,
            id="MedicationRequest_Patient1_Q1",
        ),
        pytest.param(
            "MedicationStatement_Patient1_Q1.json",
            """
            library Retrieve version '1.0.0'
            using FHIR version '4.0.0'
            include FHIRHelpers version '4.0.0'
            
            codesystem atc: 'http://fhir.de/CodeSystem/bfarm/atc'
            
            context Unfiltered
            
            define B01AC06Ref:
              from [Medication: Code 'B01AC06' from atc] M
                return 'Medication/' + M.id
            
            context Patient
            
            define Criterion:
              exists (from [MedicationStatement] M
                where M.medication.reference in B01AC06Ref and
                  (ToDate(M.effective as dateTime) in Interval[@2020-08-30T, @2020-08-30T] or
                  M.effective overlaps Interval[@2020-08-30T, @2020-08-30T]))
            
            define InInitialPopulation:
              Criterion
            """,
            id="MedicationStatement_Patient1_Q1",
        ),
    ],
)
def test_sq_to_cql_translation(sq_file, expected):
    assert (
        _translate(Path(__file__).parent / "test-queries" / sq_file)
        == dedent(expected).strip()
    )
