Instance: CdsAvailabilityMeasure
InstanceOf: http://hl7.org/fhir/us/cqfmeasures/StructureDefinition/cv-measure-cqfm
Description: "Example Measure to count all ICD-10 codes and the patient count."
* status = #active
* url = "https://medizininformatik-initiative.de/fhir/fdpg/Measure/CdsAvailabilityMeasure"
* version = "1.0"
* name = "CDSAvailabilityMeasure"
* experimental = false
* publisher = "FDPG-Plus-Availability"
* description = "Measure to count the availabilities of different crtieria based on terminology system code counts"


// Profil Diagnose
* insert AddStratifierGroup(0, "Condition?_profile=https://www.medizininformatik-initiative.de/fhir/core/modul-diagnose/StructureDefinition/Diagnose", Condition, Condition.subject.reference)
* insert AddStratifierToGroupWhere(0, 0, Condition.code.coding.where, system='http://fhir.de/CodeSystem/bfarm/icd-10-gm', "condition-icd10-code" , "diag-icd10")
* insert AddStratifierToGroupWhere(0, 1, Condition.code.coding.where, system='http://snomed.info/sct', "condition-sct-code" , "diag-sct")
* insert AddStratifierToGroupWhere(0, 2, Condition.code.coding.where, system='http://fhir.de/CodeSystem/bfarm/alpha-id', "condition-alhpaid-code" , "diag-alphaid")
* insert AddStratifierToGroupWhere(0, 3, Condition.code.coding.where, system='http://www.orpha.net', "condition-orphanet-code" , "diag-orphanet")
* insert AddStratifierToGroupWhere(0, 4, Condition.code.coding.where, system='http://terminology.hl7.org/CodeSystem/icd-o-3', "condition-icdo3-code" , "diag-icd-o-3")


// Profil Laboratory
* insert AddStratifierGroup(1, "Observation?_profile:below=https://www.medizininformatik-initiative.de/fhir/core/modul-labor/StructureDefinition/ObservationLab", Observation, Observation.subject.reference)
//* insert AddStratifierToGroupWhere(1, 0, Observation.code.coding.where, system='http://loinc.org', "observation-lab-loinc-code" , "lab-loinc")
* insert AddStratifierToGroup(1, 0, Observation.code.coding.where(system='http://loinc.org'\), "observation-lab-loinc-code" , "lab-loinc")

// Profil Patient
* insert AddStratifierGroup(2, "Patient?_profile:below=https://www.medizininformatik-initiative.de/fhir/core/modul-person/StructureDefinition/Patient", Patient, Patient.id.value)
* insert AddStratifierToGroup(2, 0, Patient.gender, "patient-gender" , "patient-gender")
* insert AddStratifierToGroupWhere(2, 1, Patient.birthDate.exists, , "patient-birthdate-exists" , "patient-birthdate-exists")


// Profil MedicationAdministration
* insert AddStratifierGroup(3, "MedicationAdministration?_profile:below=https://www.medizininformatik-initiative.de/fhir/core/modul-medikation/StructureDefinition/MedicationAdministration&_include=MedicationAdministration:medication", MedicationAdministration, MedicationAdministration.subject.reference)
* insert AddStratifierToGroup(3, 0, MedicationAdministration.medication.resolve(\).ofType(Medication\).code.coding.where(system='http://fhir.de/CodeSystem/ifa/pzn'\), "medicationadministration-medication-code-pzn" , "medicationadministration-medication-code-pzn")
* insert AddStratifierToGroup(3, 1, MedicationAdministration.medication.resolve(\).ofType(Medication\).code.coding.where(system='http://fhir.de/CodeSystem/bfarm/atc'\), "medicationadministration-medication-code-atc" , "medicationadministration-medication-code-atc")

