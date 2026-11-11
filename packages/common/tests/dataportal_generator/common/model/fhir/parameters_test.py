import pytest

from dataportal_generator.common.model.fhir.parameters import (
    KeyedParameters,
    KeyedParametersParameter,
)


@pytest.fixture
def params() -> KeyedParameters:
    return KeyedParameters.model_validate(
        {
            "resourceType": "Parameters",
            "parameter": [
                {"name": "result", "valueBoolean": True},
                {"name": "display", "valueString": "Foo"},
                {"name": "designation", "valueString": "A"},
                {"name": "designation", "valueString": "B"},
                {
                    "name": "match",
                    "part": [
                        {"name": "equivalence", "valueCode": "equal"},
                        {"name": "concept", "valueCoding": {"code": "1"}},
                    ],
                },
                {
                    "name": "match",
                    "part": [{"name": "concept", "valueCoding": {"code": "2"}}],
                },
                {"name": "empty"},
                {"name": "used-codesystem", "valueUri": "http://loinc.org"},
            ],
        }
    )


def test_getitem(params: KeyedParameters):
    assert [p.valueString for p in params["designation"]] == ["A", "B"]
    assert len(params["match", "concept"]) == 2
    with pytest.raises(KeyError):
        _ = params["missing"]
    with pytest.raises(KeyError):
        _ = params["match", "missing"]


def test_contains(params: KeyedParameters):
    assert "display" in params
    assert ("match", "equivalence") in params
    assert "missing" not in params
    assert 42 not in params


def test_keys(params: KeyedParameters):
    assert params.keys() == [
        "result",
        "display",
        "designation",
        "match",
        "empty",
        "used-codesystem",
    ]


def test_get(params: KeyedParameters):
    assert params.get("designation").valueString == "A"
    assert params.get("missing") is None


def test_get_value(params: KeyedParameters):
    assert params.get_value("result") is True
    assert params.get_value("display") == "Foo"
    assert params.get_value(("match", "concept")).code == "1"
    assert params.get_value("empty", "default") == "default"
    assert params.get_value("missing") is None


def test_get_values(params: KeyedParameters):
    assert params.get_values("designation") == ["A", "B"]
    assert [c.code for c in params.get_values(("match", "concept"))] == ["1", "2"]
    assert params.get_values("empty") == []


def test_empty_parameters():
    params = KeyedParameters()
    assert params.keys() == []
    assert params.get_all("anything") == []
    assert "anything" not in params


def test_serialization_unchanged(params: KeyedParameters):
    assert params.model_dump()["resourceType"] == "Parameters"


def test_nested_models_are_keyed(params: KeyedParameters):
    assert all(isinstance(p, KeyedParametersParameter) for p in params.parameter)
    assert all(
        isinstance(p, KeyedParametersParameter)
        for p in params.get_all(("match", "concept"))
    )


def test_property_access(params: KeyedParameters):
    assert [p.value for p in params.designation] == ["A", "B"]
    assert params.display[0].value == "Foo"
    assert params.match[0].concept[0].value.code == "1"
    assert params.match[0].equivalence[0].value == "equal"
    assert params.used_codesystem[0].value == "http://loinc.org"
    with pytest.raises(AttributeError):
        _ = params.missing
    with pytest.raises(AttributeError):
        _ = params.match[1].equivalence


def test_property_access_prefers_model_fields(params: KeyedParameters):
    assert params.id is None
    assert params.match[0].name == "match"
    assert params.empty[0].value is None


def test_part_key_access(params: KeyedParameters):
    match = params.get("match")
    assert match.keys() == ["equivalence", "concept"]
    assert match.get_value("concept").code == "1"
    assert "concept" in match


def test_round_trip(params: KeyedParameters):
    assert KeyedParameters.model_validate_json(params.model_dump_json()) == params
