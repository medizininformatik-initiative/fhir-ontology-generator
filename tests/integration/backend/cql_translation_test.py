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


@pytest.fixture(scope="session", autouse=True)
def translator_tool_exists():
    if not _TRANSLATOR_TOOL_PATH.exists():
        raise FileNotFoundError(
            f"Missing translator tool JAR file @ {_TRANSLATOR_TOOL_PATH}"
        )


def _translate(sq_file_path: Path) -> str:
    return (
        subprocess.check_output(
            [
                "java",
                "-jar",
                str(_TRANSLATOR_TOOL_PATH),
                *_FIXED_ARGS,
                str(sq_file_path),
            ],
            stderr=subprocess.STDOUT,
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
        pytest.param(
            "Mikrobio_Empfindlichkeit_Patient1_Q1.json",
            """
            library Retrieve version '1.0.0'
            using FHIR version '4.0.0'
            include FHIRHelpers version '4.0.0'
            
            codesystem loinc: 'http://loinc.org'
            codesystem snomed: 'http://snomed.info/sct'
            codesystem v3ObservationInterpretation: 'http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation'
            
            context Patient
            
            define "Specimen 258503004":
              (from [Specimen: Code '258503004' from snomed] S
                where ToDate(S.collection.collected as dateTime) in Interval[@0001-01-01T, @2026-02-12T] or
                  S.collection.collected overlaps Interval[@0001-01-01T, @2026-02-12T]) union
              (from [Specimen: Code '472862007' from snomed] S
                where ToDate(S.collection.collected as dateTime) in Interval[@0001-01-01T, @2026-02-12T] or
                  S.collection.collected overlaps Interval[@0001-01-01T, @2026-02-12T]) union
              (from [Specimen: Code '258505006' from snomed] S
                where ToDate(S.collection.collected as dateTime) in Interval[@0001-01-01T, @2026-02-12T] or
                  S.collection.collected overlaps Interval[@0001-01-01T, @2026-02-12T]) union
              (from [Specimen: Code '472885008' from snomed] S
                where ToDate(S.collection.collected as dateTime) in Interval[@0001-01-01T, @2026-02-12T] or
                  S.collection.collected overlaps Interval[@0001-01-01T, @2026-02-12T])
            
            define Criterion:
              exists (from [Observation: Code '18868-0' from loinc] O
                with "Specimen 258503004" S
                  such that O.specimen.reference contains 'Specimen/' + S.id
                where O.interpretation ~ Code 'R' from v3ObservationInterpretation and
                  ToDate(O.effective as dateTime) in Interval[@0001-01-01T, @2026-02-12T])
            
            define InInitialPopulation:
              Criterion
            """,
            id="Mikrobio_Empfindlichkeit_Patient1_Q1",
        ),
        pytest.param(
            "Mikrobio_Immunologie_Serologie_Patient1_Q1.json",
            """
            library Retrieve version '1.0.0'
            using FHIR version '4.0.0'
            include FHIRHelpers version '4.0.0'
            
            codesystem loinc: 'http://loinc.org'
            codesystem snomed: 'http://snomed.info/sct'
            
            context Patient
            
            define "Specimen 258503004":
              (from [Specimen: Code '258503004' from snomed] S
                where ToDate(S.collection.collected as dateTime) in Interval[@0001-01-01T, @2026-02-12T] or
                  S.collection.collected overlaps Interval[@0001-01-01T, @2026-02-12T]) union
              (from [Specimen: Code '472862007' from snomed] S
                where ToDate(S.collection.collected as dateTime) in Interval[@0001-01-01T, @2026-02-12T] or
                  S.collection.collected overlaps Interval[@0001-01-01T, @2026-02-12T]) union
              (from [Specimen: Code '258505006' from snomed] S
                where ToDate(S.collection.collected as dateTime) in Interval[@0001-01-01T, @2026-02-12T] or
                  S.collection.collected overlaps Interval[@0001-01-01T, @2026-02-12T]) union
              (from [Specimen: Code '472885008' from snomed] S
                where ToDate(S.collection.collected as dateTime) in Interval[@0001-01-01T, @2026-02-12T] or
                  S.collection.collected overlaps Interval[@0001-01-01T, @2026-02-12T])
            
            define Criterion:
              exists (from [Observation: Code '252318005' from snomed] O
                with "Specimen 258503004" S
                  such that O.specimen.reference contains 'Specimen/' + S.id
                where O.value.as(CodeableConcept) ~ Code '10828004' from snomed and
                  O.code ~ Code '50697-2' from loinc and
                  ToDate(O.effective as dateTime) in Interval[@0001-01-01T, @2026-02-12T])
            
            define InInitialPopulation:
              Criterion
            """,
            id="Mikrobio_Immunologie_Serologie_Patient1_Q1",
        ),
        pytest.param(
            "Mikrobio_Keimzahl_Patient1_Q1.json",
            """
            library Retrieve version '1.0.0'
            using FHIR version '4.0.0'
            include FHIRHelpers version '4.0.0'
            
            codesystem loinc: 'http://loinc.org'
            codesystem snomed: 'http://snomed.info/sct'
            
            context Patient
            
            define "Specimen 258503004":
              (from [Specimen: Code '258503004' from snomed] S
                where ToDate(S.collection.collected as dateTime) in Interval[@0001-01-01T, @2026-02-12T] or
                  S.collection.collected overlaps Interval[@0001-01-01T, @2026-02-12T]) union
              (from [Specimen: Code '472862007' from snomed] S
                where ToDate(S.collection.collected as dateTime) in Interval[@0001-01-01T, @2026-02-12T] or
                  S.collection.collected overlaps Interval[@0001-01-01T, @2026-02-12T]) union
              (from [Specimen: Code '258505006' from snomed] S
                where ToDate(S.collection.collected as dateTime) in Interval[@0001-01-01T, @2026-02-12T] or
                  S.collection.collected overlaps Interval[@0001-01-01T, @2026-02-12T]) union
              (from [Specimen: Code '472885008' from snomed] S
                where ToDate(S.collection.collected as dateTime) in Interval[@0001-01-01T, @2026-02-12T] or
                  S.collection.collected overlaps Interval[@0001-01-01T, @2026-02-12T])
            
            define Criterion:
              exists (from [Observation: Code '49223-1' from loinc] O
                with "Specimen 258503004" S
                  such that O.specimen.reference contains 'Specimen/' + S.id
                where ToDate(O.effective as dateTime) in Interval[@0001-01-01T, @2026-02-12T])
            
            define InInitialPopulation:
              Criterion
            """,
            id="Mikrobio_Keimzahl_Patient1_Q1",
        ),
        pytest.param(
            "Mikrobio_Molekulare_Diagnostik_Patient1_Q1.json",
            """
            library Retrieve version '1.0.0'
            using FHIR version '4.0.0'
            include FHIRHelpers version '4.0.0'
            
            codesystem loinc: 'http://loinc.org'
            codesystem snomed: 'http://snomed.info/sct'
            
            context Patient
            
            define "Specimen 258503004":
              (from [Specimen: Code '258503004' from snomed] S
                where ToDate(S.collection.collected as dateTime) in Interval[@0001-01-01T, @2026-02-12T] or
                  S.collection.collected overlaps Interval[@0001-01-01T, @2026-02-12T]) union
              (from [Specimen: Code '472862007' from snomed] S
                where ToDate(S.collection.collected as dateTime) in Interval[@0001-01-01T, @2026-02-12T] or
                  S.collection.collected overlaps Interval[@0001-01-01T, @2026-02-12T]) union
              (from [Specimen: Code '258505006' from snomed] S
                where ToDate(S.collection.collected as dateTime) in Interval[@0001-01-01T, @2026-02-12T] or
                  S.collection.collected overlaps Interval[@0001-01-01T, @2026-02-12T]) union
              (from [Specimen: Code '472885008' from snomed] S
                where ToDate(S.collection.collected as dateTime) in Interval[@0001-01-01T, @2026-02-12T] or
                  S.collection.collected overlaps Interval[@0001-01-01T, @2026-02-12T])
            
            define Criterion:
              exists (from [Observation: Code '92253-4' from loinc] O
                with "Specimen 258503004" S
                  such that O.specimen.reference contains 'Specimen/' + S.id
                where O.value.as(CodeableConcept) ~ Code '10828004' from snomed and
                  O.code ~ Code '94310-0' from loinc and
                  ToDate(O.effective as dateTime) in Interval[@0001-01-01T, @2026-02-12T])
            
            define InInitialPopulation:
              Criterion
            """,
            id="Mikrobio_Molekulare_Diagnostik_Patient1_Q1",
        ),
        pytest.param(
            "Mikrobio_MRE-Klasse_Patient1_Q1.json",
            """
            library Retrieve version '1.0.0'
            using FHIR version '4.0.0'
            include FHIRHelpers version '4.0.0'
            
            codesystem snomed: 'http://snomed.info/sct'
            
            context Patient
            
            define "Specimen 258503004":
              (from [Specimen: Code '258503004' from snomed] S
                where ToDate(S.collection.collected as dateTime) in Interval[@0001-01-01T, @2026-02-16T] or
                  S.collection.collected overlaps Interval[@0001-01-01T, @2026-02-16T]) union
              (from [Specimen: Code '472862007' from snomed] S
                where ToDate(S.collection.collected as dateTime) in Interval[@0001-01-01T, @2026-02-16T] or
                  S.collection.collected overlaps Interval[@0001-01-01T, @2026-02-16T]) union
              (from [Specimen: Code '258505006' from snomed] S
                where ToDate(S.collection.collected as dateTime) in Interval[@0001-01-01T, @2026-02-16T] or
                  S.collection.collected overlaps Interval[@0001-01-01T, @2026-02-16T]) union
              (from [Specimen: Code '472885008' from snomed] S
                where ToDate(S.collection.collected as dateTime) in Interval[@0001-01-01T, @2026-02-16T] or
                  S.collection.collected overlaps Interval[@0001-01-01T, @2026-02-16T])
            
            define Criterion:
              exists (from [Observation: Code '1285113001' from snomed] O
                with "Specimen 258503004" S
                  such that O.specimen.reference contains 'Specimen/' + S.id
                where O.value.as(CodeableConcept) ~ Code '710332005' from snomed and
                  ToDate(O.effective as dateTime) in Interval[@0001-01-01T, @2026-02-16T])
            
            define InInitialPopulation:
              Criterion
            """,
            id="Mikrobio_MRE-Klasse_Patient1_Q1",
        ),
        pytest.param(
            "Mikrobio_MRGN-Klasse_Patient1_Q1.json",
            """
            library Retrieve version '1.0.0'
            using FHIR version '4.0.0'
            include FHIRHelpers version '4.0.0'
            
            codesystem loinc: 'http://loinc.org'
            codesystem snomed: 'http://snomed.info/sct'
            
            context Patient
            
            define "Specimen 258503004":
              (from [Specimen: Code '258503004' from snomed] S
                where ToDate(S.collection.collected as dateTime) in Interval[@0001-01-01T, @2026-02-16T] or
                  S.collection.collected overlaps Interval[@0001-01-01T, @2026-02-16T]) union
              (from [Specimen: Code '472862007' from snomed] S
                where ToDate(S.collection.collected as dateTime) in Interval[@0001-01-01T, @2026-02-16T] or
                  S.collection.collected overlaps Interval[@0001-01-01T, @2026-02-16T]) union
              (from [Specimen: Code '258505006' from snomed] S
                where ToDate(S.collection.collected as dateTime) in Interval[@0001-01-01T, @2026-02-16T] or
                  S.collection.collected overlaps Interval[@0001-01-01T, @2026-02-16T]) union
              (from [Specimen: Code '472885008' from snomed] S
                where ToDate(S.collection.collected as dateTime) in Interval[@0001-01-01T, @2026-02-16T] or
                  S.collection.collected overlaps Interval[@0001-01-01T, @2026-02-16T])
            
            define Criterion:
              exists (from [Observation: Code '99780-9' from loinc] O
                with "Specimen 258503004" S
                  such that O.specimen.reference contains 'Specimen/' + S.id
                where O.value.as(CodeableConcept) ~ Code 'LA33215-7' from loinc and
                  ToDate(O.effective as dateTime) in Interval[@0001-01-01T, @2026-02-16T])
            
            define InInitialPopulation:
              Criterion            """,
            id="Mikrobio_MRGN-Klasse_Patient1_Q1",
        ),
        pytest.param(
            "Mikrobio_Resistenzgene_Patient1_Q1.json",
            """
            library Retrieve version '1.0.0'
            using FHIR version '4.0.0'
            include FHIRHelpers version '4.0.0'
            
            codesystem loinc: 'http://loinc.org'
            codesystem snomed: 'http://snomed.info/sct'
            
            context Patient
            
            define "Specimen 258503004":
              (from [Specimen: Code '258503004' from snomed] S
                where ToDate(S.collection.collected as dateTime) in Interval[@0001-01-01T, @2026-02-16T] or
                  S.collection.collected overlaps Interval[@0001-01-01T, @2026-02-16T]) union
              (from [Specimen: Code '472862007' from snomed] S
                where ToDate(S.collection.collected as dateTime) in Interval[@0001-01-01T, @2026-02-16T] or
                  S.collection.collected overlaps Interval[@0001-01-01T, @2026-02-16T]) union
              (from [Specimen: Code '258505006' from snomed] S
                where ToDate(S.collection.collected as dateTime) in Interval[@0001-01-01T, @2026-02-16T] or
                  S.collection.collected overlaps Interval[@0001-01-01T, @2026-02-16T]) union
              (from [Specimen: Code '472885008' from snomed] S
                where ToDate(S.collection.collected as dateTime) in Interval[@0001-01-01T, @2026-02-16T] or
                  S.collection.collected overlaps Interval[@0001-01-01T, @2026-02-16T])
            
            define Criterion:
              exists (from [Observation: Code '48813-0' from loinc] O
                with "Specimen 258503004" S
                  such that O.specimen.reference contains 'Specimen/' + S.id
                where O.value.as(CodeableConcept) ~ Code '260373001' from snomed and
                  ToDate(O.effective as dateTime) in Interval[@0001-01-01T, @2026-02-16T])
            
            define InInitialPopulation:
              Criterion
            """,
            id="Mikrobio_Resistenzgene_Patient1_Q1",
        ),
        pytest.param(
            "Mikrobio_Resistenzmutation_Patient1_Q1.json",
            """
            library Retrieve version '1.0.0'
            using FHIR version '4.0.0'
            include FHIRHelpers version '4.0.0'
            
            codesystem loinc: 'http://loinc.org'
            codesystem snomed: 'http://snomed.info/sct'
            
            context Patient
            
            define "Specimen 258503004":
              (from [Specimen: Code '258503004' from snomed] S
                where ToDate(S.collection.collected as dateTime) in Interval[@0001-01-01T, @2026-02-16T] or
                  S.collection.collected overlaps Interval[@0001-01-01T, @2026-02-16T]) union
              (from [Specimen: Code '472862007' from snomed] S
                where ToDate(S.collection.collected as dateTime) in Interval[@0001-01-01T, @2026-02-16T] or
                  S.collection.collected overlaps Interval[@0001-01-01T, @2026-02-16T]) union
              (from [Specimen: Code '258505006' from snomed] S
                where ToDate(S.collection.collected as dateTime) in Interval[@0001-01-01T, @2026-02-16T] or
                  S.collection.collected overlaps Interval[@0001-01-01T, @2026-02-16T]) union
              (from [Specimen: Code '472885008' from snomed] S
                where ToDate(S.collection.collected as dateTime) in Interval[@0001-01-01T, @2026-02-16T] or
                  S.collection.collected overlaps Interval[@0001-01-01T, @2026-02-16T])
            
            define Criterion:
              exists (from [Observation: Code '94054-4' from loinc] O
                with "Specimen 258503004" S
                  such that O.specimen.reference contains 'Specimen/' + S.id
                where O.value.as(CodeableConcept) ~ Code '260373001' from snomed and
                  ToDate(O.effective as dateTime) in Interval[@0001-01-01T, @2026-02-16T])
            
            define InInitialPopulation:
              Criterion
            """,
            id="Mikrobio_Resistenzmutation_Patient1_Q1",
        ),
        pytest.param(
            "Mikrobio_Virulenzfaktor_Patient1_Q1.json",
            """
            library Retrieve version '1.0.0'
            using FHIR version '4.0.0'
            include FHIRHelpers version '4.0.0'
            
            codesystem loinc: 'http://loinc.org'
            codesystem snomed: 'http://snomed.info/sct'
            
            context Patient
            
            define "Specimen 258503004":
              (from [Specimen: Code '258503004' from snomed] S
                where ToDate(S.collection.collected as dateTime) in Interval[@0001-01-01T, @2026-02-16T] or
                  S.collection.collected overlaps Interval[@0001-01-01T, @2026-02-16T]) union
              (from [Specimen: Code '472862007' from snomed] S
                where ToDate(S.collection.collected as dateTime) in Interval[@0001-01-01T, @2026-02-16T] or
                  S.collection.collected overlaps Interval[@0001-01-01T, @2026-02-16T]) union
              (from [Specimen: Code '258505006' from snomed] S
                where ToDate(S.collection.collected as dateTime) in Interval[@0001-01-01T, @2026-02-16T] or
                  S.collection.collected overlaps Interval[@0001-01-01T, @2026-02-16T]) union
              (from [Specimen: Code '472885008' from snomed] S
                where ToDate(S.collection.collected as dateTime) in Interval[@0001-01-01T, @2026-02-16T] or
                  S.collection.collected overlaps Interval[@0001-01-01T, @2026-02-16T])
            
            define Criterion:
              exists (from [Observation: Code '87380-2' from loinc] O
                with "Specimen 258503004" S
                  such that O.specimen.reference contains 'Specimen/' + S.id
                where O.value.as(CodeableConcept) ~ Code '260373001' from snomed and
                  ToDate(O.effective as dateTime) in Interval[@0001-01-01T, @2026-02-16T])
            
            define InInitialPopulation:
              Criterion
            """,
            id="Mikrobio_Virulenzfaktor_Patient1_Q1",
        ),
        pytest.param(
            "Mikrobio_Vorraussichtliche_Empfindlichkeit_Patient1_Q1.json",
            """
            library Retrieve version '1.0.0'
            using FHIR version '4.0.0'
            include FHIRHelpers version '4.0.0'
            
            codesystem loinc: 'http://loinc.org'
            codesystem snomed: 'http://snomed.info/sct'
            
            context Patient
            
            define "Specimen 258503004":
              (from [Specimen: Code '258503004' from snomed] S
                where ToDate(S.collection.collected as dateTime) in Interval[@0001-01-01T, @2026-02-16T] or
                  S.collection.collected overlaps Interval[@0001-01-01T, @2026-02-16T]) union
              (from [Specimen: Code '472862007' from snomed] S
                where ToDate(S.collection.collected as dateTime) in Interval[@0001-01-01T, @2026-02-16T] or
                  S.collection.collected overlaps Interval[@0001-01-01T, @2026-02-16T]) union
              (from [Specimen: Code '258505006' from snomed] S
                where ToDate(S.collection.collected as dateTime) in Interval[@0001-01-01T, @2026-02-16T] or
                  S.collection.collected overlaps Interval[@0001-01-01T, @2026-02-16T]) union
              (from [Specimen: Code '472885008' from snomed] S
                where ToDate(S.collection.collected as dateTime) in Interval[@0001-01-01T, @2026-02-16T] or
                  S.collection.collected overlaps Interval[@0001-01-01T, @2026-02-16T])
            
            define Criterion:
              exists (from [Observation: Code '73574-6' from loinc] O
                with "Specimen 258503004" S
                  such that O.specimen.reference contains 'Specimen/' + S.id
                where O.value.as(CodeableConcept) ~ Code '131196009' from snomed and
                  ToDate(O.effective as dateTime) in Interval[@0001-01-01T, @2026-02-16T])
            
            define InInitialPopulation:
              Criterion
            """,
            id="Mikrobio_Vorraussichtliche_Empfindlichkeit_Patient1_Q1",
        ),
        pytest.param(
            "Observation_Patient1_Q1.json",
            """
            library Retrieve version '1.0.0'
            using FHIR version '4.0.0'
            include FHIRHelpers version '4.0.0'
            
            codesystem loinc: 'http://loinc.org'
            
            context Patient
            
            define Criterion:
              exists (from [Observation: Code '26464-8' from loinc] O
                where ToDate(O.effective as dateTime) in Interval[@2024-02-13T, @2024-02-17T])
            
            define InInitialPopulation:
              Criterion
            """,
            id="Observation_Patient1_Q1",
        ),
        pytest.param(
            "Person_Condition_Todesursache_LOINC_Patient1_Q1.json",
            """
            library Retrieve version '1.0.0'
            using FHIR version '4.0.0'
            include FHIRHelpers version '4.0.0'
            
            codesystem loinc: 'http://loinc.org'
            codesystem sidicd10: 'http://hl7.org/fhir/sid/icd-10'
            
            context Patient
            
            define Criterion:
              exists (from [Condition: category ~ Code '79378-6' from loinc] C
                where C.code ~ Code 'A15.0' from sidicd10)
            
            define InInitialPopulation:
              Criterion
            """,
            id="Person_Condition_Todesursache_LOINC_Patient1_Q1",
        ),
        pytest.param(
            "Person_Condition_Todesursache_SNOMED_Patient1_Q1.json",
            """
            library Retrieve version '1.0.0'
            using FHIR version '4.0.0'
            include FHIRHelpers version '4.0.0'
            
            codesystem sidicd10: 'http://hl7.org/fhir/sid/icd-10'
            codesystem snomed: 'http://snomed.info/sct'
            
            context Patient
            
            define Criterion:
              exists (from [Condition: category ~ Code '16100001' from snomed] C
                where C.code ~ Code 'A15.0' from sidicd10)
            
            define InInitialPopulation:
              Criterion
            """,
            id="Person_Condition_Todesursache_SNOMED_Patient1_Q1",
        ),
        pytest.param(
            "Person_Gender_Patient1_Q1.json",
            """
            library Retrieve version '1.0.0'
            using FHIR version '4.0.0'
            include FHIRHelpers version '4.0.0'
            
            context Patient
            
            define Criterion:
              Patient.gender = 'male'
            
            define InInitialPopulation:
              Criterion
            """,
            id="Person_Gender_Patient1_Q1",
        ),
        pytest.param(
            "Person_Vitalstatus_Patient1_Q1.json",
            """
            library Retrieve version '1.0.0'
            using FHIR version '4.0.0'
            include FHIRHelpers version '4.0.0'
            
            codesystem loinc: 'http://loinc.org'
            codesystem vitalstatus: 'https://www.medizininformatik-initiative.de/fhir/core/modul-person/CodeSystem/Vitalstatus'
            
            context Patient
            
            define Criterion:
              exists (from [Observation: Code '67162-8' from loinc] O
                where O.value.as(CodeableConcept) ~ Code 'T' from vitalstatus and
                  ToDate(O.effective as dateTime) in Interval[@2024-02-21T, @2024-02-21T])
            
            define InInitialPopulation:
              Criterion
            """,
            id="Person_Vitalstatus_Patient1_Q1",
        ),
        pytest.param(
            "Person_CategorySCT_Patient1_Q1.json",
            """
            library Retrieve version '1.0.0'
            using FHIR version '4.0.0'
            include FHIRHelpers version '4.0.0'
            
            codesystem snomed: 'http://snomed.info/sct'
            
            context Patient
            
            define Criterion:
              exists (from [Procedure: category ~ Code '387713003' from snomed] P
                where ToDate(P.performed as dateTime) in Interval[@2024-02-19T, @2024-02-21T] or
                  P.performed overlaps Interval[@2024-02-19T, @2024-02-21T])
            
            define InInitialPopulation:
              Criterion
            """,
            id="Prozedur_CategorySCT_SNOMED_Patient1_Q1",
        ),
        pytest.param(
            "Prozedur_OPS_Patient1_Q1.json",
            """
            library Retrieve version '1.0.0'
            using FHIR version '4.0.0'
            include FHIRHelpers version '4.0.0'
            
            codesystem ops: 'http://fhir.de/CodeSystem/bfarm/ops'
            
            context Patient
            
            define Criterion:
              exists (from [Procedure: Code '5-323.51' from ops] P
                where ToDate(P.performed as dateTime) in Interval[@2024-02-19T, @2024-02-21T] or
                  P.performed overlaps Interval[@2024-02-19T, @2024-02-21T])
            
            define InInitialPopulation:
              Criterion
            """,
            id="Prozedur_OPS_Patient1_Q1",
        ),
        pytest.param(
            "Prozedur_SCT_Patient1_Q1.json",
            """
            library Retrieve version '1.0.0'
            using FHIR version '4.0.0'
            include FHIRHelpers version '4.0.0'
            
            codesystem snomed: 'http://snomed.info/sct'
            
            context Patient
            
            define Criterion:
              exists (from [Procedure: Code '726427004' from snomed] P
                where ToDate(P.performed as dateTime) in Interval[@2024-02-19T, @2024-02-21T] or
                  P.performed overlaps Interval[@2024-02-19T, @2024-02-21T]) or
              exists (from [Procedure: Code '232638008' from snomed] P
                where ToDate(P.performed as dateTime) in Interval[@2024-02-19T, @2024-02-21T] or
                  P.performed overlaps Interval[@2024-02-19T, @2024-02-21T]) or
              exists (from [Procedure: Code '3654008' from snomed] P
                where ToDate(P.performed as dateTime) in Interval[@2024-02-19T, @2024-02-21T] or
                  P.performed overlaps Interval[@2024-02-19T, @2024-02-21T])
            
            define InInitialPopulation:
              Criterion
            """,
            id="Prozedur_SCT_Patient1_Q1",
        ),
    ],
)
def test_sq_to_cql_translation(
    sq_file,
    expected,
):
    assert (
        _translate(Path(__file__).parent / "test-queries" / sq_file)
        == dedent(expected).strip()
    )
