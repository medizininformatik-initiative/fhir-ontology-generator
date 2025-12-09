import pytest

from data_selection_extraction.config.profile_detail import MatchEntry


@pytest.mark.parametrize(
    argnames=["match_entry", "elem_def", "profile", "expected"],
    argvalues=[
        (
            MatchEntry(target="id", exact=True, pattern="Encounter.status"),
            "Encounter.status",
            "http://hl7.org/fhir/StructureDefinition/Encounter",
            True,
        ),
        (
            MatchEntry(target="id", exact=True, pattern="Encounter.type"),
            "Encounter.type:Kontaktebene",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
            True,
        ),
        (
            MatchEntry(target="id", exact=True, pattern="Encounter.serviceType"),
            "Encounter.serviceType.coding",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
            True,
        ),
        (
            MatchEntry(target="id", exact=True, pattern="Encounter.location"),
            "Encounter.location:Zimmer.status",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
            True,
        ),
        (
            MatchEntry(target="id", exact=True, pattern="Encounter.status"),
            "Encounter.statusHistory",
            "http://hl7.org/fhir/StructureDefinition/Encounter",
            False,
        ),
    ],
    indirect=["elem_def", "profile"],
    ids=[
        "encounter-exact-match",
        "encounter-exact-slice-match",
        "encounter-exact-sub-element-match",
        "encounter-exact-slice-sub-element-match",
        "encounter-exact-similar-no-match",
    ],
)
def test_match_entry(match_entry: MatchEntry, elem_def, profile, expected):
    return match_entry.matches(elem_def) == expected