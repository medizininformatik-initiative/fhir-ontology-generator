from itertools import combinations
from typing import Any, List

import pytest
from fhir.resources.R4B.coding import Coding
from fhir.resources.R4B.element import Element
from fhir.resources.R4B.elementdefinition import (
    ElementDefinition,
    ElementDefinitionBinding,
    ElementDefinitionSlicing,
    ElementDefinitionSlicingDiscriminator,
    ElementDefinitionType,
)
from fhir.resources.R4B.parameters import ParametersParameter

from common.model.fhir.structure_definition import StructureDefinitionSnapshot
from common.util.fhir.package.manager import FhirPackageManager
from common.util.fhirpath import functions
from common.util.fhirpath.functions import (
    _append_filter_from_profile_discriminated_elem,
    _element_data_to_fhirpath_filter,
    _element_to_fhirpath_filter,
    _find_polymorphic_value,
    _find_value_for_discriminator_pattern_or_value,
    _get_filter_from_pattern_or_value_discriminated_elem,
    filter_for_slice,
)

DISCRIMINATOR_PATHS = {
    "value": "code",
    "pattern": "category",
    "exists": "identifier",
    "type": "$this.value",
    "profile": "$this",
}

DISCRIMINATOR_PREDICATES = {
    "value": "code.coding.exists(system = 'value-system' and code = 'value-code')",
    "pattern": "category.coding.exists(system = 'pattern-system' and code = 'pattern-code')",
    "exists": "identifier.exists()",
    "type": "value.exists($this is Quantity)",
    "profile": "resolve().meta.profile.exists($this = 'profile-url')",
}


def _slice_elem(
    types=None,
    element_id="Observation.component:example",
    path="Observation.component",
):
    return ElementDefinition(
        id=element_id,
        path=path,
        type=[ElementDefinitionType(code=t) for t in (types or ["Quantity"])],
    )


def _discriminator(discr_type):
    return ElementDefinitionSlicingDiscriminator(
        type=discr_type,
        path=DISCRIMINATOR_PATHS[discr_type],
    )


def _parent_with_discriminators(discriminator_types, parent_id="Observation.component"):
    return ElementDefinition(
        id=parent_id,
        path=parent_id,
        slicing=ElementDefinitionSlicing(
            discriminator=[_discriminator(t) for t in discriminator_types],
            rules="open",
        ),
    )


def _parent(parent_id, discriminators):
    return ElementDefinition(
        id=parent_id,
        path=parent_id,
        slicing=ElementDefinitionSlicing(discriminator=discriminators, rules="open"),
    )


def _discriminator_with_path(discr_type, path):
    return ElementDefinitionSlicingDiscriminator(type=discr_type, path=path)


def _expected_filter(discriminator_types):
    predicates = [DISCRIMINATOR_PREDICATES[t] for t in discriminator_types]
    return f"component.where({' and '.join(predicates)})"


def _combination_case_id(discriminator_types):
    return " + ".join(discriminator_types)


PAIRWISE_DISCRIMINATOR_CASES = [
    pytest.param(discriminator_types, id=_combination_case_id(discriminator_types))
    for discriminator_types in combinations(
        ["value", "pattern", "exists", "type", "profile"], 2
    )
]


@pytest.fixture
def discriminator_filter_stubs(monkeypatch):
    def pattern_or_value_filter(_slice_elem_def, discr_path, *_):
        discr_type = {
            DISCRIMINATOR_PATHS["value"]: "value",
            DISCRIMINATOR_PATHS["pattern"]: "pattern",
        }[discr_path]
        return f"where({DISCRIMINATOR_PREDICATES[discr_type]})"

    def profile_filter(*_):
        return f"component.where({DISCRIMINATOR_PREDICATES['profile']})"

    monkeypatch.setattr(
        functions,
        "_get_filter_from_pattern_or_value_discriminated_elem",
        pattern_or_value_filter,
    )
    monkeypatch.setattr(
        functions,
        "_append_filter_from_profile_discriminated_elem",
        profile_filter,
    )


