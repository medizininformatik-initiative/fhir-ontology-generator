from datetime import date, datetime
from decimal import Decimal

import pytest
from dataportal_generator.common.fhir.pattern import matches_pattern
from fhir.resources.R4B.codeableconcept import CodeableConcept
from fhir.resources.R4B.coding import Coding
from fhir.resources.R4B.identifier import Identifier
from fhir.resources.R4B.quantity import Quantity

CODING_LOINC = Coding(system="http://loinc.org", code="1234-5", display="Test")
CODING_SNOMED = Coding(system="http://snomed.info/sct", code="987654")

CODEABLE_CONCEPT = CodeableConcept(
    coding=[CODING_LOINC, CODING_SNOMED], text="Some text"
)


# --- Primitives -------------------------------------------------------------


@pytest.mark.parametrize(
    argnames=["data", "pattern", "expected"],
    argvalues=[
        pytest.param("abc", "abc", True, id="string-equal"),
        pytest.param("abc", "def", False, id="string-not-equal"),
        pytest.param(5, 5, True, id="int-equal"),
        pytest.param(5, 6, False, id="int-not-equal"),
        pytest.param(True, True, True, id="bool-equal"),
        pytest.param(True, False, False, id="bool-not-equal"),
        pytest.param(1.5, 1.5, True, id="float-equal"),
        pytest.param(None, None, True, id="none-equal"),
        pytest.param("5", 5, False, id="string-vs-int-not-equal"),
    ],
)
def test_matches_pattern_primitives(data, pattern, expected):
    assert matches_pattern(data, pattern) == expected


@pytest.mark.parametrize(
    argnames=["data", "pattern", "expected"],
    argvalues=[
        pytest.param(Decimal("1.50"), 1.5, True, id="decimal-matches-equal-float"),
        pytest.param(
            date(2024, 1, 1), "2024-01-01", True, id="date-matches-iso-string"
        ),
        pytest.param(
            datetime(2024, 1, 1, 12, 30),
            "2024-01-01T12:30:00",
            True,
            id="datetime-matches-iso-string",
        ),
        pytest.param(
            date(2024, 1, 1), "2024-01-02", False, id="date-mismatch"
        ),
    ],
)
def test_matches_pattern_normalizes_non_json_native_primitives(data, pattern, expected):
    assert matches_pattern(data, pattern) == expected


# --- Complex objects (dicts / FHIR `Element` instances) --------------------


def test_matches_pattern_dict_against_dict_subset():
    data = {"system": "http://loinc.org", "code": "1234-5", "display": "Test"}
    assert matches_pattern(data, {"system": "http://loinc.org"})
    assert matches_pattern(data, {"system": "http://loinc.org", "code": "1234-5"})


def test_matches_pattern_dict_missing_key_does_not_match():
    data = {"system": "http://loinc.org"}
    assert not matches_pattern(data, {"system": "http://loinc.org", "code": "1234-5"})


def test_matches_pattern_dict_wrong_value_does_not_match():
    data = {"system": "http://loinc.org", "code": "1234-5"}
    assert not matches_pattern(data, {"code": "abc"})


def test_matches_pattern_empty_pattern_matches_any_object():
    assert matches_pattern({"system": "http://loinc.org"}, {})


def test_matches_pattern_empty_pattern_does_not_match_non_object():
    assert not matches_pattern("abc", {})


def test_matches_pattern_fhir_element_instance():
    assert matches_pattern(CODING_LOINC, {"system": "http://loinc.org"})
    assert matches_pattern(
        CODING_LOINC, {"system": "http://loinc.org", "code": "1234-5"}
    )
    assert not matches_pattern(CODING_LOINC, {"system": "http://snomed.info/sct"})


def test_matches_pattern_fhir_element_instance_ignores_unset_fields():
    # `display` is set on the instance but not required by the pattern, and other unset fields (e.g. `version`,
    # `userSelected`) must not be required either since they were never serialized in the first place
    assert matches_pattern(CODING_LOINC, {"code": "1234-5"})


def test_matches_pattern_nested_complex_object():
    quantity = Quantity(value=5.0, unit="mg", system="http://unitsofmeasure.org", code="mg")
    assert matches_pattern(quantity, {"unit": "mg", "code": "mg"})
    assert not matches_pattern(quantity, {"unit": "g"})


# --- Arrays ------------------------------------------------------------------


