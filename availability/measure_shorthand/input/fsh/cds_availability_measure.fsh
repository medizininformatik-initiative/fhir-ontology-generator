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
* insert AddStratifierToGroup(1, 0, Observation.code.coding.where(system='http://loinc.org'\), "observation-lab-loinc-code" , "lab-loincr")

// Profil Patient
* insert AddStratifierGroup(2, "Patient?_profile:below=https://www.medizininformatik-initiative.de/fhir/core/modul-person/StructureDefinition/Patient", Patient, id)
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
//TODO