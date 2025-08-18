from typing import Any, List, Optional

import fhir.resources.R4B.structuredefinition
import pytest
from fhir.resources.R4B.codeableconcept import CodeableConcept
from fhir.resources.R4B.coding import Coding
from fhir.resources.R4B.element import Element
from fhir.resources.R4B.elementdefinition import (
    ElementDefinition,
    ElementDefinitionBinding,
    ElementDefinitionSlicingDiscriminator,
)
from fhir.resources.R4B.expression import Expression
from fhir.resources.R4B.elementdefinition import ElementDefinitionType
from fhir.resources.R4B.extension import Extension
from fhir.resources.R4B.measure import (
    MeasureGroupStratifier,
    MeasureGroup,
    MeasureGroupPopulation,
    Measure,
)
from fhir.resources.R4B.parameters import ParametersParameter
from fhir.resources.R4B.structuredefinition import StructureDefinition

from availability.core.element_availability import (
    _find_polymorphic_value,
    _find_value_for_discriminator_pattern_or_value,
    _element_to_fhirpath_filter,
    _element_data_to_fhirpath_filter,
    _append_filter_from_profile_discriminated_elem,
    _append_filter_for_slice,
    _get_filter_from_pattern_or_value_discriminated_elem,
    _generate_stratifier,
    _get_full_element_id,
    _resolve_polymorphism_in_expr,
    _generate_stratifier_for_reference,
    _generate_stratifiers_for_extension_elements,
    _generate_stratifiers_for_typed_elem,
    _resolve_supported_types,
    _generate_stratifiers_for_elem_def,
    _generate_measure_group_for_profile,
    update_stratifier_ids,
    _add_data_absent_reason_clause,
    _ensure_trailing_existence_check,
    generate_measure,
)
from common.model.fhir.structure_definition import StructureDefinitionSnapshot
from common.util.fhir.package.manager import FhirPackageManager
from common.util.fhirpath import parse_expr, fhirpathParser


def test__add_data_absent_reason_clause():
    expr_str = "where(a = 1 and b = 2)"
    param_list: fhirpathParser.ParamListContext = (
        parse_expr(expr_str)
        .getChild(0)
        .getChild(0)
        .getChild(0)
        .function()
        .paramList()
        .getChild(0)
    )
    result = _add_data_absent_reason_clause(param_list)
    assert (
        "a = 1 and b = 2 and extension('http://hl7.org/fhir/StructureDefinition/data-absent-reason').empty()"
        == result
    )

    expr_str = "where(a = 1 or b = 2)"
    param_list: fhirpathParser.ParamListContext = (
        parse_expr(expr_str)
        .getChild(0)
        .getChild(0)
        .getChild(0)
        .function()
        .paramList()
        .getChild(0)
    )
    result = _add_data_absent_reason_clause(param_list)
    assert (
        "(a = 1 or b = 2) and extension('http://hl7.org/fhir/StructureDefinition/data-absent-reason').empty()"
        == result
    )

    result = _add_data_absent_reason_clause()
    assert (
        "extension('http://hl7.org/fhir/StructureDefinition/data-absent-reason').empty()"
        == result
    )


