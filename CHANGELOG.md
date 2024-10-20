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