@pytest.mark.parametrize(
    "discriminator_types",
    PAIRWISE_DISCRIMINATOR_CASES,
)
def test_filter_for_slice_combines_all_pairwise_discriminator_types(
    discriminator_filter_stubs, monkeypatch, discriminator_types
):
    monkeypatch.setattr(
        functions,
        "get_parent_element",
        lambda *_: _parent_with_discriminators(discriminator_types),
    )

    actual = functions.filter_for_slice(
        "component",
        _slice_elem(),
        snapshot=object(),
        manager=object(),
    )

    assert actual == _expected_filter(discriminator_types)


def test_filter_for_slice_combines_more_than_two_discriminators(
    discriminator_filter_stubs, monkeypatch
):
    discriminator_types = ("value", "exists", "type", "profile")
    monkeypatch.setattr(
        functions,
        "get_parent_element",
        lambda *_: _parent_with_discriminators(discriminator_types),
    )

    actual = functions.filter_for_slice(
        "component",
        _slice_elem(),
        snapshot=object(),
        manager=object(),
    )

    assert actual == _expected_filter(discriminator_types)


def test_filter_for_slice_combines_multi_type_discriminator(monkeypatch):
    discriminator_types = ("type", "exists")
    monkeypatch.setattr(
        functions,
        "get_parent_element",
        lambda *_: _parent_with_discriminators(discriminator_types),
    )

    actual = functions.filter_for_slice(
        "component",
        _slice_elem(["Quantity", "CodeableConcept"]),
        snapshot=object(),
        manager=object(),
    )

    expected = (
        "component.where(value.exists($this is Quantity or $this is CodeableConcept) "
        "and identifier.exists())"
    )
    assert actual == expected


def test_filter_for_observation_component_with_single_type_discriminator(monkeypatch):
    parent = _parent(
        "Observation.component",
        [_discriminator_with_path("type", "$this.value")],
    )
    monkeypatch.setattr(functions, "get_parent_element", lambda *_: parent)

    actual = functions.filter_for_slice(
        "component",
        _slice_elem(
            ["Quantity"],
            element_id="Observation.component:systolic",
            path="Observation.component",
        ),
        snapshot=object(),
        manager=object(),
    )

    assert actual == "component.value.ofType(Quantity)"


def test_filter_for_observation_component_with_single_code_pattern_discriminator(
    monkeypatch,
):
    parent = _parent(
        "Observation.component",
        [_discriminator_with_path("pattern", "code")],
    )
    monkeypatch.setattr(functions, "get_parent_element", lambda *_: parent)
    monkeypatch.setattr(
        functions,
        "_get_filter_from_pattern_or_value_discriminated_elem",
        lambda *_: "where(code.coding.exists(system = 'loinc' and code = '85354-9'))",
    )

    actual = functions.filter_for_slice(
        "component",
        _slice_elem(
            ["BackboneElement"],
            element_id="Observation.component",
            path="Observation.component",
        ),
        snapshot=object(),
        manager=object(),
    )

    expected = (
        "component.where(code.coding.exists(system = 'loinc' and code = '85354-9'))"
    )
    assert actual == expected


def test_filter_for_observation_component_combines_code_and_type_discriminators(
    monkeypatch,
):
    parent = _parent(
        "Observation.component",
        [
            _discriminator_with_path("pattern", "code"),
            _discriminator_with_path("type", "$this.value"),
        ],
    )
    monkeypatch.setattr(functions, "get_parent_element", lambda *_: parent)
    monkeypatch.setattr(
        functions,
        "_get_filter_from_pattern_or_value_discriminated_elem",
        lambda *_: "where(code.coding.exists(system = 'loinc' and code = '8480-6'))",
    )

    actual = functions.filter_for_slice(
        "component",
        _slice_elem(
            ["Quantity"],
            element_id="Observation.component:systolic",
            path="Observation.component",
        ),
        snapshot=object(),
        manager=object(),
    )

    expected = (
        "component.where(code.coding.exists(system = 'loinc' and code = '8480-6') "
        "and value.exists($this is Quantity))"
    )
    assert actual == expected