def test_matches_pattern_array_element_must_match_at_least_one_instance_element():
    assert matches_pattern(
        CODEABLE_CONCEPT, {"coding": [{"system": "http://loinc.org", "code": "1234-5"}]}
    )


def test_matches_pattern_array_pattern_with_multiple_elements_matched_independently():
    assert matches_pattern(
        CODEABLE_CONCEPT,
        {
            "coding": [
                {"system": "http://loinc.org"},
                {"system": "http://snomed.info/sct"},
            ]
        },
    )


def test_matches_pattern_array_pattern_element_without_any_matching_instance_element():
    assert not matches_pattern(
        CODEABLE_CONCEPT, {"coding": [{"system": "http://example.org/unknown"}]}
    )


def test_matches_pattern_array_extra_instance_elements_are_allowed():
    # The instance's `coding` array contains an entry (SNOMED) not mentioned in the pattern -- that's fine, patterns
    # only require presence, not exclusivity
    assert matches_pattern(CODEABLE_CONCEPT, {"coding": [{"system": "http://loinc.org"}]})


def test_matches_pattern_array_pattern_against_non_array_instance_does_not_match():
    assert not matches_pattern({"coding": "not-a-list"}, {"coding": [{"system": "x"}]})


def test_matches_pattern_array_pattern_against_missing_instance_array_does_not_match():
    assert not matches_pattern({}, {"coding": [{"system": "x"}]})


# --- Repeating elements (top-level list of instances) ------------------------


def test_matches_pattern_repeating_element_all_instances_must_match():
    identifiers = [
        Identifier(system="http://example.org/mrn", value="123"),
        Identifier(system="http://example.org/mrn", value="456"),
    ]
    assert matches_pattern(identifiers, {"system": "http://example.org/mrn"})


def test_matches_pattern_repeating_element_single_mismatch_fails_whole_match():
    identifiers = [
        Identifier(system="http://example.org/mrn", value="123"),
        Identifier(system="http://example.org/other", value="456"),
    ]
    assert not matches_pattern(identifiers, {"system": "http://example.org/mrn"})


def test_matches_pattern_empty_repeating_element_vacuously_matches():
    assert matches_pattern([], {"system": "http://example.org/mrn"})


def test_matches_pattern_repeating_element_of_dicts():
    data = [
        {"system": "http://example.org/mrn", "value": "123"},
        {"system": "http://example.org/mrn", "value": "456"},
    ]
    assert matches_pattern(data, {"system": "http://example.org/mrn"})
    assert not matches_pattern(data, {"value": "123"})


# --- Top-level list / primitive patterns --------------------------------------
# `pattern[x]` need not be a `dict` -- it can equally be a bare array-valued sub value (e.g. the `coding` array of a
# `CodeableConcept` extracted on its own) or a primitive value (e.g. `patternCode`/`patternString`)


def test_matches_pattern_top_level_list_pattern_against_list_instance():
    assert matches_pattern(["a", "b", "c"], ["a", "b"])
    assert matches_pattern(["a", "b", "c"], ["a"])


def test_matches_pattern_top_level_list_pattern_element_without_match_fails():
    assert not matches_pattern(["a", "b", "c"], ["a", "d"])


def test_matches_pattern_top_level_list_pattern_against_non_list_instance_fails():
    assert not matches_pattern("a", ["a"])


def test_matches_pattern_top_level_list_pattern_of_complex_objects():
    data = [
        {"system": "http://loinc.org", "code": "1234-5"},
        {"system": "http://snomed.info/sct", "code": "987654"},
    ]
    assert matches_pattern(data, [{"system": "http://loinc.org"}])
    assert matches_pattern(
        data, [{"system": "http://loinc.org"}, {"system": "http://snomed.info/sct"}]
    )
    assert not matches_pattern(data, [{"system": "http://example.org/unknown"}])


def test_matches_pattern_top_level_primitive_pattern_against_fhir_element():
    # `data` here stands in for an already-navigated primitive-typed FHIR element (e.g. `Coding.code`)
    assert matches_pattern(CODING_LOINC.code, "1234-5")
    assert not matches_pattern(CODING_LOINC.code, "other-code")


def test_matches_pattern_top_level_primitive_pattern_applies_to_all_repetitions():
    assert matches_pattern(["abc", "abc"], "abc")
    assert not matches_pattern(["abc", "def"], "abc")