// Profil MedicationStatement
* insert AddStratifierGroup(4, "MedicationStatement?_profile:below=https://www.medizininformatik-initiative.de/fhir/core/modul-medikation/StructureDefinition/MedicationStatement&_include=MedicationStatement:medication", MedicationStatement, MedicationStatement.subject.reference)
* insert AddStratifierToGroup(4, 0, MedicationStatement.medication.resolve(\).ofType(Medication\).code.coding.where(system='http://fhir.de/CodeSystem/ifa/pzn'\), "medicationstatement-medication-code-pzn" , "medicationstatement-medication-code-pzn")
* insert AddStratifierToGroup(4, 1, MedicationStatement.medication.resolve(\).ofType(Medication\).code.coding.where(system='http://fhir.de/CodeSystem/bfarm/atc'\), "medicationstatement-medication-code-atc" , "medicationstatement-medication-code-atc")

// Profil MedicationRequest
* insert AddStratifierGroup(5, "MedicationRequest?_profile:below=https://www.medizininformatik-initiative.de/fhir/core/modul-medikation/StructureDefinition/MedicationRequest&_include=MedicationRequest:medication", MedicationRequest, MedicationRequest.subject.reference)
* insert AddStratifierToGroup(5, 0, MedicationRequest.medication.resolve(\).ofType(Medication\).code.coding.where(system='http://fhir.de/CodeSystem/ifa/pzn'\), "medicationrequest-medication-code-pzn" , "medicationrequest-medication-code-pzn")
* insert AddStratifierToGroup(5, 1, MedicationRequest.medication.resolve(\).ofType(Medication\).code.coding.where(system='http://fhir.de/CodeSystem/bfarm/atc'\), "medicationrequest-medication-code-atc" , "medicationrequest-medication-code-atc")


// Profil Procedure
* insert AddStratifierGroup(6, "Procedure?_profile:below=https://www.medizininformatik-initiative.de/fhir/core/modul-prozedur/StructureDefinition/Procedure", Procedure, Procedure.subject.reference)
* insert AddStratifierToGroup(6, 0, Procedure.code.coding.where(system='http://fhir.de/CodeSystem/bfarm/ops'\), "procedure-ops-code" , "procedure-ops-code")
* insert AddStratifierToGroup(6, 1, Procedure.code.coding.where(system='http://snomed.info/sct'\), "procedure-sct-code" , "procedure-sct-code")


// Specimen
* insert AddStratifierGroup(7, "Specimen?_profile:below=https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Specimen", Specimen, Specimen.subject.reference)
* insert AddStratifierToGroup(7, 0, Specimen.type.coding.where(system='http://snomed.info/sct'\), "specimen-type-sct-code" , "specimen-type-sct-code")


// Encounter
* insert AddStratifierGroup(8, "Encounter?_profile:below=https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung", Encounter, Encounter.subject.reference)
* insert AddStratifierToGroup(8, 0, Encounter.class.coding, "encounter-class-coding" , "encounter-class-coding")