def test_filter_for_encounter_location_combines_physical_type_and_status_patterns(
    monkeypatch,
):
    parent = _parent(
        "Encounter.location",
        [
            _discriminator_with_path("pattern", "physicalType"),
            _discriminator_with_path("pattern", "status"),
        ],
    )
    monkeypatch.setattr(functions, "get_parent_element", lambda *_: parent)

    def pattern_filter(_slice_elem_def, discr_path, *_):
        return {
            "physicalType": "where(physicalType.coding.exists(system = 'http://terminology.hl7.org/CodeSystem/location-physical-type' and code = 'ro'))",
            "status": "where(status = 'active')",
        }[discr_path]

    monkeypatch.setattr(
        functions,
        "_get_filter_from_pattern_or_value_discriminated_elem",
        pattern_filter,
    )

    actual = functions.filter_for_slice(
        "location",
        _slice_elem(
            ["BackboneElement"],
            element_id="Encounter.location",
            path="Encounter.location",
        ),
        snapshot=object(),
        manager=object(),
    )

    expected = (
        "location.where(physicalType.coding.exists(system = "
        "'http://terminology.hl7.org/CodeSystem/location-physical-type' "
        "and code = 'ro') and status = 'active')"
    )
    assert actual == expected


@pytest.mark.parametrize(
    "elem, elem_name, expected",
    [
        (ParametersParameter(name="test1", valueCode="abc"), "value", "abc"),
        (ParametersParameter(name="test2", valueUri="abc"), "value", "abc"),
        (Coding(system="http://code-system.org", code="abc"), "value", None),
    ],
)
def test__find_polymorphic_value(elem: Element, elem_name: str, expected):
    value = _find_polymorphic_value(elem, elem_name)
    assert expected == value


@pytest.mark.parametrize(
    "elem_def, expected",
    [
        (ElementDefinition(path="a.b.c", fixedCode="abc"), ("fixed", "abc")),
        (ElementDefinition(path="a.b.c", patternCode="abc"), ("pattern", "abc")),
        (
            ElementDefinition(
                path="a.b.c", binding=ElementDefinitionBinding(strength="required")
            ),
            ("binding", ElementDefinitionBinding(strength="required")),
        ),
        (ElementDefinition(path="a.b.c"), None),
    ],
)
def test__find_value_for_discriminator_pattern_or_value(elem_def, expected):
    value = _find_value_for_discriminator_pattern_or_value(elem_def)
    assert expected == value


@pytest.mark.parametrize(
    "key, data, expected",
    [
        ("$this", "abc", ["$this = 'abc'"]),
        ("element", "abc", ["element = 'abc'"]),
        ("$this", [], []),
        (
            "$this",
            ["a"],
            ["$this = 'a'"],
        ),
        (
            "$this",
            ["a", "b", "c"],
            ["exists($this = 'a') and exists($this = 'b') and exists($this = 'c')"],
        ),
        ("$this", {}, []),
        (
            "$this",
            {"a": "1"},
            ["a = '1'"],
        ),
        (
            "element",
            {"a": "1"},
            ["element.exists(a = '1')"],
        ),
        (
            "$this",
            {"a": "1", "b": "2", "c": "3"},
            ["a = '1' and b = '2' and c = '3'"],
        ),
        (
            "element",
            {"a": "1", "b": "2", "c": "3"},
            ["element.exists(a = '1' and b = '2' and c = '3')"],
        ),
        (
            "element",
            {"coding": [{"system": "http://codesystem.org", "code": "abc"}]},
            [
                "element.coding.exists(system = 'http://codesystem.org' and code = 'abc')"
            ],
        ),
    ],
)
def test__element_data_to_fhirpath_filter(key: str, data: Any, expected: List[str]):
    value = _element_data_to_fhirpath_filter(key, data)
    assert expected == value


