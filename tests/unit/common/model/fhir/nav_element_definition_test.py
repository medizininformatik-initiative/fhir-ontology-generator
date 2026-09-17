from typing import Optional

import pytest
from fhir.resources.R4B.elementdefinition import ElementDefinition

from common.model.fhir.structure_definition import IdxStructureDefinition
from common.model.fhir.nav_element_definition import NavElementDefinition


@pytest.mark.parametrize(
    argnames=["elem_def", "profile", "elements", "slices"],
    argvalues=[
        pytest.param(
            "Encounter.class",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
            set(),
            set(),
            id="elem_def_without_children",
        ),
        pytest.param(
            "Encounter.classHistory",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
            {
                "Encounter.classHistory.id",
                "Encounter.classHistory.extension",
                "Encounter.classHistory.modifierExtension",
                "Encounter.classHistory.class",
                "Encounter.classHistory.period",
            },
            set(),
            id="elem_def_with_children",
        ),
        pytest.param(
            "Encounter.type",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
            set(),
            {"Encounter.type:Kontaktebene", "Encounter.type:KontaktArt"},
            id="elem_def_with_slices",
        ),
    ],
    indirect=["elem_def", "profile"],
)
def test_construct_from(
    elem_def: ElementDefinition,
    profile: IdxStructureDefinition,
    elements: set[NavElementDefinition],
    slices: set[NavElementDefinition],
):
    nav_elem_def = NavElementDefinition.construct_from(profile, elem_def)

    assert isinstance(nav_elem_def, NavElementDefinition)
    if nav_elem_def.parent:
        assert isinstance(nav_elem_def.parent, NavElementDefinition)

    assert all(
        (isinstance(v, NavElementDefinition) for v in nav_elem_def.children)
    ), """
        All sub element definitions should be instances of 'NavigableElementDefinition'
    """
    assert all(
        (v.parent and v.parent.id == nav_elem_def.id for v in nav_elem_def.elements)
    ), """
        All sub element definitions of the element definition should have it as a parent
    """

    assert set(v.id for v in nav_elem_def.elements) == elements
    assert set(v.id for v in nav_elem_def.slices) == slices


@pytest.mark.parametrize(
    argnames=["elem_def", "profile", "rel_id", "expected_id"],
    argvalues=[
        pytest.param(
            "Encounter.classHistory",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
            "class",
            "Encounter.classHistory.class",
            id="existing_child",
        ),
        pytest.param(
            "Encounter.classHistory",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
            "nonexistent",
            None,
            id="missing_child",
        ),
    ],
    indirect=["elem_def", "profile"],
)
def test_element_by_rel_id(
    elem_def: ElementDefinition,
    profile: IdxStructureDefinition,
    rel_id: str,
    expected_id: Optional[str],
):
    nav_elem_def = NavElementDefinition.construct_from(profile, elem_def)

    result = nav_elem_def.element(rel_id=rel_id)

    if expected_id is None:
        assert result is None
    else:
        assert isinstance(result, NavElementDefinition)
        assert result.id == expected_id


@pytest.mark.parametrize(
    argnames=["elem_def", "profile", "full_id", "expected_id"],
    argvalues=[
        pytest.param(
            "Encounter.classHistory",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
            "Encounter.classHistory.period",
            "Encounter.classHistory.period",
            id="existing_child",
        ),
        pytest.param(
            "Encounter.classHistory",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
            "Encounter.classHistory.nonexistent",
            None,
            id="missing_child",
        ),
    ],
    indirect=["elem_def", "profile"],
)
def test_element_by_full_id(
    elem_def: ElementDefinition,
    full_id: str,
    expected_id: Optional[str],
    profile: IdxStructureDefinition,
):
    nav_elem_def = NavElementDefinition.construct_from(profile, elem_def)

    result = nav_elem_def.element(full_id=full_id)

    if expected_id is None:
        assert result is None
    else:
        assert isinstance(result, NavElementDefinition)
        assert result.id == expected_id


@pytest.mark.parametrize(
    argnames=["elem_def", "profile"],
    argvalues=[
        pytest.param(
            "Encounter.classHistory",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
            id="elem_def",
        )
    ],
    indirect=["elem_def", "profile"],
)
def test_element_raises_without_arguments(
    elem_def: ElementDefinition, profile: IdxStructureDefinition
):
    nav_elem_def = NavElementDefinition.construct_from(profile, elem_def)

    with pytest.raises(ValueError):
        nav_elem_def.element()


@pytest.mark.parametrize(
    argnames=["elem_def", "profile", "name", "expected_id"],
    argvalues=[
        pytest.param(
            "Encounter.type",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
            "Kontaktebene",
            "Encounter.type:Kontaktebene",
            id="existing_slice",
        ),
        pytest.param(
            "Encounter.type",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
            "unknown",
            None,
            id="missing_slice",
        ),
    ],
    indirect=["elem_def", "profile"],
)
def test_slice_by_name(
    elem_def: ElementDefinition,
    profile: IdxStructureDefinition,
    name: str,
    expected_id: Optional[str],
):
    nav_elem_def = NavElementDefinition.construct_from(profile, elem_def)

    result = nav_elem_def.slice(name=name)

    if expected_id is None:
        assert result is None
    else:
        assert isinstance(result, NavElementDefinition)
        assert result.id == expected_id