@pytest.mark.parametrize(
    "expr_str, is_primitive, expected",
    [
        ("Resource.element1.hasValue()", True, "Resource.element1.hasValue()"),
        (
            "Resource.element1.hasValue()",
            False,
            "Resource.element1.exists(extension('http://hl7.org/fhir/StructureDefinition/data-absent-reason').empty())",
        ),
        ("Resource.element1.exists()", True, "Resource.element1.hasValue()"),
        (
            "Resource.element1.exists()",
            False,
            "Resource.element1.exists(extension('http://hl7.org/fhir/StructureDefinition/data-absent-reason').empty())",
        ),
        (
            "Resource.element1.exists(a = 1)",
            True,
            "Resource.element1.exists(a = 1 and extension('http://hl7.org/fhir/StructureDefinition/data-absent-reason').empty())",
        ),
        (
            "Resource.element1.exists(a = 1)",
            False,
            "Resource.element1.exists(a = 1 and extension('http://hl7.org/fhir/StructureDefinition/data-absent-reason').empty())",
        ),
        (
            "Resource.element1.where(a = 1)",
            True,
            "Resource.element1.where(a = 1).hasValue()",
        ),
        (
            "Resource.element1.where(a = 1)",
            False,
            "Resource.element1.exists(a = 1 and extension('http://hl7.org/fhir/StructureDefinition/data-absent-reason').empty())",
        ),
        (
            "Resource.element1",
            True,
            "Resource.element1.hasValue()",
        ),
        (
            "Resource.element1",
            False,
            "Resource.element1.exists(extension('http://hl7.org/fhir/StructureDefinition/data-absent-reason').empty())",
        ),
    ],
    ids=[
        "hasValue_and_is_primitive",
        "hasValue_without_params_and_is_complex",
        "exists_without_param_and_is_primitive",
        "exists_without_param_and_is_complex",
        "exists_with_param_and_is_primitive",
        "exists_with_param_and_is_complex",
        "where_and_is_primitive",
        "where_and_is_complex",
        "other_and_is_primitive",
        "other_and_is_complex",
    ],
)
def test__ensure_trailing_existence_check(
    expr_str: str, is_primitive: bool, expected: str
):
    value = _ensure_trailing_existence_check(expr_str, is_primitive)
    assert value == expected


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
):
    value = _get_filter_from_pattern_or_value_discriminated_elem(
        elem_def, discr_path, snapshot
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
    value = _append_filter_for_slice(base_expr, elem_def, profile, package_manager)
    assert value == expected


@pytest.mark.parametrize(
    "expr, field_name, expected",
    [
        (
            "Resource.element1.where(element2 = 'abc').element3.exists()",
            "Resource.element1.element3",
            {
                "criteria": {
                    "language": "text/fhirpath",
                    "expression": "Resource.element1.where(element2 = 'abc').element3.exists()",
                },
                "code": {
                    "coding": [
                        {
                            "system": "http://fhir-data-evaluator/strat/system",
                            "code": "Resource.element1.element3",
                        }
                    ]
                },
            },
        ),
        (
            "Resource.element1.exists()",
            "Resource.element1",
            {
                "criteria": {
                    "language": "text/fhirpath",
                    "expression": "Resource.element1.exists()",
                },
                "code": {
                    "coding": [
                        {
                            "system": "http://fhir-data-evaluator/strat/system",
                            "code": "Resource.element1",
                        }
                    ]
                },
            },
        ),
        (
            "Resource.element1.exists(element2 = 'abc')",
            "Resource.element1",
            {
                "criteria": {
                    "language": "text/fhirpath",
                    "expression": "Resource.element1.exists(element2 = 'abc')",
                },
                "code": {
                    "coding": [
                        {
                            "system": "http://fhir-data-evaluator/strat/system",
                            "code": "Resource.element1",
                        }
                    ]
                },
            },
        ),
    ],
)
def test__generate_stratifier(expr: str, field_name: str, expected: str):
    value = _generate_stratifier(expr, field_name)
    assert value == MeasureGroupStratifier.model_validate(expected)


@pytest.mark.parametrize(
    "chained_elem_id, type_code, expected",
    [
        (["Resource.element1.element2"], None, "Resource.element1.element2"),
        (["Resource.element1.element2[x]"], None, "Resource.element1.element2[x]"),
        (
            ["Resource.element1.element2[x]"],
            "dataType",
            "Resource.element1.element2DataType",
        ),
        (
            ["Resource.element1.element3:slice1"],
            None,
            "Resource.element1.element3:slice1",
        ),
        (
            [
                "Resource1.element1.extension",
                "Extension.value[x]",
                "Resource2.element1:slice1",
            ],
            None,
            "Resource1.element1.extension.value[x].element1:slice1",
        ),
    ],
)
def test__field_name_from_element_id(
    chained_elem_id: List[str], type_code: Optional[str], expected: str
):
    value = _get_full_element_id(chained_elem_id, type_code)
    assert value == expected


@pytest.mark.parametrize(
    "expr, fhir_type, expected",
    [
        ("Resource.element1[x]", "DataType", "Resource.element1.ofType(DataType)"),
        ("Resource.element1[x]", None, "Resource.element1"),
    ],
)
def test__resolve_polymorphism_in_expr(
    expr: str, fhir_type: Optional[str], expected: str
):
    value = _resolve_polymorphism_in_expr(expr, fhir_type)
    assert value == expected


@pytest.mark.parametrize(
    argnames="profile, base_expr, chained_elem_id, expected",
    argvalues=[
        (
            StructureDefinition(
                url="http://organization.org/fhir/StructureDefinition/profile1",
                name="profile1",
                status="active",
                kind="resource",
                abstract=False,
                type="Condition",
            ),
            "Resource.element1",
            ["Resource.element1"],
            [
                MeasureGroupStratifier(
                    criteria=Expression(
                        language="text/fhirpath",
                        expression="Resource.element1.resolve().ofType(Condition).meta.profile contains 'http://organization.org/fhir/StructureDefinition/profile1'",
                    ),
                    code=CodeableConcept(
                        coding=[
                            Coding(
                                system="http://fhir-data-evaluator/strat/system",
                                code="Resource.element1->Condition",
                            )
                        ]
                    ),
                ),
            ],
        ),
        (
            "http://hl7.org/fhir/StructureDefinition/Condition",
            "Specimen.extension('https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Diagnose').value.ofType(Reference)",
            ["Specimen.extension:festgestellteDiagnose", "Extension.value[x]"],
            [
                MeasureGroupStratifier(
                    criteria=Expression(
                        language="text/fhirpath",
                        expression="Specimen.extension('https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Diagnose').value.ofType(Reference).resolve().ofType(Condition).meta.profile.exists($this = 'http://hl7.org/fhir/StructureDefinition/Condition' or $this = 'https://www.medizininformatik-initiative.de/fhir/core/modul-diagnose/StructureDefinition/Diagnose' or $this = 'https://www.medizininformatik-initiative.de/fhir/core/modul-person/StructureDefinition/Todesursache' or $this = 'https://www.medizininformatik-initiative.de/fhir/ext/modul-patho/StructureDefinition/mii-pr-patho-problem-list-item')",
                    ),
                    code=CodeableConcept(
                        coding=[
                            Coding(
                                system="http://fhir-data-evaluator/strat/system",
                                code="Specimen.extension:festgestellteDiagnose.valueReference->Condition",
                            )
                        ]
                    ),
                ),
            ],
        ),
    ],
    ids=[
        "reference-without-descendants-in-scope",
        "reference-with-descendants-in-scope",
    ],
    indirect=["profile"],
)
def test__generate_stratifier_for_reference(
    profile: StructureDefinition,
    base_expr: str,
    chained_elem_id: List[str],
    expected,
    package_manager: FhirPackageManager,
):
    value = _generate_stratifier_for_reference(
        profile, base_expr, chained_elem_id, package_manager
    )
    assert value == expected


@pytest.mark.parametrize(
    argnames="profile, base_expr, chained_elem_id, expected",
    argvalues=[
        (
            "https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/EinstellungBlutversorgung",
            "Specimen.collection.extension('https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/EinstellungBlutversorgung')",
            ["Specimen.collection.extension:einstellungBlutversorgung"],
            [
                MeasureGroupStratifier(
                    criteria=Expression(
                        language="text/fhirpath",
                        expression="Specimen.collection.extension('https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/EinstellungBlutversorgung').value.ofType(dateTime).hasValue()",
                    ),
                    code=CodeableConcept(
                        coding=[
                            Coding(
                                system="http://fhir-data-evaluator/strat/system",
                                code="Specimen.collection.extension:einstellungBlutversorgung.value[x]",
                            )
                        ]
                    ),
                ),
            ],
        ),
        (
            "https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Diagnose",
            "Specimen.extension('https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Diagnose')",
            ["Specimen.extension:festgestellteDiagnose"],
            [
                MeasureGroupStratifier(
                    criteria=Expression(
                        language="text/fhirpath",
                        expression="Specimen.extension('https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Diagnose').value.ofType(Reference).reference.hasValue()",
                    ),
                    code=CodeableConcept(
                        coding=[
                            Coding(
                                system="http://fhir-data-evaluator/strat/system",
                                code="Specimen.extension:festgestellteDiagnose.value[x]",
                            )
                        ]
                    ),
                ),
            ],
        ),
    ],
    ids=[
        "extension-with-valueDateTime",
        "extension-with-valueReference",
    ],
    indirect=["profile"],
)
def test__generate_stratifiers_for_extension_elements(
    profile: StructureDefinitionSnapshot,
    base_expr: str,
    chained_elem_id,
    expected: List[MeasureGroupStratifier],
    package_manager: FhirPackageManager,
):
    values = _generate_stratifiers_for_extension_elements(
        profile, base_expr, package_manager, chained_elem_id
    )
    assert values == expected


@pytest.mark.parametrize(
    argnames="elem_type, parent_expr, parent_elem_id, chained_elem_id, expected",
    argvalues=[
        pytest.param(
            ElementDefinitionType(
                code="Extension",
                profile=[
                    "https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Diagnose"
                ],
            ),
            "Specimen.extension('https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Diagnose')",
            "Specimen.extension:festgestellteDiagnose",
            ["Specimen.extension:festgestellteDiagnose"],
            [
                MeasureGroupStratifier(
                    criteria=Expression(
                        language="text/fhirpath",
                        expression="Specimen.extension('https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Diagnose').exists(extension('http://hl7.org/fhir/StructureDefinition/data-absent-reason').empty())",
                    ),
                    code=CodeableConcept(
                        coding=[
                            Coding(
                                system="http://fhir-data-evaluator/strat/system",
                                code="Specimen.extension:festgestellteDiagnose",
                            )
                        ]
                    ),
                ),
                MeasureGroupStratifier(
                    criteria=Expression(
                        language="text/fhirpath",
                        expression="Specimen.extension('https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Diagnose').value.ofType(Reference).reference.hasValue()",
                    ),
                    code=CodeableConcept(
                        coding=[
                            Coding(
                                system="http://fhir-data-evaluator/strat/system",
                                code="Specimen.extension:festgestellteDiagnose.value[x]",
                            )
                        ]
                    ),
                ),
            ],
        ),
        (
            ElementDefinitionType(
                code="Extension",
                profile=["http://fhir.de/StructureDefinition/Aufnahmegrund"],
            ),
            "Encounter.extension('http://fhir.de/StructureDefinition/Aufnahmegrund')",
            "Encounter.extension:Aufnahmegrund",
            ["Encounter.extension:Aufnahmegrund"],
            [
                MeasureGroupStratifier(
                    code=CodeableConcept(
                        coding=[
                            Coding(
                                code="Encounter.extension:Aufnahmegrund",
                                system="http://fhir-data-evaluator/strat/system",
                            )
                        ],
                    ),
                    criteria=Expression(
                        expression="Encounter.extension('http://fhir.de/StructureDefinition/Aufnahmegrund').exists(extension('http://hl7.org/fhir/StructureDefinition/data-absent-reason').empty())",
                        language="text/fhirpath",
                    ),
                ),
                MeasureGroupStratifier(
                    code=CodeableConcept(
                        coding=[
                            Coding(
                                code="Encounter.extension:Aufnahmegrund.extension:DritteStelle",
                                system="http://fhir-data-evaluator/strat/system",
                            )
                        ],
                    ),
                    criteria=Expression(
                        expression="Encounter.extension('http://fhir.de/StructureDefinition/Aufnahmegrund').extension('DritteStelle').exists(extension('http://hl7.org/fhir/StructureDefinition/data-absent-reason').empty())",
                        language="text/fhirpath",
                    ),
                ),
                MeasureGroupStratifier(
                    code=CodeableConcept(
                        coding=[
                            Coding(
                                code="Encounter.extension:Aufnahmegrund.extension:DritteStelle.value[x]",
                                system="http://fhir-data-evaluator/strat/system",
                            )
                        ],
                    ),
                    criteria=Expression(
                        expression="Encounter.extension('http://fhir.de/StructureDefinition/Aufnahmegrund').extension('DritteStelle').value.ofType(Coding).exists(extension('http://hl7.org/fhir/StructureDefinition/data-absent-reason').empty())",
                        language="text/fhirpath",
                    ),
                ),
                MeasureGroupStratifier(
                    code=CodeableConcept(
                        coding=[
                            Coding(
                                code="Encounter.extension:Aufnahmegrund.extension:ErsteUndZweiteStelle",
                                system="http://fhir-data-evaluator/strat/system",
                            )
                        ],
                    ),
                    criteria=Expression(
                        expression="Encounter.extension('http://fhir.de/StructureDefinition/Aufnahmegrund').extension('ErsteUndZweiteStelle').exists(extension('http://hl7.org/fhir/StructureDefinition/data-absent-reason').empty())",
                        language="text/fhirpath",
                    ),
                ),
                MeasureGroupStratifier(
                    code=CodeableConcept(
                        coding=[
                            Coding(
                                code="Encounter.extension:Aufnahmegrund.extension:ErsteUndZweiteStelle.value[x]",
                                system="http://fhir-data-evaluator/strat/system",
                            )
                        ],
                    ),
                    criteria=Expression(
                        expression="Encounter.extension('http://fhir.de/StructureDefinition/Aufnahmegrund').extension('ErsteUndZweiteStelle').value.ofType(Coding).exists(extension('http://hl7.org/fhir/StructureDefinition/data-absent-reason').empty())",
                        language="text/fhirpath",
                    ),
                ),
                MeasureGroupStratifier(
                    code=CodeableConcept(
                        coding=[
                            Coding(
                                code="Encounter.extension:Aufnahmegrund.extension:VierteStelle",
                                system="http://fhir-data-evaluator/strat/system",
                            )
                        ],
                    ),
                    criteria=Expression(
                        expression="Encounter.extension('http://fhir.de/StructureDefinition/Aufnahmegrund').extension('VierteStelle').exists(extension('http://hl7.org/fhir/StructureDefinition/data-absent-reason').empty())",
                        language="text/fhirpath",
                    ),
                ),
                MeasureGroupStratifier(
                    code=CodeableConcept(
                        coding=[
                            Coding(
                                code="Encounter.extension:Aufnahmegrund.extension:VierteStelle.value[x]",
                                system="http://fhir-data-evaluator/strat/system",
                            )
                        ],
                    ),
                    criteria=Expression(
                        expression="Encounter.extension('http://fhir.de/StructureDefinition/Aufnahmegrund').extension('VierteStelle').value.ofType(Coding).exists(extension('http://hl7.org/fhir/StructureDefinition/data-absent-reason').empty())",
                        language="text/fhirpath",
                    ),
                ),
            ],
        ),
        pytest.param(
            ElementDefinitionType(
                code="Reference",
                targetProfile=[
                    "http://hl7.org/fhir/StructureDefinition/Patient",
                    "http://hl7.org/fhir/StructureDefinition/Group",
                ],
            ),
            "Observation.subject",
            "Observation.subject",
            ["Observation.subject"],
            [
                MeasureGroupStratifier(
                    criteria=Expression(
                        language="text/fhirpath",
                        expression="Observation.subject.reference.hasValue()",
                    ),
                    code=CodeableConcept(
                        coding=[
                            Coding(
                                system="http://fhir-data-evaluator/strat/system",
                                code="Observation.subject",
                            )
                        ]
                    ),
                ),
            ],
        ),
        (
            ElementDefinitionType(code="CodeableConcept"),
            "Observation.value",
            "Observation.value[x]",
            ["Observation.value[x]"],
            [
                MeasureGroupStratifier(
                    criteria=Expression(
                        language="text/fhirpath",
                        expression="Observation.value.ofType(CodeableConcept).exists(extension('http://hl7.org/fhir/StructureDefinition/data-absent-reason').empty())",
                    ),
                    code=CodeableConcept(
                        coding=[
                            Coding(
                                system="http://fhir-data-evaluator/strat/system",
                                code="Observation.value[x]",
                            )
                        ]
                    ),
                )
            ],
        ),
    ],
    ids=[
        "extension_typed_elem_with_external_def",
        "extension_typed_elem_with_internal_def",
        "reference_typed_elem",
        "codeableconcept_typed_elem",
    ],
)
def test__generate_stratifiers_for_typed_elem(
    elem_type: ElementDefinitionType,
    parent_expr: str,
    parent_elem_id: str,
    chained_elem_id: List[str],
    expected: List[MeasureGroupStratifier],
    package_manager: FhirPackageManager,
):
    values = _generate_stratifiers_for_typed_elem(
        elem_type, parent_expr, parent_elem_id, package_manager, chained_elem_id
    )
    assert values == expected


@pytest.mark.parametrize(
    "elem_def, profile, expected",
    [
        (
            "Observation.value[x]",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-labor/StructureDefinition/ObservationLab",
            [
                ElementDefinitionType(code="Quantity"),
                ElementDefinitionType(code="CodeableConcept"),
                ElementDefinitionType(code="Range"),
                ElementDefinitionType(code="Ratio"),
            ],
        ),
        (
            "Observation.component.referenceRange",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-labor/StructureDefinition/ObservationLab",
            [
                ElementDefinitionType(code="BackboneElement"),
            ],
        ),
    ],
    ids=["elem_def_without_type_refs", "elem_def_with_type_refs"],
    indirect=["elem_def", "profile"],
)
def test__resolve_supported_types(
    elem_def: ElementDefinition, profile, expected, package_manager
):
    values = _resolve_supported_types(elem_def, profile, package_manager)
    assert values == expected


@pytest.mark.parametrize(
    argnames="elem_def, profile, elem_expr_cache, chained_elem_id, expected",
    argvalues=[
        (
            "Condition.element1",
            StructureDefinitionSnapshot(
                url="http://organization.org/fhir/StructureDefinition/profile1",
                name="profile1",
                status="active",
                kind="resource",
                abstract=False,
                type="Condition",
                snapshot=fhir.resources.R4B.structuredefinition.StructureDefinitionSnapshot(
                    element=[
                        ElementDefinition(
                            id="Condition.element1", path="Condition.element1", type=[]
                        )
                    ]
                ),
            ),
            {"Condition": "Condition"},
            None,
            [],
        ),
        (
            "Observation.status",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-labor/StructureDefinition/ObservationLab",
            {"Observation": "Observation"},
            None,
            [
                MeasureGroupStratifier(
                    criteria=Expression(
                        language="text/fhirpath",
                        expression="Observation.status.hasValue()",
                    ),
                    code=CodeableConcept(
                        coding=[
                            Coding(
                                system="http://fhir-data-evaluator/strat/system",
                                code="Observation.status",
                            )
                        ]
                    ),
                )
            ],
        ),
        (
            "Condition.onset[x]",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-diagnose/StructureDefinition/Diagnose",
            {"Condition": "Condition"},
            None,
            [
                MeasureGroupStratifier(
                    criteria=Expression(
                        language="text/fhirpath",
                        expression="Condition.onset.exists(extension('http://hl7.org/fhir/StructureDefinition/data-absent-reason').empty())",
                    ),
                    code=CodeableConcept(
                        coding=[
                            Coding(
                                system="http://fhir-data-evaluator/strat/system",
                                code="Condition.onset[x]",
                            )
                        ]
                    ),
                ),
                MeasureGroupStratifier(
                    criteria=Expression(
                        language="text/fhirpath",
                        expression="Condition.onset.ofType(dateTime).hasValue()",
                    ),
                    code=CodeableConcept(
                        coding=[
                            Coding(
                                system="http://fhir-data-evaluator/strat/system",
                                code="Condition.onsetDateTime",
                            )
                        ]
                    ),
                ),
                MeasureGroupStratifier(
                    criteria=Expression(
                        language="text/fhirpath",
                        expression="Condition.onset.ofType(Period).exists(extension('http://hl7.org/fhir/StructureDefinition/data-absent-reason').empty())",
                    ),
                    code=CodeableConcept(
                        coding=[
                            Coding(
                                system="http://fhir-data-evaluator/strat/system",
                                code="Condition.onsetPeriod",
                            )
                        ]
                    ),
                ),
            ],
        ),
    ],
    ids=["elem_without_type", "elem_with_single_type", "elem_with_multiple_types"],
    indirect=["elem_def", "profile"],
)
def test__generate_stratifiers_for_elem_def(
    elem_def,
    profile,
    elem_expr_cache,
    chained_elem_id,
    expected,
    package_manager,
):
    values = _generate_stratifiers_for_elem_def(
        elem_def, profile, package_manager, elem_expr_cache, chained_elem_id
    )
    assert values == expected


@pytest.mark.parametrize(
    "profile, id_num, expected",
    [
        (
            StructureDefinition(
                url="http://organization.org/fhir/StructureDefinition/profile1",
                version="1.0.0",
                name="profile1",
                status="active",
                kind="resource",
                abstract=False,
                type="Condition",
                snapshot=fhir.resources.R4B.structuredefinition.StructureDefinitionSnapshot(
                    element=[
                        ElementDefinition(
                            id="Condition",
                            path="Condition",
                        ),
                        ElementDefinition(
                            id="Condition.element1[x]",
                            path="Condition.element1",
                            type=[
                                ElementDefinitionType(
                                    code="string",
                                ),
                                ElementDefinitionType(
                                    code="boolean",
                                ),
                            ],
                        ),
                    ]
                ),
            ),
            0,
            MeasureGroup(
                id="grp_profile1",
                extension=[
                    Extension(
                        url="http://hl7.org/fhir/StructureDefinition/elementSource",
                        valueUri="http://organization.org/fhir/StructureDefinition/profile1#1.0.0",
                    )
                ],
                population=[
                    MeasureGroupPopulation(
                        id="initial-population-identifier-0",
                        code=CodeableConcept(
                            coding=[
                                Coding(
                                    system="http://terminology.hl7.org/CodeSystem/measure-population",
                                    code="initial-population",
                                    display="Initial Population",
                                )
                            ]
                        ),
                        criteria=Expression(
                            language="text/x-fhir-query",
                            expression="Condition?_profile:below=http://organization.org/fhir/StructureDefinition/profile1",
                        ),
                    ),
                    MeasureGroupPopulation(
                        id="measure-population-identifier-0",
                        code=CodeableConcept(
                            coding=[
                                Coding(
                                    system="http://terminology.hl7.org/CodeSystem/measure-population",
                                    code="measure-population",
                                    display="Measure Population",
                                )
                            ]
                        ),
                        criteria=Expression(
                            language="text/fhirpath",
                            expression="Condition",
                        ),
                    ),
                    MeasureGroupPopulation(
                        id="measure-observation-identifier-0",
                        extension=[
                            Extension(
                                url="http://hl7.org/fhir/us/cqfmeasures/StructureDefinition/cqfm-aggregateMethod",
                                valueCode="unique-count",
                            ),
                            Extension(
                                url="http://hl7.org/fhir/us/cqfmeasures/StructureDefinition/cqfm-criteriaReference",
                                valueString="measure-population-identifier-0",
                            ),
                        ],
                        code=CodeableConcept(
                            coding=[
                                Coding(
                                    system="http://terminology.hl7.org/CodeSystem/measure-population",
                                    code="measure-observation",
                                    display="Measure Observation",
                                )
                            ]
                        ),
                        criteria=Expression(
                            language="text/fhirpath",
                            expression="Condition.id.value",
                        ),
                    ),
                ],
                stratifier=[
                    MeasureGroupStratifier(
                        code=CodeableConcept(
                            coding=[
                                Coding(
                                    system="http://fhir-data-evaluator/strat/system",
                                    code="Condition.element1[x]",
                                )
                            ]
                        ),
                        criteria=Expression(
                            language="text/fhirpath",
                            expression="Condition.element1.exists(extension('http://hl7.org/fhir/StructureDefinition/data-absent-reason').empty())",
                        ),
                    ),
                    MeasureGroupStratifier(
                        code=CodeableConcept(
                            coding=[
                                Coding(
                                    system="http://fhir-data-evaluator/strat/system",
                                    code="Condition.element1String",
                                )
                            ]
                        ),
                        criteria=Expression(
                            language="text/fhirpath",
                            expression="Condition.element1.ofType(string).hasValue()",
                        ),
                    ),
                    MeasureGroupStratifier(
                        code=CodeableConcept(
                            coding=[
                                Coding(
                                    system="http://fhir-data-evaluator/strat/system",
                                    code="Condition.element1Boolean",
                                )
                            ]
                        ),
                        criteria=Expression(
                            language="text/fhirpath",
                            expression="Condition.element1.ofType(boolean).hasValue()",
                        ),
                    ),
                ],
            ),
        )
    ],
    ids=["basic"],
    indirect=["profile"],
)
def test__generate_measure_group_for_profile(
    profile: StructureDefinitionSnapshot,
    id_num: int,
    expected,
    package_manager: FhirPackageManager,
):
    value = _generate_measure_group_for_profile(profile, package_manager, id_num)
    assert value.model_dump_json() == expected.model_dump_json()


@pytest.mark.parametrize(
    argnames="measure, expected",
    argvalues=[
        (
            Measure(
                status="active",
                group=[
                    MeasureGroup(
                        id="grp_test_abc",
                        stratifier=[
                            MeasureGroupStratifier(),
                        ],
                    ),
                    MeasureGroup(
                        id="grp_test_def",
                        stratifier=[
                            MeasureGroupStratifier(),
                        ],
                    ),
                ],
            ),
            Measure(
                status="active",
                group=[
                    MeasureGroup(
                        id="grp_test_abc",
                        stratifier=[
                            MeasureGroupStratifier(id="strat_grp_test_abc_1"),
                        ],
                    ),
                    MeasureGroup(
                        id="grp_test_def",
                        stratifier=[
                            MeasureGroupStratifier(id="strat_grp_test_def_1"),
                        ],
                    ),
                ],
            ),
        ),
        (
            Measure(
                status="active",
                group=[
                    MeasureGroup(
                        id="grp_test_abc",
                        stratifier=[
                            MeasureGroupStratifier(),
                            MeasureGroupStratifier(),
                            MeasureGroupStratifier(),
                        ],
                    ),
                ],
            ),
            Measure(
                status="active",
                group=[
                    MeasureGroup(
                        id="grp_test_abc",
                        stratifier=[
                            MeasureGroupStratifier(id="strat_grp_test_abc_1"),
                            MeasureGroupStratifier(id="strat_grp_test_abc_2"),
                            MeasureGroupStratifier(id="strat_grp_test_abc_3"),
                        ],
                    ),
                ],
            ),
        ),
    ],
    ids=["multiple_groups", "multiple_stratifiers_in_group"],
)
def test_update_stratifier_ids(measure: Measure, expected: Measure):
    value = update_stratifier_ids(measure)
    assert value.model_dump_json() == expected.model_dump_json()


def test_generate_measure(package_manager: FhirPackageManager):
    measure = generate_measure(package_manager)
    assert isinstance(measure, Measure)