@pytest.mark.parametrize(
    "key, data, expected",
    [
        ("$this", "abc", "where($this = 'abc')"),
        ("element", "abc", "where(element = 'abc')"),
        (
            "$this",
            ["a"],
            "where($this = 'a')",
        ),
        (
            "$this",
            ["a", "b", "c"],
            "where(exists($this = 'a') and exists($this = 'b') and exists($this = 'c'))",
        ),
        (
            "$this",
            {"a": "1"},
            "where(a = '1')",
        ),
        (
            "element",
            {"a": "1"},
            "where(element.exists(a = '1'))",
        ),
        (
            "$this",
            {"a": "1", "b": "2", "c": "3"},
            "where(a = '1' and b = '2' and c = '3')",
        ),
        (
            "element",
            {"a": "1", "b": "2", "c": "3"},
            "where(element.exists(a = '1' and b = '2' and c = '3'))",
        ),
        (
            "element",
            {"coding": [{"system": "http://codesystem.org", "code": "abc"}]},
            "where(element.coding.exists(system = 'http://codesystem.org' and code = 'abc'))",
        ),
    ],
)
def test__element_to_fhirpath_filter(key: str, data: Any, expected: str):
    value = _element_to_fhirpath_filter(key, data)
    assert value == expected


def test__append_filter_from_profile_discriminated_elem(
    base_expr: str,
    elem_def: ElementDefinition,
    discr: ElementDefinitionSlicingDiscriminator,
    snapshot: StructureDefinitionSnapshot,
    manager: FhirPackageManager,
    expected,
):
    value = _append_filter_from_profile_discriminated_elem(
        base_expr, elem_def, discr, snapshot, manager
    )
    assert value == expected


def test__get_filter_from_pattern_or_value_discriminated_elem(
    elem_def: ElementDefinition,
    discr_path: str,
    snapshot: StructureDefinitionSnapshot,
    expected: str,
    package_manager: FhirPackageManager,
):
    value = _get_filter_from_pattern_or_value_discriminated_elem(
        elem_def, discr_path, snapshot, package_manager
    )
    assert value == expected


@pytest.mark.parametrize(
    argnames="base_expr, elem_def, profile, expected",
    argvalues=[
        (
            "Specimen.processing",
            "Specimen.processing:lagerprozess",
            "https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Specimen",
            "Specimen.processing.where(procedure.coding.exists(system = 'http://snomed.info/sct' and code = '1186936003'))",
        ),
        (
            "Specimen.collection.fastingStatus",
            "Specimen.collection.fastingStatus[x]:fastingStatusCodeableConcept",
            "https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Specimen",
            "Specimen.collection.fastingStatus.ofType(CodeableConcept)",
        ),
        (
            "Specimen.collection.extension",
            "Specimen.collection.extension:einstellungBlutversorgung",
            "https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Specimen",
            "Specimen.collection.extension('https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/EinstellungBlutversorgung')",
        ),
        (
            "Observation.effective",
            "Observation.effective[x]:effectiveDateTime",
            "https://www.medizininformatik-initiative.de/fhir/ext/modul-icu/StructureDefinition/kopfumfang",
            "Observation.effective.where($this is dateTime or $this is Period)",
        ),
        (
            "Composition.section",
            "Composition.section:diagRep",
            "https://www.medizininformatik-initiative.de/fhir/ext/modul-bildgebung/StructureDefinition/mii-pr-bildgebung-semistrukt-befundbericht",
            "Composition.section.where(entry.resolve().meta.profile.exists($this = 'https://www.medizininformatik-initiative.de/fhir/ext/modul-bildgebung/StructureDefinition/mii-pr-bildgebung-radiologischer-befund'))",
        ),
    ],
    ids=[
        "pattern_slicing_with_pattern_in_subelement",
        "type_slicing",
        "profile_slicing_with_single_profile",
        # "profile_slicing_with_multiple_profiles"  # We have no such example in the package cache ATM
        "type_slicing_with_multiple_types",
        "profile_slicing",
    ],
    indirect=["elem_def", "profile"],
)
def test__append_filter_for_slice(
    base_expr: str,
    elem_def: ElementDefinition,
    profile: StructureDefinitionSnapshot,
    expected: str,
    package_manager: FhirPackageManager,
):
    value = filter_for_slice(base_expr, elem_def, profile, package_manager)
    assert value == expected
