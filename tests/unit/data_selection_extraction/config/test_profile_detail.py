import pytest

from data_selection_extraction.config.profile_detail import FieldConfigEntry


@pytest.mark.parametrize(
    argnames=["config_entry", "elem_def", "profile", "expected"],
    argvalues=[
        pytest.param(
            FieldConfigEntry(pattern={"id": "Encounter.status"}),
            "Encounter.status",
            "http://hl7.org/fhir/StructureDefinition/Encounter",
            True,
            id="encounter-exact-should-match",
        ),
        pytest.param(
            FieldConfigEntry(pattern={"id": "Encounter.type"}),
            "Encounter.type:Kontaktebene",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
            False,
            id="encounter-exact-slice-should-not-match",
        ),
        pytest.param(
            FieldConfigEntry(pattern={"id": "Encounter.serviceType"}),
            "Encounter.serviceType.coding",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
            False,
            id="encounter-exact-sub-element-should-not-match",
        ),
        pytest.param(
            FieldConfigEntry(pattern={"id": "Encounter.location"}),
            "Encounter.location:Zimmer.status",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
            False,
            id="encounter-exact-slice-sub-element-should-not-match",
        ),
        pytest.param(
            FieldConfigEntry(pattern={"id": "Encounter.status"}),
            "Encounter.statusHistory",
            "http://hl7.org/fhir/StructureDefinition/Encounter",
            False,
            id="encounter-exact-similar-should-not-match",
        ),
        ################################################################################################################
        pytest.param(
            FieldConfigEntry(pattern={"id": "!regex:Encounter.type(?fhir:slices())"}),
            "Encounter.type:Kontaktebene",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
            True,
            id="encounter-regex-slices-filter-should-match",
        ),
        pytest.param(
            FieldConfigEntry(pattern={"id": "!regex:Encounter.type(?fhir:slices())"}),
            "Encounter.type",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
            False,
            id="encounter-regex-slices-filter-should-not-match",
        ),
        ################################################################################################################
        pytest.param(
            FieldConfigEntry(
                pattern={"id": "!regex:Encounter.type(?fhir:slicesOrSelf())"}
            ),
            "Encounter.type:Kontaktebene",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
            True,
            id="encounter-regex-slicesOrSelf-filter-should-match-1",
        ),
        pytest.param(
            FieldConfigEntry(
                pattern={"id": "!regex:Encounter.type(?fhir:slicesOrSelf())"}
            ),
            "Encounter.type",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
            True,
            id="encounter-regex-slicesOrSelf-filter-should-match-2",
        ),
        pytest.param(
            FieldConfigEntry(
                pattern={"id": "!regex:Encounter.type(?fhir:slicesOrSelf())"}
            ),
            "Encounter",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
            False,
            id="encounter-regex-slicesOrSelf-filter-should-not-match-1",
        ),
        pytest.param(
            FieldConfigEntry(
                pattern={
                    "id": "!regex:Encounter.serviceType.coding(?fhir:slicesOrSelf())"
                }
            ),
            "Encounter.serviceType.coding:Fachabteilungsschluessel.code",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
            False,
            id="encounter-regex-slicesOrSelf-filter-should-not-match-2",
        ),
        ################################################################################################################
        pytest.param(
            FieldConfigEntry(
                pattern={"id": "!regex:Encounter.serviceType(?fhir:descendants())"}
            ),
            "Encounter.serviceType.coding",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
            True,
            id="encounter-regex-descendants-filter-should-match-1",
        ),
        pytest.param(
            FieldConfigEntry(
                pattern={"id": "!regex:Encounter.serviceType(?fhir:descendants())"}
            ),
            "Encounter.serviceType.coding:Fachabteilungsschluessel",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
            True,
            id="encounter-regex-descendants-filter-should-match-2",
        ),
        pytest.param(
            FieldConfigEntry(
                pattern={"id": "!regex:Encounter.serviceType(?fhir:descendants())"}
            ),
            "Encounter.serviceType.coding:Fachabteilungsschluessel.code",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
            True,
            id="encounter-regex-descendants-filter-should-match-3",
        ),
        pytest.param(
            FieldConfigEntry(
                pattern={"id": "!regex:Encounter.serviceType(?fhir:descendants())"}
            ),
            "Encounter.serviceType",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
            False,
            id="encounter-regex-descendants-filter-should-not-match-1",
        ),
        pytest.param(
            FieldConfigEntry(
                pattern={
                    "id": "!regex:Encounter.serviceType.coding(?fhir:descendants())"
                }
            ),
            "Encounter.serviceType.coding:Fachabteilungsschluessel",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
            False,
            id="encounter-regex-descendants-filter-should-not-match-2",
        ),
        ################################################################################################################
        pytest.param(
            FieldConfigEntry(
                pattern={
                    "id": "!regex:Encounter.serviceType(?fhir:descendantsOrSelf())"
                }
            ),
            "Encounter.serviceType.coding",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
            True,
            id="encounter-regex-descendantsOrSelf-filter-should-match-1",
        ),
        pytest.param(
            FieldConfigEntry(
                pattern={
                    "id": "!regex:Encounter.serviceType(?fhir:descendantsOrSelf())"
                }
            ),
            "Encounter.serviceType.coding:Fachabteilungsschluessel",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
            True,
            id="encounter-regex-descendantsOrSelf-filter-should-match-2",
        ),
        pytest.param(
            FieldConfigEntry(
                pattern={
                    "id": "!regex:Encounter.serviceType(?fhir:descendantsOrSelf())"
                }
            ),
            "Encounter.serviceType.coding:Fachabteilungsschluessel.code",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
            True,
            id="encounter-regex-descendantsOrSelf-filter-should-match-3",
        ),
        pytest.param(
            FieldConfigEntry(
                pattern={
                    "id": "!regex:Encounter.serviceType.coding(?fhir:descendantsOrSelf())"
                }
            ),
            "Encounter.serviceType.coding",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
            True,
            id="encounter-regex-descendantsOrSelf-filter-should-match-4",
        ),
        pytest.param(
            FieldConfigEntry(
                pattern={
                    "id": "!regex:Encounter.serviceType.coding(?fhir:descendantsOrSelf())"
                }
            ),
            "Encounter.serviceType.coding:Fachabteilungsschluessel",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
            False,
            id="encounter-regex-descendantsOrSelf-filter-should-not-match-1",
        ),
        ################################################################################################################
        pytest.param(
            FieldConfigEntry(
                pattern={
                    "id": "!regex:Encounter.location(?fhir:slices();descendants())"
                }
            ),
            "Encounter.location:Zimmer.physicalType",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
            True,
            id="encounter-regex-slices-descendantsOrSelf-filters-should-match-1",
        ),
        pytest.param(
            FieldConfigEntry(
                pattern={
                    "id": "!regex:Encounter.location(?fhir:slices();descendants())"
                }
            ),
            "Encounter.location.physicalType",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
            False,
            id="encounter-regex-slices-descendantsOrSelf-filters-should-not-match-1",
        ),
        ################################################################################################################
        pytest.param(
            FieldConfigEntry(
                pattern={
                    "id": "!regex:Encounter.serviceType(?fhir:descendants();slices())"
                }
            ),
            "Encounter.serviceType.coding:Fachabteilungsschluessel",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
            True,
            id="encounter-regex-descendantsOrSelf-slices-filters-should-match-1",
        ),
        pytest.param(
            FieldConfigEntry(
                pattern={
                    "id": "!regex:Encounter.serviceType(?fhir:descendants();slices())"
                }
            ),
            "Encounter.serviceType.coding:Fachabteilungsschluessel.code",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
            False,
            id="encounter-regex-descendantsOrSelf-slices-filters-should-not-match-1",
        ),
    ],
    indirect=["elem_def", "profile"],
)
def test_match_entry(config_entry: FieldConfigEntry, elem_def, profile, expected):
    assert config_entry.matches(elem_def) == expected


@pytest.mark.parametrize(
    argnames="profile",
    argvalues=[
        pytest.param(
            "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
            id="example-mii-cds-encounter-contact-profile",
        )
    ],
    indirect=["profile"],
)
def test_match_entry_must_support_filtering(profile):
    match_entry = FieldConfigEntry(
        pattern={
            "mustSupport": True,
        }
    )
    for elem_def in profile.snapshot.element:
        assert match_entry.matches(elem_def) == (
            elem_def.mustSupport if (elem_def.mustSupport is not None) else False
        ), f"""
        Element definition '{elem_def.id}' fails mustSupport filter test
        """