// Consent
* insert AddStratifierGroup(9, "Consent?_profile:below=http://fhir.de/ConsentManagement/StructureDefinition/Consent", Consent, Consent.patient.reference)
* insert AddStratifierToGroup(9, 0, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.1'\), "consent-patientendaten-erheben-speichern-nutzen" , "consent-patientendaten-erheben-speichern-nutzen")
* insert AddStratifierToGroup(9, 1, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.2'\), "consent-idat-erheben" , "consent-idat-erheben")
* insert AddStratifierToGroup(9, 2, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.3'\), "consent-idat-speichern-verarbeiten" , "consent-idat-speichern-verarbeiten")
* insert AddStratifierToGroup(9, 3, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.4'\), "consent-idat-zusammenfuehren-dritte" , "consent-idat-zusammenfuehren-dritte")
* insert AddStratifierToGroup(9, 4, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.5'\), "consent-idat-bereitstellen-eu-dsgvo-niveau" , "consent-idat-bereitstellen-eu-dsgvo-niveau")
* insert AddStratifierToGroup(9, 5, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.6'\), "consent-mdat-erheben" , "consent-mdat-erheben")
* insert AddStratifierToGroup(9, 6, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.7'\), "consent-mdat-speichern-verarbeiten" , "consent-mdat-speichern-verarbeiten")
* insert AddStratifierToGroup(9, 7, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.8'\), "consent-mdat-wissenschaftlich-nutzen-eu-dsgvo-niveau" , "consent-mdat-wissenschaftlich-nutzen-eu-dsgvo-niveau")
* insert AddStratifierToGroup(9, 8, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.9'\), "consent-mdat-zusammenfuehren-dritte" , "consent-mdat-zusammenfuehren-dritte")
* insert AddStratifierToGroup(9, 9, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.37'\), "consent-rekontaktierung-ergebnisse-erheblicher-bedeutung" , "consent-rekontaktierung-ergebnisse-erheblicher-bedeutung")
* insert AddStratifierToGroup(9, 10, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.44'\), "consent-patientendaten-retrospektiv-verarbeiten-nutzen" , "consent-patientendaten-retrospektiv-verarbeiten-nutzen")
* insert AddStratifierToGroup(9, 11, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.45'\), "consent-mdat-retrospektiv-speichern-verarbeiten" , "consent-mdat-retrospektiv-speichern-verarbeiten")
* insert AddStratifierToGroup(9, 12, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.46'\), "consent-mdat-retrospektiv-wissenschaftlich-nutzen-eu-dsgvo-niveau" , "consent-mdat-retrospektiv-wissenschaftlich-nutzen-eu-dsgvo-niveau")
* insert AddStratifierToGroup(9, 13, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.47'\), "consent-mdat-retrospektiv-zusammenfuehren-dritte" , "consent-mdat-retrospektiv-zusammenfuehren-dritte")
* insert AddStratifierToGroup(9, 14, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.48'\), "consent-patientendaten-weitergabe-non-dsgvo-niveau" , "consent-patientendaten-weitergabe-non-dsgvo-niveau")
* insert AddStratifierToGroup(9, 15, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.49'\), "consent-mdat-bereitstellen-non-eu-dsgvo-niveau" , "consent-mdat-bereitstellen-non-eu-dsgvo-niveau")
* insert AddStratifierToGroup(9, 16, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.10'\), "consent-krankenkassendaten-retrospektiv-uebertragen-speichern-nutzen" , "consent-krankenkassendaten-retrospektiv-uebertragen-speichern-nutzen")
* insert AddStratifierToGroup(9, 17, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.11'\), "consent-kkdat-5j-retrospektiv-uebertragen" , "consent-kkdat-5j-retrospektiv-uebertragen")
* insert AddStratifierToGroup(9, 18, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.12'\), "consent-kkdat-5j-retrospektiv-speichern-verarbeiten" , "consent-kkdat-5j-retrospektiv-speichern-verarbeiten")
* insert AddStratifierToGroup(9, 19, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.13'\), "consent-kkdat-5j-retrospektiv-wissenschaftlich-nutzen" , "consent-kkdat-5j-retrospektiv-wissenschaftlich-nutzen")
* insert AddStratifierToGroup(9, 20, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.38'\), "consent-kkdat-5j-retrospektiv-uebertragen-kvnr" , "consent-kkdat-5j-retrospektiv-uebertragen-kvnr")
* insert AddStratifierToGroup(9, 21, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.14'\), "consent-kkdat-prospektiv-uebertragen-speichern-nutzen" , "consent-kkdat-prospektiv-uebertragen-speichern-nutzen")
* insert AddStratifierToGroup(9, 22, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.15'\), "consent-kkdat-5j-prospektiv-uebertragen" , "consent-kkdat-5j-prospektiv-uebertragen")
* insert AddStratifierToGroup(9, 23, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.16'\), "consent-kkdat-5j-prospektiv-speichern-verarbeiten" , "consent-kkdat-5j-prospektiv-speichern-verarbeiten")
* insert AddStratifierToGroup(9, 24, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.17'\), "consent-kkdat-5j-prospektiv-wissenschaftlich-nutzen" , "consent-kkdat-5j-prospektiv-wissenschaftlich-nutzen")
* insert AddStratifierToGroup(9, 25, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.39'\), "consent-kkdat-5j-prospektiv-uebertragen-kvnr" , "consent-kkdat-5j-prospektiv-uebertragen-kvnr")
* insert AddStratifierToGroup(9, 26, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.18'\), "consent-biomaterial-erheben-lagern-nutzen" , "consent-biomaterial-erheben-lagern-nutzen")
* insert AddStratifierToGroup(9, 27, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.19'\), "consent-biomat-erheben" , "consent-biomat-erheben")
* insert AddStratifierToGroup(9, 28, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.20'\), "consent-biomat-lagern-verarbeiten" , "consent-biomat-lagern-verarbeiten")
* insert AddStratifierToGroup(9, 29, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.21'\), "consent-biomat-eigentum-uebertragen" , "consent-biomat-eigentum-uebertragen")
* insert AddStratifierToGroup(9, 30, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.22'\), "consent-biomat-wissenschaftlich-nutzen-eu-dsgvo-niveau" , "consent-biomat-wissenschaftlich-nutzen-eu-dsgvo-niveau")
* insert AddStratifierToGroup(9, 31, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.23'\), "consent-biomat-analysedaten-zusammenfuehren-dritte" , "consent-biomat-analysedaten-zusammenfuehren-dritte")
* insert AddStratifierToGroup(9, 32, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.24'\), "consent-biomaterial-zusatzentnahme" , "consent-biomaterial-zusatzentnahme")
* insert AddStratifierToGroup(9, 33, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.25'\), "consent-biomat-zusatzmengen-entnehmen" , "consent-biomat-zusatzmengen-entnehmen")
* insert AddStratifierToGroup(9, 34, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.50'\), "consent-biomaterial-retrospektiv-speichern-nutzen" , "consent-biomaterial-retrospektiv-speichern-nutzen")
* insert AddStratifierToGroup(9, 35, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.51'\), "consent-biomat-retrospektiv-lagern-verarbeiten" , "consent-biomat-retrospektiv-lagern-verarbeiten")
* insert AddStratifierToGroup(9, 36, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.52'\), "consent-biomat-retrospektiv-wissenschaftlich-nutzen-eu-dsgvo-niveau" , "consent-biomat-retrospektiv-wissenschaftlich-nutzen-eu-dsgvo-niveau")
* insert AddStratifierToGroup(9, 37, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.53'\), "consent-biomat-retrospektiv-analysedaten-zusammenfuehren-dritte" , "consent-biomat-retrospektiv-analysedaten-zusammenfuehren-dritte")
* insert AddStratifierToGroup(9, 38, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.54'\), "consent-biomaterial-weitergabe-non-eu-dsgvo-niveau" , "consent-biomaterial-weitergabe-non-eu-dsgvo-niveau")
* insert AddStratifierToGroup(9, 39, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.55'\), "consent-biomat-bereitstellen-ohne-eu-dsgvo-niveau" , "consent-biomat-bereitstellen-ohne-eu-dsgvo-niveau")
* insert AddStratifierToGroup(9, 40, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.26'\), "consent-rekontaktierung-ergaenzungen" , "consent-rekontaktierung-ergaenzungen")
* insert AddStratifierToGroup(9, 41, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.27'\), "consent-rekontaktierung-verknuepfung-datenbanken" , "consent-rekontaktierung-verknuepfung-datenbanken")
* insert AddStratifierToGroup(9, 42, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.28'\), "consent-rekontaktierung-weitere-erhebung" , "consent-rekontaktierung-weitere-erhebung")
* insert AddStratifierToGroup(9, 43, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.29'\), "consent-rekontaktierung-weitere-studien" , "consent-rekontaktierung-weitere-studien")
* insert AddStratifierToGroup(9, 44, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.30'\), "consent-rekontaktierung-zusatzbefund" , "consent-rekontaktierung-zusatzbefund")
* insert AddStratifierToGroup(9, 45, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.31'\), "consent-rekontaktierung-zusatzbefund" , "consent-rekontaktierung-zusatzbefund")
* insert AddStratifierToGroup(9, 46, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.32'\), "consent-z1-gecco83-nutzung-num/codex" , "consent-z1-gecco83-nutzung-num/codex")
* insert AddStratifierToGroup(9, 47, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.40'\), "consent-mdat-gecco83-komplettieren-einmalig" , "consent-mdat-gecco83-komplettieren-einmalig")
* insert AddStratifierToGroup(9, 48, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.43'\), "consent-mdat-gecco83-erheben" , "consent-mdat-gecco83-erheben")
* insert AddStratifierToGroup(9, 49, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.33'\), "consent-mdat-gecco83-bereitstellen-num/codex" , "consent-mdat-gecco83-bereitstellen-num/codex")
* insert AddStratifierToGroup(9, 50, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.34'\), "consent-mdat-gecco83-speichern-verarbeiten-num/codex" , "consent-mdat-gecco83-speichern-verarbeiten-num/codex")
* insert AddStratifierToGroup(9, 51, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.41'\), "consent-mdat-gecco83-wissenschaftlich-nutzen-covid-19-forschung-eu-dsgvo-konform-deprecated" , "consent-mdat-gecco83-wissenschaftlich-nutzen-covid-19-forschung-eu-dsgvo-konform-deprecated")
* insert AddStratifierToGroup(9, 52, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.42'\), "consent-mdat-gecco83-wissenschaftlich-nutzen-pandemie-forschung-eu-dsgvo-konform-deprecated" , "consent-mdat-gecco83-wissenschaftlich-nutzen-pandemie-forschung-eu-dsgvo-konform-deprecated")
* insert AddStratifierToGroup(9, 53, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.56'\), "consent-mdat-gecco83-wissenschaftlich-nutzen-num/codex-eu-dsgvo-niveau" , "consent-mdat-gecco83-wissenschaftlich-nutzen-num/codex-eu-dsgvo-niveau")
* insert AddStratifierToGroup(9, 54, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.35'\), "consent-z1-gecco83-weitergabe-num/codex-non-eu-dsgvo-niveau" , "consent-z1-gecco83-weitergabe-num/codex-non-eu-dsgvo-niveau")
* insert AddStratifierToGroup(9, 55, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.36'\), "consent-mdat-gecco83-bereitstellen-num/codex-ohne-eu-dsgvo-niveau" , "consent-mdat-gecco83-bereitstellen-num/codex-ohne-eu-dsgvo-niveau")
* insert AddStratifierToGroup(9, 56, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.57'\), "consent-z2-patientendaten-erheben-nutzen-kontaktierung-im-acribis-projekt" , "consent-z2-patientendaten-erheben-nutzen-kontaktierung-im-acribis-projekt")
* insert AddStratifierToGroup(9, 57, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.58'\), "consent-patdat-erheben-nutzen-kontaktierung-im-acribis-projekt" , "consent-patdat-erheben-nutzen-kontaktierung-im-acribis-projekt")
* insert AddStratifierToGroup(9, 58, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.59'\), "consent-z2-idat-melderegister-abfragen-speichern-verarbeiten-im-acribis-projekt" , "consent-z2-idat-melderegister-abfragen-speichern-verarbeiten-im-acribis-projekt")
* insert AddStratifierToGroup(9, 59, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.60'\), "consent-anschrift-und-vitalstatus-melderegister-abfragen-speichern-verarbeiten-im-acribis-projekt" , "consent-anschrift-und-vitalstatus-melderegister-abfragen-speichern-verarbeiten-im-acribis-projekt")
* insert AddStratifierToGroup(9, 60, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.61'\), "consent-z2-mdat-hausarzt-erheben-speichern-verarbeiten-nutzen-im-acribis-projekt" , "consent-z2-mdat-hausarzt-erheben-speichern-verarbeiten-nutzen-im-acribis-projekt")
* insert AddStratifierToGroup(9, 61, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.62'\), "consent-mdat-hausarzt-erheben-speichern-verarbeiten-nutzen-im-acribis-projekt" , "consent-mdat-hausarzt-erheben-speichern-verarbeiten-nutzen-im-acribis-projekt")
* insert AddStratifierToGroup(9, 62, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.63'\), "consent-z3-promdat-patientenbefragung" , "consent-z3-promdat-patientenbefragung")
* insert AddStratifierToGroup(9, 63, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.64'\), "consent-promdat-patientenbefragung-erheben" , "consent-promdat-patientenbefragung-erheben")
* insert AddStratifierToGroup(9, 64, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.65'\), "consent-promdat-wissenschaftlich-nutzen-auf-eu-dsgvo-niveau" , "consent-promdat-wissenschaftlich-nutzen-auf-eu-dsgvo-niveau")
* insert AddStratifierToGroup(9, 65, Consent.provision.provision.code.coding.where(code='2.16.840.1.113883.3.1937.777.24.5.3.66'\), "consent-rekontaktierung-prom-studien" , "consent-rekontaktierung-prom-studien")



// ICU - Arterieller Blutdruck
* insert AddStratifierGroup(10, "Observation?_profile:below=https://simplifier.net/medizininformatikinitiative-modul-intensivmedizin/sd_mii_icu_arterieller_blutdruck", Observation, Observation.subject.reference)
* insert AddStratifierToGroup(10, 0, Observation.code.coding.where(system='http://loinc.org'\), "icu-arterieller-blutdruck" , "icu-arterieller-blutdruck")

// ICU - Atemfrequenz
* insert AddStratifierGroup(11, "Observation?_profile:below=https://simplifier.net/medizininformatikinitiative-modul-intensivmedizin/sd_mii_icu_atemfrequenz", Observation, Observation.subject.reference)
* insert AddStratifierToGroup(11, 0, Observation.code.coding.where(system='http://loinc.org'\), "icu-atemfrequenz" , "icu-atemfrequenz")

// ICU - Herzfrequenz
* insert AddStratifierGroup(12, "Observation?_profile:below=https://simplifier.net/medizininformatikinitiative-modul-intensivmedizin/sd_mii_icu_herzfrequenz", Observation, Observation.subject.reference)
* insert AddStratifierToGroup(12, 0, Observation.code.coding.where(system='http://loinc.org'\), "icu-herzfrequenz" , "icu-herzfrequenz")

// ICU - Koepergewicht
* insert AddStratifierGroup(13, "Observation?_profile:below=https://simplifier.net/medizininformatikinitiative-modul-intensivmedizin/sd_mii_icu_koerpergewicht", Observation, Observation.subject.reference)
* insert AddStratifierToGroup(13, 0, Observation.code.coding.where(system='http://loinc.org'\), "icu-koerpergewicht" , "icu-koerpergewicht")

// ICU - Koerpergroesse
* insert AddStratifierGroup(14, "Observation?_profile:below=https://simplifier.net/medizininformatikinitiative-modul-intensivmedizin/sd_mii_icu_koerpergroesse", Observation, Observation.subject.reference)
* insert AddStratifierToGroup(14, 0, Observation.code.coding.where(system='http://loinc.org'\), "icu-koerpergroesse" , "icu-koerpergroesse")

// ICU - o2saettigung
* insert AddStratifierGroup(15, "Observation?_profile:below=https://gematik.de/fhir/isik/StructureDefinition/sd-mii-icu-o2saettigung-im-arteriellen-blut-durch-pulsoxymetrie", Observation, Observation.subject.reference)
* insert AddStratifierToGroup(15, 0, Observation.code.coding.where(system='http://loinc.org'\), "icu-o2saettigung" , "icu-o2saettigung")



