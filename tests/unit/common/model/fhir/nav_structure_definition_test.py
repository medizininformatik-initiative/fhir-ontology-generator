from typing import Optional

import pytest
from _pytest.fixtures import FixtureRequest
from common.model.fhir.nav_element_definition import NavElementDefinition
from common.model.fhir.nav_structure_definition import (
    NavStructureDefinition,
    _elem_def_tree_to_list,
)

_STRUCT_DEF_URL = "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung"


@pytest.fixture
def nav_struct_def(package_manager) -> NavStructureDefinition:
    struct_def = package_manager.find({"url": _STRUCT_DEF_URL})
    if not struct_def:
        raise FileNotFoundError(
            f"Structure definition {_STRUCT_DEF_URL} is not present in package cache"
        )
    return NavStructureDefinition.model_validate(struct_def.model_dump())


@pytest.fixture
def struct_def_json(nav_struct_def) -> dict:
    return nav_struct_def.model_dump()


@pytest.fixture
def nav_elem_def(request: FixtureRequest, nav_struct_def: NavStructureDefinition):
    match request.param:
        case str(v):
            return nav_struct_def.get_element_by_id(v)
        case _ as v:
            raise ValueError(f"Unsupported parameter type {type(v)}")


@pytest.mark.parametrize(
    argnames=["nav_elem_def", "parent", "elements", "slices"],
    argvalues=[
        pytest.param(
            "Encounter.class",
            "Encounter",
            set(),
            set(),
            id="elem_def_without_children",
        ),
        pytest.param(
            "Encounter.classHistory",
            "Encounter",
            {
                "Encounter.classHistory.id",
                "Encounter.classHistory.extension",
                "Encounter.classHistory.modifierExtension",
                "Encounter.classHistory.class",
                "Encounter.classHistory.period",
            },
            set(),
            id="elem_def_with_sub_elements",
        ),
        pytest.param(
            "Encounter.type",
            "Encounter",
            set(),
            {"Encounter.type:Kontaktebene", "Encounter.type:KontaktArt"},
            id="elem_def_with_slices",
        ),
        pytest.param(
            "Encounter",
            None,
            {
                "Encounter.account",
                "Encounter.appointment",
                "Encounter.basedOn",
                "Encounter.class",
                "Encounter.classHistory",
                "Encounter.contained",
                "Encounter.diagnosis",
                "Encounter.episodeOfCare",
                "Encounter.extension",
                "Encounter.hospitalization",
                "Encounter.id",
                "Encounter.identifier",
                "Encounter.implicitRules",
                "Encounter.language",
                "Encounter.length",
                "Encounter.location",
                "Encounter.meta",
                "Encounter.modifierExtension",
                "Encounter.partOf",
                "Encounter.participant",
                "Encounter.period",
                "Encounter.priority",
                "Encounter.reasonCode",
                "Encounter.reasonReference",
                "Encounter.serviceProvider",
                "Encounter.serviceType",
                "Encounter.status",
                "Encounter.statusHistory",
                "Encounter.subject",
                "Encounter.text",
                "Encounter.type",
            },
            set(),
            id="root_elem_def",
        ),
    ],
    indirect=["nav_elem_def"],
)
def test_elements_resolved_from_struct_def_are_navigable(
    nav_elem_def: NavElementDefinition,
    parent: Optional[str],
    elements: set[str],
    slices: set[str],
    nav_struct_def: NavStructureDefinition,
):
    assert isinstance(nav_elem_def, NavElementDefinition)
    assert nav_elem_def.struct_def is nav_struct_def

    assert (nav_elem_def.parent.id if nav_elem_def.parent else None) == parent
    assert set(v.id for v in nav_elem_def.elements) == elements
    assert set(v.id for v in nav_elem_def.slices) == slices
    assert all(isinstance(v, NavElementDefinition) for v in nav_elem_def.children)


@pytest.mark.parametrize(
    argnames=["path", "expected_ids"],
    argvalues=[
        pytest.param(
            "Encounter.type",
            {
                "Encounter.type",
                "Encounter.type:Kontaktebene",
                "Encounter.type:KontaktArt",
            },
            id="path_with_slices",
        ),
        pytest.param(
            "Encounter.classHistory",
            {"Encounter.classHistory"},
            id="path_without_slices",
        ),
        pytest.param("Encounter.nonexistent", set(), id="unknown_path"),
    ],
)
def test_get_element_by_path_returns_navigable_elements(
    nav_struct_def: NavStructureDefinition,
    path: str,
    expected_ids: set[str],
):
    matches = nav_struct_def.get_element_by_path(path)

    assert {ed.id for ed in matches} == expected_ids
    assert all(isinstance(ed, NavElementDefinition) for ed in matches)


def test_all_source_elements_are_present_exactly_once(
    nav_struct_def: NavStructureDefinition,
    struct_def_json: dict,
):
    source_ids = [ed["id"] for ed in struct_def_json["snapshot"]["element"]]
    nav_ids = [ed.id for ed in nav_struct_def.snapshot.element]

    assert sorted(nav_ids) == nav_ids, "elements should be sorted by id"
    assert set(nav_ids) == set(source_ids)
    assert len(nav_ids) == len(
        source_ids
    ), "No element should be dropped or duplicated by the tree flattening"


@pytest.mark.parametrize(
    argnames=["nav_elem_def", "expected_ids"],
    argvalues=[
        pytest.param("Encounter.class", {"Encounter.class"}, id="leaf_element"),
        pytest.param(
            "Encounter.classHistory",
            {
                "Encounter.classHistory",
                "Encounter.classHistory.id",
                "Encounter.classHistory.extension",
                "Encounter.classHistory.modifierExtension",
                "Encounter.classHistory.class",
                "Encounter.classHistory.period",
            },
            id="element_with_sub_elements",
        ),
        pytest.param(
            "Encounter.type",
            {
                "Encounter.type",
                "Encounter.type:Kontaktebene",
                "Encounter.type:KontaktArt",
            },
            id="element_with_slices",
        ),
    ],
    indirect=["nav_elem_def"],
)
def test__elem_def_tree_to_list_flattens_whole_subtree(
    nav_elem_def: NavElementDefinition, expected_ids: set[str]
):
    flattened = _elem_def_tree_to_list(nav_elem_def)

    assert flattened[0] is nav_elem_def
    assert all(isinstance(ed, NavElementDefinition) for ed in flattened)
    assert {ed.id for ed in flattened} == expected_ids


def test__elem_def_tree_to_list_covers_whole_struct_def(
    nav_struct_def: NavStructureDefinition,
):
    root = nav_struct_def.get_element_by_id(nav_struct_def.type)

    flattened = _elem_def_tree_to_list(root)

    assert {ed.id for ed in flattened} == {
        ed.id for ed in nav_struct_def.snapshot.element
    }
    assert len(flattened) == len(nav_struct_def.snapshot.element)
