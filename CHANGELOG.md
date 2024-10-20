# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),

## [UNRELEASED] - yyyy-mm-dd

### Added
### Changed
### Deprecated
### Removed
### Fixed
### Security

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