@pytest.mark.parametrize(
    argnames=["elem_def", "full_id", "expected_id", "profile"],
    argvalues=[
        pytest.param(
            "Encounter.type",
            "Encounter.type:KontaktArt",
            "Encounter.type:KontaktArt",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
            id="existing_slice",
        ),
        pytest.param(
            "Encounter.type",
            "Encounter.type:unknown",
            None,
            "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
            id="missing_slice",
        ),
    ],
    indirect=["elem_def", "profile"],
)
def test_slice_by_full_id(
    elem_def: ElementDefinition,
    full_id: str,
    expected_id: Optional[str],
    profile: IdxStructureDefinition,
):
    nav_elem_def = NavElementDefinition.construct_from(profile, elem_def)

    result = nav_elem_def.slice(full_id=full_id)

    if expected_id is None:
        assert result is None
    else:
        assert isinstance(result, NavElementDefinition)
        assert result.id == expected_id


@pytest.mark.parametrize(
    argnames=["profile", "elem_def"],
    argvalues=[
        pytest.param(
            "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
            "Encounter.type",
            id="elem_def",
        )
    ],
    indirect=["profile", "elem_def"],
)
def test_slice_raises_without_arguments(
    elem_def: ElementDefinition, profile: IdxStructureDefinition
):
    nav_elem_def = NavElementDefinition.construct_from(profile, elem_def)

    with pytest.raises(ValueError):
        nav_elem_def.slice()


@pytest.mark.parametrize(
    argnames=["elem_def", "rel_id", "expected_id", "profile"],
    argvalues=[
        pytest.param(
            "Encounter.classHistory",
            "class",
            "Encounter.classHistory.class",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
            id="rel_id_targets_child",
        ),
        pytest.param(
            "Encounter.type",
            ":Kontaktebene",
            "Encounter.type:Kontaktebene",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
            id="rel_id_targets_slice",
        ),
    ],
    indirect=["elem_def", "profile"],
)
def test_child_by_rel_id(
    elem_def: ElementDefinition,
    rel_id: str,
    expected_id: str,
    profile: IdxStructureDefinition,
):
    nav_elem_def = NavElementDefinition.construct_from(profile, elem_def)

    result = nav_elem_def.child(rel_id=rel_id)

    assert isinstance(result, NavElementDefinition)
    assert result.id == expected_id


@pytest.mark.parametrize(
    argnames=["elem_def", "full_id", "expected_id", "profile"],
    argvalues=[
        pytest.param(
            "Encounter.classHistory",
            "Encounter.classHistory.class",
            "Encounter.classHistory.class",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
            id="full_id_matches_child",
        ),
        pytest.param(
            "Encounter.type",
            "Encounter.type:Kontaktebene",
            "Encounter.type:Kontaktebene",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
            id="full_id_matches_slice",
        ),
        pytest.param(
            "Encounter.classHistory",
            "Encounter.classHistory.unknown",
            None,
            "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
            id="full_id_matches_neither",
        ),
    ],
    indirect=["elem_def", "profile"],
)
def test_child_by_full_id(
    elem_def: ElementDefinition,
    full_id: str,
    expected_id: Optional[str],
    profile: IdxStructureDefinition,
):
    nav_elem_def = NavElementDefinition.construct_from(profile, elem_def)

    result = nav_elem_def.child(full_id=full_id)

    if expected_id is None:
        assert result is None
    else:
        assert isinstance(result, NavElementDefinition)
        assert result.id == expected_id


@pytest.mark.parametrize(
    argnames=["elem_def", "profile"],
    argvalues=[
        pytest.param(
            "Encounter.classHistory",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
            id="elem_def",
        )
    ],
    indirect=["elem_def", "profile"],
)
def test_child_raises_without_arguments(
    elem_def: ElementDefinition, profile: IdxStructureDefinition
):
    nav_elem_def = NavElementDefinition.construct_from(profile, elem_def)

    with pytest.raises(ValueError):
        nav_elem_def.child()


@pytest.mark.parametrize(
    argnames=["elem_def", "profile", "expected"],
    argvalues=[
        pytest.param(
            "Observation.code",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-labor/StructureDefinition/ObservationLab",
            "code",
            id="simple",
        ),
        pytest.param(
            "Observation.effective[x]",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-labor/StructureDefinition/ObservationLab",
            "effective[x]",
            id="when-polymorphic-return-id-with-polymorhpism-indicator",
        ),
        pytest.param(
            "Observation.value[x]:valueQuantity",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-labor/StructureDefinition/ObservationLab",
            ":valueQuantity",
            id="when-slice-def-elem-def-return-slice-name-with-colon-prefix",
        ),
    ],
    indirect=["elem_def", "profile"],
)
def test_rel_id_property(
    elem_def: ElementDefinition, profile: IdxStructureDefinition, expected
):
    nav_elem_def = NavElementDefinition.construct_from(profile, elem_def)
    assert nav_elem_def.rel_id == expected


@pytest.mark.parametrize(
    argnames=["elem_def", "profile", "expected"],
    argvalues=[
        pytest.param(
            "Observation.code",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-labor/StructureDefinition/ObservationLab",
            "code",
            id="simple",
        ),
        pytest.param(
            "Observation.effective[x]",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-labor/StructureDefinition/ObservationLab",
            "effective",
            id="when-polymorphic-return-path-without-poylmorphism-indicator",
        ),
        pytest.param(
            "Observation.value[x]:valueQuantity",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-labor/StructureDefinition/ObservationLab",
            None,
            id="when-slice-def-elem-def-return-none",
        ),
    ],
    indirect=["elem_def", "profile"],
)
def test_rel_path_property(
    elem_def: ElementDefinition, profile: IdxStructureDefinition, expected
):
    nav_elem_def = NavElementDefinition.construct_from(profile, elem_def)
    assert nav_elem_def.rel_path == expected
