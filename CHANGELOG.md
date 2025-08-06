# Changelog

All notable changes to this project will be documented in this file.

<!-- CHANGELOG Editing Guidelines
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [UNRELEASED] - yyyy-mm-dd

### Added
### Changed
### Deprecated
### Removed
### Fixed
### Security
-->


## [3.8.3] - 2025-06-08

## Fixed

- Fix concepts with fewer descendants than the configured limit not being selectable in the cohort selection ([#317](https://github.com/medizininformatik-initiative/fhir-ontology-generator/issues/317) @paulolaup)

## [3.8.2] - 2025-07-14

## Added

- Add result code filter for DiagnosticReport resource profiles in DSE ([#310](https://github.com/medizininformatik-initiative/fhir-ontology-generator/issues/310) @Frontman50)

## [3.8.1] - 2025-06-23

## Fixed

- Fix CQL mapping cardinality aggregation ([#295](https://github.com/medizininformatik-initiative/fhir-ontology-generator/issues/295) @paulolaup)
- Fix FHIRPath expression for Encounter resource in availability measure ([#292](https://github.com/medizininformatik-initiative/fhir-ontology-generator/issues/292) @juliangruendner)
- Reintroduce modules MII CDS Bildgebung, Enwilligung, and Pathologie into DSE ([#296](https://github.com/medizininformatik-initiative/fhir-ontology-generator/issues/296) @paulolaup)
- Remove primitive elements from DSE Profile Details tree ([#299](https://github.com/medizininformatik-initiative/fhir-ontology-generator/issues/299) @paulolaup)
- Keep module root node in profile tree ([#298](https://github.com/medizininformatik-initiative/fhir-ontology-generator/issues/298) @Frontman50)

## [3.8.0] - 2025-06-10

## Added

- Add 'Cause of Death' criteria class based on MII CDS Person module by @paulolaup in https://github.com/medizininformatik-initiative/fhir-ontology-generator/issues/49

## Changed

- Update display name determination for criteria classes with fixed concept identifiers such as the patients age by @paulolaup in https://github.com/medizininformatik-initiative/fhir-ontology-generator/issues/217

## Removed

- Cleanup generated SQL import files (removal of unused tables, indices, etc.) by @paulolaup in https://github.com/medizininformatik-initiative/fhir-ontology-generator/issues/62

## [3.7.0] - 2025-05-19

## Changed

- Make (almost) all fields selectable in feature selection by @Frontman50 in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/280
- Finish refactoring of project by @paulolaup as specified in https://github.com/medizininformatik-initiative/fhir-ontology-generator/issues/146
- Refactor composite tests by @Frontman, @paulolaup in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/273

## Fixed

- Change ICU module name for feature selection by @Frontman50 in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/279
- Fix database import generation for feature selection UI profiles by @paulolaup as specified in https://github.com/medizininformatik-initiative/fhir-ontology-generator/issues/270

## [3.6.0] - 2025-5-12

## Added

- Implement compaction of DSE profile tree by @paulolaup in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/265

## Changed

- Change treatment of FHIR Patient resource in DSE by @paulolaup in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/264
- Update test blood pressure with composite to new structure new file structure by @Frontman50 in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/261
- Update docs by @paulolaup in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/269

## Fixed

- Fix Invalid cql mapping for composite attributes by @Frontman50 in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/266

## [3.5.0] - 2025-05-05

## Added

- Add module display names and translations by @Frontman50 in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/251
- Separate references into distinct field in DSE profiles by @paulolaup in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/254
- Add shortcut for extension fields containing references by @paulolaup in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/255

### [3.4.0] - 2025-04-24

## Added

- Refactor module name and files names by @paulolaup in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/242
- Refactor project directory by @paulolaup in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/228
- Add FDPG availability measure generation by @Frontman50 in https://github.com/medizininformatik-initiative/fhir-ontology-generator/issues/209
- Add FDPG availability measure generation output to CI by @Frontman50 in https://github.com/medizininformatik-initiative/fhir-ontology-generator/issues/229

## [3.2.2] - 2025-03-17

### Fixed

- Add temporary fix to address automatic selection of referenced profiles in UI by @paulolaup in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/212

## [3.2.1] - 2025-03-17

### Fix

- Reintroduce missing profile snapshots for DSE gen by @paulolaup in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/202
- Undo changes caused in FHIRSearch mapping by update of CQL mapping by @paulolaup in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/205

## [3.2.0] - 2025-03-13

### Added

- Added typing for all attributes and values by @Frontman50 in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/173
- Extend CQL mapping model by adding basic cardinality information by @paulolaup in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/194
- Implement Coding resolution for CQL mapping by @paulolaup in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/190

### Changed

- Update test data by @paulolaup in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/196
- Improve CQL mapping naming ang typing by @paulolaup in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/183

### Fixed

- Fix Elasticsearch tokenizer max N-gram length by @paulolaup in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/174
- Fix issues generation with FHIRPath generation for CQL mapping by @paulolaup in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/177
- Fix consent integration tests by @paulolaup in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/180
- Fix generated FHIRPath expressions in CQL mapping by @paulolaup in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/181
- Fix attribute naming in CQL mapping by @paulolaup in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/185
- Fix term code emission for CQL mapping in combined consent generation by @paulolaup in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/192

## [3.1.0] - 2025-02-13

| Modul            | Version                                                                    | Changelog    |
|------------------|----------------------------------------------------------------------------|--------------|
| MII_DIAGNOSE     | "de.medizininformatikinitiative.kerndatensatz.diagnose 2025.0.0-alpha2"    |              |
| MII_LAB          | "de.medizininformatikinitiative.kerndatensatz.laborbefund 2025.0.0-alpha1" |              |
| MII_MEDICATION   | "de.medizininformatikinitiative.kerndatensatz.medikation 2025.0.0-alpha5"  |              |
| MII_PERSON       | "de.medizininformatikinitiative.kerndatensatz.person 2025.0.0-alpha4"      |              |
| MII_PROCEDURE    | "de.medizininformatikinitiative.kerndatensatz.prozedur 2025.0.0-alpha2"    |              |
| MII_FALL         | "de.medizininformatikinitiative.kerndatensatz.fall 2025.0.0-alpha4"        |              |
| MII_SPECIMEN     | "de.medizininformatikinitiative.kerndatensatz.biobank 2025.0.0"            |              |
| MII_CONSENT      | "de.medizininformatikinitiative.kerndatensatz.consent 1.0.7"               |              |
| MII_ICU          | "de.medizininformatikinitiative.kerndatensatz.icu 2025.0.1"                | Added to DSE |
| MII_MOLGEN       | "de.medizininformatikinitiative.kerndatensatz.molgen 2025.0.0"             | Added to DSE |
| MII_RADIOLOGY    | "de.medizininformatikinitiative.kerndatensatz.bildgebung 2025.0.0"         | Added to DSE |
| MII_ONKOLOGY     | "de.medizininformatikinitiative.kerndatensatz.onkologie 2025.0.2"          | Added to DSE |
| MII_PATHOLOGY    | "de.medizininformatikinitiative.kerndatensatz.patho 2025.0.2"              | Added to DSE |
| MII_MICROBIOLOGY | "de.medizininformatikinitiative.kerndatensatz.mikrobiologie 2025.0.1"      | Added to DSE |
| MII_STUDIES      | "de.medizininformatikinitiative.kerndatensatz.studie 2025.0.0"             | Added to DSE |


### Added

- Added Erweiterungsmodule  by @Frontman50 in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/165
- Add translations for code systems by @Frontman50 in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/121
- Make display translations searchable by @michael-82 in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/96
- Extending UI profile for display translations by @Frontman50 in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/139
- Addressed empty translation array by @Frontman50 in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/151
- Add flag to update translation files on build by @juliangruendner in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/150
- Implement type emission for time restriction in CQL mapping by @paulolaup in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/157
- blacklisting of too general value sets for filter of dse features by @juliangruendner in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/168
- create integration test base setup by @paulolaup in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/155

### Fixed

- fix: only make leaf profile tree profiles in dse selectable @juliangruendner in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/170
- Index display.original fields in elastic search files by @michael-82 in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/153
- Fix usage of wrong hash functions for contextualized termcodes by @paulolaup in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/160
- Fix key error by @paulolaup in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/142

## [3.0.1]

### Fixed

- Fixed FHIRPath expression to include missing elements currently not generated by `sq2cql` by @paulolaup in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/134

## [3.0.0] - 2024-11-20

| Modul          | Version                                                                    | Changelog                                       |
|----------------|----------------------------------------------------------------------------|-------------------------------------------------|
| MII_DIAGNOSE   | "de.medizininformatikinitiative.kerndatensatz.diagnose 2025.0.0-alpha2"    | Added orphanet, alpha-id, sct                   |
| MII_LAB        | "de.medizininformatikinitiative.kerndatensatz.laborbefund 2025.0.0-alpha1" | Extended to all lab loinc codes                 |
| MII_MEDICATION | "de.medizininformatikinitiative.kerndatensatz.medikation 2025.0.0-alpha5"  | Added MedicationStatement and MedicationRequest |
| MII_PERSON     | "de.medizininformatikinitiative.kerndatensatz.person 2025.0.0-alpha4"      | Added vital status                              |
| MII_PROCEDURE  | "de.medizininformatikinitiative.kerndatensatz.prozedur 2025.0.0-alpha2"    | Added sct                                       |
| MII_FALL       | "de.medizininformatikinitiative.kerndatensatz.fall 2025.0.0-alpha4"        | Added - new module                              |
| MII_SPECIMEN   | "de.medizininformatikinitiative.kerndatensatz.biobank 2025.0.0"            | Extend to full specimen type value set          |
| MII_CONSENT    | "de.medizininformatikinitiative.kerndatensatz.consent 1.0.7"               | Added combined consent                          |

### Added

- Add required and recommended to profile details, include mustSupport,… by @juliangruendner in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/107
- Make psql version configurable @paulolaup in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/111
- Merge same ui tree subtrees into one @paulolaup in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/114
- Add field names of profile to profile tree @juliangruendner in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/116
- Make optional values attributes configurable @paulolaup https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/118
- Resolve reference to create code filter by @juliangruendner in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/99
- Change attribute type CodeableConcept to Coding by @juliangruendner in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/123
- Added automatic CI build by @EmteZogaf in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/123
- Add fields for each profile comma separated to dse profile tree
- Generation for Dataselection Ontology
- Merging of multiple ontologies
- Generation of combined Consent
- Generation of Elastic Search ontology files
- Parceling of ontology files
- Add script for merging and loading availability files from fhir data evaluator
- Added Referenced profiles to dse fields

### Changed

- Refactored cohort selection ontology generation to on script with configs and own ontologies per FHIR (CDS) module
- ui-trees and mapping-trees are now changed to a implicit tree structure by reference to parents and children, instead of duplicating subtrees.
- Change date field to recorded date for diagnosis

### Fixed

- Fix composite generation by @BoehmDo in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/97
- Use a requests session for repeated calls to speed up terminology server access
- Ensure atc hierarchy is added



## [3.0.0-alpha.1] - 2024-11-15

| Modul          | Version                                                               | Changelog                                       |
|----------------|-----------------------------------------------------------------------|-------------------------------------------------|
| MII_DIAGNOSE   | "de.medizininformatikinitiative.kerndatensatz.diagnose 2025.0.0-alpha1" | Added Orphanet                                  |
| MII_LAB        | "de.medizininformatikinitiative.kerndatensatz.laborbefund 2025.0.0-alpha1" |                                                 |
| MII_MEDICATION | "de.medizininformatikinitiative.kerndatensatz.medikation 2025.0.0-alpha3" | Added MedicationStatement and MedicationRequest |
| MII_PERSON     | "de.medizininformatikinitiative.kerndatensatz.person 2025.0.0-alpha1" |                                                 |
| MII_PROCEDURE  | "de.medizininformatikinitiative.kerndatensatz.prozedur 2025.0.0-alpha1" |                                                 |
| MII_FALL       | "de.medizininformatikinitiative.kerndatensatz.fall 2025.0.0-alpha1"   |                                                 |
| MII_SPECIMEN   | "de.medizininformatikinitiative.kerndatensatz.biobank 2025.0.0"       |                                                 |
| MII_CONSENT    | "de.medizininformatikinitiative.kerndatensatz.consent 1.0.7"          | Added combined consent                          |

### Added

- Add required and recommended to profile details, include mustSupport,… by @juliangruendner in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/107
- Make psql version configurable @paulolaup in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/111
- Merge same ui tree subtrees into one @paulolaup in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/114
- Add field names of profile to profile tree @juliangruendner in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/116
- Make optional values attributes configurable @paulolaup https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/118
- Resolve reference to create code filter by @juliangruendner in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/99
- Change attribute type CodeableConcept to Coding by @juliangruendner in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/123
- Added automatic CI build by @EmteZogaf in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/123
- Add fields for each profile comma separated to dse profile tree

### Fixed

- Fix composite generation by @BoehmDo in https://github.com/medizininformatik-initiative/fhir-ontology-generator/pull/97

## [3.0.0-alpha] - 2024-10-20

| Modul          | Version | Changelog |
|----------------| ------------- |-------|
| MII_DIAGNOSE   |  "de.medizininformatikinitiative.kerndatensatz.diagnose 2025.0.0-alpha1" |       |
| MII_LAB        | "de.medizininformatikinitiative.kerndatensatz.laborbefund 2025.0.0-alpha1" |       |
| MII_MEDICATION | "de.medizininformatikinitiative.kerndatensatz.medikation 2025.0.0-alpha1" |       |
| MII_PERSON     | "de.medizininformatikinitiative.kerndatensatz.person 2025.0.0-alpha1" |       |
| MII_PROCEDURE  | "de.medizininformatikinitiative.kerndatensatz.prozedur 2025.0.0-alpha1" |       |
| MII_FALL       | "de.medizininformatikinitiative.kerndatensatz.fall 2025.0.0-alpha1" | |
| MII_SPECIMEN   | "de.medizininformatikinitiative.kerndatensatz.biobank 1.0.8" |       |
| MII_CONSENT    | "de.medizininformatikinitiative.kerndatensatz.consent 1.0.7" |       |


### Added

- Generation for Dataselection Ontology
- Merging of multiple ontologies
- Generation of combined Consent
- Generation of Elastic Search ontology files
- Parceling of ontology files
- Add script for merging and loading availability files from fhir data evaluator

### Changed

- Refactored cohort selection ontology generation to on script with configs and own ontologies per FHIR (CDS) module
- ui-trees and mapping-trees are now changed to a implicit tree structure by reference to parents and children, instead of duplicating subtrees.
- Change date field to recorded date for diagnosis


### Fixed

- Use a requests session for repeated calls to speed up terminology server access

## [2.0.0] - 2024-06-17


Updated FHIR KDS Profiles to match the latest MII Release:

| Modul | Version | Changelog |
| ------------- | ------------- | ------------- |
| MII_DIAGNOSE |  "de.medizininformatikinitiative.kerndatensatz.diagnose 2024.0.0" | ICD10 v2024 |
| MII_LAB | "de.medizininformatikinitiative.kerndatensatz.laborbefund 1.0.6" | Laboratory values do no longer support value filters but are still restricted to the TOP300 |
| MII_MEDICATION | "de.medizininformatikinitiative.kerndatensatz.medikation 2.0.0" | ATC v2024 |
| MII_PERSON | "de.medizininformatikinitiative.kerndatensatz.person 2024.0.0" | |
| MII_PROCEDURE | "de.medizininformatikinitiative.kerndatensatz.prozedur 2024.0.0" | With the latest Terminology Update, the readability of OPS v2024 Code displays has significantly improved.  |
| MII_SPECIMEN | "de.medizininformatikinitiative.kerndatensatz.biobank 1.0.1" | Specimen now encompasses all concept referenced (n = 1790) in the valueset binding instead of the most commonly used (n = 50) |


## [INIT] - pre 2024-06-17

Previous versions do not have a changelog.