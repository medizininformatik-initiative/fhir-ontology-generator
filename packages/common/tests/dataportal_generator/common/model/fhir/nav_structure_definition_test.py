import json
from pathlib import Path
from typing import Optional

import pytest
from _pytest.fixtures import FixtureRequest
from  dataportal_generator.common.model.fhir.nav_element_definition import NavElementDefinition
from dataportal_generator.common.model.fhir.nav_structure_definition import (
    NavStructureDefinition,
    _elem_def_tree_to_list,
)


@pytest.fixture
def struct_def_json(resources: Path) -> dict:
    struct_def_path = resources / "structure_definitions" / "MII_PR_Fall_KontaktGesundheitseinrichtung.json"
    with struct_def_path.open(mode="r", encoding="utf-8") as fd:
        return json.load(fd)


@pytest.fixture
def nav_struct_def(struct_def_json: dict) -> NavStructureDefinition:
    return NavStructureDefinition.model_validate(struct_def_json)


@pytest.fixture
def nav_elem_def(request: FixtureRequest, nav_struct_def: NavStructureDefinition):
    match request.param:
        case str(v):
            return nav_struct_def.get_element_by_id(v)
        case _ as v:
            raise ValueError(f"Unsupported parameter type {type(v)}")


@pytest.mark.parametrize(
    argnames=["nav_elem_def", "elements", "slices"],
    argvalues=[
        pytest.param(
            "Encounter.class",
            set(),
            set(),
            id="elem_def_without_children",
        ),
        pytest.param(
            "Encounter.classHistory",
            {"Encounter.classHistory.id", "Encounter.classHistory.extension",
             "Encounter.classHistory.modifierExtension", "Encounter.classHistory.class",
             "Encounter.classHistory.period"},
            set(),
            id="elem_def_with_children",
        ),
        pytest.param(
            "Encounter.type",
            set(),
            {"Encounter.type:Kontaktebene", "Encounter.type:KontaktArt"},
            id="elem_def_with_slices",
        ),
        pytest.param(
            "Encounter",
            None,
            set(),
            id="root_elem_def",
        ),
    ],
    indirect=["nav_elem_def"],
)
def test_elements_resolved_from_struct_def_are_navigable(
    nav_elem_def: NavElementDefinition, elements: Optional[set[str]], slices: set[str],
    nav_struct_def: NavStructureDefinition,
):
    assert isinstance(nav_elem_def, NavElementDefinition)
    assert nav_elem_def.struct_def is nav_struct_def

    if elements is not None:
        assert set(v.id for v in nav_elem_def.elements) == elements
    assert set(v.id for v in nav_elem_def.slices) == slices
    assert all(isinstance(v, NavElementDefinition) for v in nav_elem_def.sub_elem_defs)


@pytest.mark.parametrize(
    argnames=["path", "expected_ids"],
    argvalues=[
        pytest.param(
            "Encounter.type",
            {"Encounter.type", "Encounter.type:Kontaktebene", "Encounter.type:KontaktArt"},
            id="path_with_slices",
        ),
        pytest.param("Encounter.classHistory", {"Encounter.classHistory"}, id="path_without_slices"),
        pytest.param("Encounter.nonexistent", set(), id="unknown_path"),
    ],
)
def test_get_element_by_path_returns_navigable_elements(
    nav_struct_def: NavStructureDefinition, path: str, expected_ids: set[str],
):
    matches = nav_struct_def.get_element_by_path(path)

    assert {ed.id for ed in matches} == expected_ids
    assert all(isinstance(ed, NavElementDefinition) for ed in matches)


def test_all_source_elements_are_present_exactly_once(
    nav_struct_def: NavStructureDefinition, struct_def_json: dict,
):
    source_ids = [ed["id"] for ed in struct_def_json["snapshot"]["element"]]
    nav_ids = [ed.id for ed in nav_struct_def.snapshot.element]

    assert sorted(nav_ids) == nav_ids, "elements should be sorted by id"
    assert set(nav_ids) == set(source_ids)
    assert len(nav_ids) == len(source_ids), "no element should be dropped or duplicated by the tree flattening"


@pytest.mark.parametrize(
    argnames=["nav_elem_def", "expected_ids"],
    argvalues=[
        pytest.param("Encounter.class", {"Encounter.class"}, id="leaf_element"),
        pytest.param(
            "Encounter.classHistory",
            {"Encounter.classHistory", "Encounter.classHistory.id", "Encounter.classHistory.extension",
             "Encounter.classHistory.modifierExtension", "Encounter.classHistory.class",
             "Encounter.classHistory.period"},
            id="element_with_children",
        ),
        pytest.param(
            "Encounter.type",
            {"Encounter.type", "Encounter.type:Kontaktebene", "Encounter.type:KontaktArt"},
            id="element_with_slices",
        ),
    ],
    indirect=["nav_elem_def"],
)
def test__elem_def_tree_to_list_flattens_whole_subtree(nav_elem_def: NavElementDefinition, expected_ids: set[str]):
    flattened = _elem_def_tree_to_list(nav_elem_def)

    assert flattened[0] is nav_elem_def
    assert all(isinstance(ed, NavElementDefinition) for ed in flattened)
    assert {ed.id for ed in flattened} == expected_ids


def test__elem_def_tree_to_list_covers_whole_struct_def(nav_struct_def: NavStructureDefinition):
    root = nav_struct_def.get_element_by_id(nav_struct_def.type)

    flattened = _elem_def_tree_to_list(root)

    assert {ed.id for ed in flattened} == {ed.id for ed in nav_struct_def.snapshot.element}
    assert len(flattened) == len(nav_struct_def.snapshot.element)
