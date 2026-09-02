from contextlib import nullcontext
from pathlib import Path

import fhir.resources.R4B.structuredefinition
import pytest
from dataportal_generator.common.fhir.package_manager import FhirPackageManager
from dataportal_generator.common.fhirpath import fhirpathParser, parse_expr
from dataportal_generator.common.model.fhir.nav_structure_definition import (
    NavStructureDefinition,
)
from dataportal_generator.common.model.project import Project
from fhir.resources.R4B.codeableconcept import CodeableConcept
from fhir.resources.R4B.coding import Coding
from fhir.resources.R4B.elementdefinition import (
    ElementDefinition,
    ElementDefinitionBase,
    ElementDefinitionSlicing,
    ElementDefinitionSlicingDiscriminator,
    ElementDefinitionType,
)
from fhir.resources.R4B.expression import Expression
from fhir.resources.R4B.extension import Extension
from fhir.resources.R4B.measure import (
    Measure,
    MeasureGroup,
    MeasureGroupPopulation,
    MeasureGroupStratifier,
)

from dataportal_generator.availability.core.element_availability import (
    StratifierGenerator,
    _add_data_absent_reason_clause,
    _ensure_trailing_existence_check,
    _find_subject_reference_elem_def,
    _generate_stratifier,
    _resolve_polymorphism_in_expr,
    _selector_sub_expr_for_elem_def,
    generate_element_availability_measure,
    generate_measure_group_for_struct_def,
    update_stratifier_ids,
)


@pytest.mark.parametrize(
    argnames=["nav_elem_def", "nav_struct_def", "expected"],
    argvalues=[
        pytest.param(
            "Encounter.type:Kontaktebene",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
            "where(coding.exists(system = 'http://fhir.de/CodeSystem/Kontaktebene'))",
            id="slice-element",
        ),
        pytest.param(
            "Encounter.type",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
            "type",
            id="non-slice-element",
        ),
    ],
    indirect=["nav_elem_def", "nav_struct_def"],
)
def test__selector_sub_expr_for_elem_def(nav_elem_def, nav_struct_def, expected):
    assert _selector_sub_expr_for_elem_def(nav_elem_def) == expected


@pytest.mark.parametrize(
    argnames="nav_struct_def, expected",
    argvalues=[
        (
            "https://www.medizininformatik-initiative.de/fhir/core/modul-medikation/StructureDefinition/Medication",
            None,
        ),
        (
            "https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Specimen",
            "Specimen.subject",
        ),
        (
            "https://www.medizininformatik-initiative.de/fhir/core/modul-diagnose/StructureDefinition/Diagnose",
            "Condition.subject",
        ),
        (
            "http://hl7.org/fhir/StructureDefinition/AllergyIntolerance",
            "AllergyIntolerance.patient",
        ),
    ],
    ids=[
        "no-patient-ref-elem",
        "single-pat-ref-elem",
        "many-pat-ref-elem-subject",
        "many-pat-ref-elem-patient",
    ],
    indirect=["nav_struct_def"],
)
def test_find_subject_reference_elem_def(nav_struct_def, expected):
    result = _find_subject_reference_elem_def(nav_struct_def)
    assert (result.id if result else None) == expected


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
    "expr, field_name, expected",
    [
        (
            "Resource.element1.where(element2 = 'abc').element3.exists()",
            "Resource.element1.element3",
            {
                "id": "Resource.element1.element3",
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
                "id": "Resource.element1",
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
                "id": "Resource.element1",
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
    "expr, fhir_type, expected",
    [
        ("Resource.element1[x]", "DataType", "Resource.element1.ofType(DataType)"),
        ("Resource.element1[x]", None, "Resource.element1"),
    ],
)
def test__resolve_polymorphism_in_expr(expr: str, fhir_type: str | None, expected: str):
    value = _resolve_polymorphism_in_expr(expr, fhir_type)
    assert value == expected


class TestMeasureGroupGenerator:
    @pytest.mark.parametrize(
        argnames="nav_elem_def, nav_struct_def, elem_expr_cache, expected",
        argvalues=[
            pytest.param(
                "Encounter.status",
                "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
                {"Encounter": "Encounter"},
                [
                    MeasureGroupStratifier(
                        id="Encounter.status",
                        code=CodeableConcept(
                            coding=[
                                Coding(
                                    system="http://fhir-data-evaluator/strat/system",
                                    code="Encounter.status",
                                )
                            ]
                        ),
                        criteria=Expression(
                            language="text/fhirpath",
                            expression="Encounter.status.hasValue()",
                        ),
                    )
                ],
                id="primitive-typed-element",
            ),
            pytest.param(
                "Encounter.period",
                "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
                {"Encounter": "Encounter"},
                [
                    MeasureGroupStratifier(
                        id="Encounter.period",
                        code=CodeableConcept(
                            coding=[
                                Coding(
                                    system="http://fhir-data-evaluator/strat/system",
                                    code="Encounter.period",
                                )
                            ]
                        ),
                        criteria=Expression(
                            language="text/fhirpath",
                            expression="Encounter.period.exists(extension('http://hl7.org/fhir/StructureDefinition/data-absent-reason').empty())",
                        ),
                    ),
                    MeasureGroupStratifier(
                        id="Encounter.period.extension",
                        code=CodeableConcept(
                            coding=[
                                Coding(
                                    system="http://fhir-data-evaluator/strat/system",
                                    code="Encounter.period.extension",
                                )
                            ]
                        ),
                        criteria=Expression(
                            language="text/fhirpath",
                            expression="Encounter.period.extension.exists()",
                        ),
                    ),
                    MeasureGroupStratifier(
                        id="Encounter.period.start",
                        code=CodeableConcept(
                            coding=[
                                Coding(
                                    system="http://fhir-data-evaluator/strat/system",
                                    code="Encounter.period.start",
                                )
                            ]
                        ),
                        criteria=Expression(
                            language="text/fhirpath",
                            expression="Encounter.period.start.hasValue()",
                        ),
                    ),
                    MeasureGroupStratifier(
                        id="Encounter.period.end",
                        code=CodeableConcept(
                            coding=[
                                Coding(
                                    system="http://fhir-data-evaluator/strat/system",
                                    code="Encounter.period.end",
                                )
                            ]
                        ),
                        criteria=Expression(
                            language="text/fhirpath",
                            expression="Encounter.period.end.hasValue()",
                        ),
                    ),
                ],
                id="complex-typed-element",
            ),
            pytest.param(
                "Encounter.type:Kontaktebene",
                "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
                {
                    "Encounter": "Encounter",
                    "Encounter.type": "Encounter.type",
                },
                [
                    MeasureGroupStratifier(
                        id="Encounter.type:Kontaktebene",
                        code=CodeableConcept(
                            coding=[
                                Coding(
                                    system="http://fhir-data-evaluator/strat/system",
                                    code="Encounter.type:Kontaktebene",
                                )
                            ]
                        ),
                        criteria=Expression(
                            language="text/fhirpath",
                            expression="Encounter.type.exists(coding.exists(system = 'http://fhir.de/CodeSystem/Kontaktebene') and extension('http://hl7.org/fhir/StructureDefinition/data-absent-reason').empty())",
                        ),
                    ),
                ],
                id="complex-typed-slice-def-elem-def",
            ),
            pytest.param(
                "Encounter.extension:Aufnahmegrund.extension:ErsteUndZweiteStelle",
                "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
                {
                    "Encounter": "Encounter",
                    "Encounter.extension": "Encounter.extension",
                    "Encounter.extension:Aufnahmegrund": "Encounter.extension.where(url = 'http://fhir.de/StructureDefinition/Aufnahmegrund')",
                    "Encounter.extension:Aufnahmegrund.extension": "Encounter.extension.where(url = 'http://fhir.de/StructureDefinition/Aufnahmegrund').extension",
                },
                [
                    MeasureGroupStratifier(
                        id="Encounter.extension:Aufnahmegrund.extension:ErsteUndZweiteStelle",
                        code=CodeableConcept(
                            coding=[
                                Coding(
                                    system="http://fhir-data-evaluator/strat/system",
                                    code="Encounter.extension:Aufnahmegrund.extension:ErsteUndZweiteStelle",
                                )
                            ]
                        ),
                        criteria=Expression(
                            language="text/fhirpath",
                            expression="Encounter.extension.where(url = 'http://fhir.de/StructureDefinition/Aufnahmegrund').extension.exists(url = 'ErsteUndZweiteStelle')",
                        ),
                    ),
                    MeasureGroupStratifier(
                        id="Encounter.extension:Aufnahmegrund.extension:ErsteUndZweiteStelle.value[x]",
                        code=CodeableConcept(
                            coding=[
                                Coding(
                                    system="http://fhir-data-evaluator/strat/system",
                                    code="Encounter.extension:Aufnahmegrund.extension:ErsteUndZweiteStelle.value[x]",
                                )
                            ]
                        ),
                        criteria=Expression(
                            language="text/fhirpath",
                            expression="Encounter.extension.where(url = 'http://fhir.de/StructureDefinition/Aufnahmegrund').extension.where(url = 'ErsteUndZweiteStelle').value.ofType(Coding).exists(extension('http://hl7.org/fhir/StructureDefinition/data-absent-reason').empty())",
                        ),
                    ),
                ],
                id="simple-extension-elem-def-with-internal-extension-def",
            ),
            pytest.param(
                "Specimen.extension:festgestellteDiagnose",
                "https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Specimen",
                {
                    "Specimen": "Specimen",
                    "Specimen.extension": "Specimen.extension",
                },
                [
                    MeasureGroupStratifier(
                        id="Specimen.extension:festgestellteDiagnose",
                        code=CodeableConcept(
                            coding=[
                                Coding(
                                    system="http://fhir-data-evaluator/strat/system",
                                    code="Specimen.extension:festgestellteDiagnose",
                                )
                            ]
                        ),
                        criteria=Expression(
                            language="text/fhirpath",
                            expression="Specimen.extension.exists(url = 'https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Diagnose')",
                        ),
                    ),
                    MeasureGroupStratifier(
                        id="Specimen.extension:festgestellteDiagnose.value[x]",
                        code=CodeableConcept(
                            coding=[
                                Coding(
                                    system="http://fhir-data-evaluator/strat/system",
                                    code="Specimen.extension:festgestellteDiagnose.value[x]",
                                )
                            ]
                        ),
                        criteria=Expression(
                            language="text/fhirpath",
                            expression="Specimen.extension.where(url = 'https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Diagnose').value.ofType(Reference).reference.hasValue()",
                        ),
                    ),
                ],
                id="simple-extension-elem-def-with-external-extension-def",
            ),
            pytest.param(
                "Encounter.extension:Aufnahmegrund",
                "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
                {
                    "Encounter": "Encounter",
                    "Encounter.extension": "Encounter.extension",
                },
                [
                    MeasureGroupStratifier(
                        id="Encounter.extension:Aufnahmegrund",
                        code=CodeableConcept(
                            coding=[
                                Coding(
                                    system="http://fhir-data-evaluator/strat/system",
                                    code="Encounter.extension:Aufnahmegrund",
                                )
                            ]
                        ),
                        criteria=Expression(
                            language="text/fhirpath",
                            expression="Encounter.extension.exists(url = 'http://fhir.de/StructureDefinition/Aufnahmegrund')",
                        ),
                    ),
                    MeasureGroupStratifier(
                        id="Encounter.extension:Aufnahmegrund.extension:ErsteUndZweiteStelle",
                        code=CodeableConcept(
                            coding=[
                                Coding(
                                    system="http://fhir-data-evaluator/strat/system",
                                    code="Encounter.extension:Aufnahmegrund.extension:ErsteUndZweiteStelle",
                                )
                            ]
                        ),
                        criteria=Expression(
                            language="text/fhirpath",
                            expression="Encounter.extension.where(url = 'http://fhir.de/StructureDefinition/Aufnahmegrund').extension.exists(url = 'ErsteUndZweiteStelle')",
                        ),
                    ),
                    MeasureGroupStratifier(
                        id="Encounter.extension:Aufnahmegrund.extension:ErsteUndZweiteStelle.value[x]",
                        code=CodeableConcept(
                            coding=[
                                Coding(
                                    system="http://fhir-data-evaluator/strat/system",
                                    code="Encounter.extension:Aufnahmegrund.extension:ErsteUndZweiteStelle.value[x]",
                                )
                            ]
                        ),
                        criteria=Expression(
                            language="text/fhirpath",
                            expression="Encounter.extension.where(url = 'http://fhir.de/StructureDefinition/Aufnahmegrund').extension.where(url = 'ErsteUndZweiteStelle').value.ofType(Coding).exists(extension('http://hl7.org/fhir/StructureDefinition/data-absent-reason').empty())",
                        ),
                    ),
                    MeasureGroupStratifier(
                        id="Encounter.extension:Aufnahmegrund.extension:DritteStelle",
                        code=CodeableConcept(
                            coding=[
                                Coding(
                                    system="http://fhir-data-evaluator/strat/system",
                                    code="Encounter.extension:Aufnahmegrund.extension:DritteStelle",
                                )
                            ]
                        ),
                        criteria=Expression(
                            language="text/fhirpath",
                            expression="Encounter.extension.where(url = 'http://fhir.de/StructureDefinition/Aufnahmegrund').extension.exists(url = 'DritteStelle')",
                        ),
                    ),
                    MeasureGroupStratifier(
                        id="Encounter.extension:Aufnahmegrund.extension:DritteStelle.value[x]",
                        code=CodeableConcept(
                            coding=[
                                Coding(
                                    system="http://fhir-data-evaluator/strat/system",
                                    code="Encounter.extension:Aufnahmegrund.extension:DritteStelle.value[x]",
                                )
                            ]
                        ),
                        criteria=Expression(
                            language="text/fhirpath",
                            expression="Encounter.extension.where(url = 'http://fhir.de/StructureDefinition/Aufnahmegrund').extension.where(url = 'DritteStelle').value.ofType(Coding).exists(extension('http://hl7.org/fhir/StructureDefinition/data-absent-reason').empty())",
                        ),
                    ),
                    MeasureGroupStratifier(
                        id="Encounter.extension:Aufnahmegrund.extension:VierteStelle",
                        code=CodeableConcept(
                            coding=[
                                Coding(
                                    system="http://fhir-data-evaluator/strat/system",
                                    code="Encounter.extension:Aufnahmegrund.extension:VierteStelle",
                                )
                            ]
                        ),
                        criteria=Expression(
                            language="text/fhirpath",
                            expression="Encounter.extension.where(url = 'http://fhir.de/StructureDefinition/Aufnahmegrund').extension.exists(url = 'VierteStelle')",
                        ),
                    ),
                    MeasureGroupStratifier(
                        id="Encounter.extension:Aufnahmegrund.extension:VierteStelle.value[x]",
                        code=CodeableConcept(
                            coding=[
                                Coding(
                                    system="http://fhir-data-evaluator/strat/system",
                                    code="Encounter.extension:Aufnahmegrund.extension:VierteStelle.value[x]",
                                )
                            ]
                        ),
                        criteria=Expression(
                            language="text/fhirpath",
                            expression="Encounter.extension.where(url = 'http://fhir.de/StructureDefinition/Aufnahmegrund').extension.where(url = 'VierteStelle').value.ofType(Coding).exists(extension('http://hl7.org/fhir/StructureDefinition/data-absent-reason').empty())",
                        ),
                    ),
                ],
                id="complex-extension-elem-def-with-internal-extension-def",
            ),
            pytest.param(
                "Procedure.extension:modalityAndTechnique",
                "http://hl7.org/fhir/us/mcode/StructureDefinition/mcode-radiotherapy-course-summary",
                {
                    "Procedure": "Procedure",
                    "Procedure.extension": "Procedure.extension",
                },
                [
                    MeasureGroupStratifier(
                        id="Procedure.extension:modalityAndTechnique",
                        code=CodeableConcept(
                            coding=[
                                Coding(
                                    system="http://fhir-data-evaluator/strat/system",
                                    code="Procedure.extension:modalityAndTechnique",
                                )
                            ]
                        ),
                        criteria=Expression(
                            language="text/fhirpath",
                            expression="Procedure.extension.exists(url = 'http://hl7.org/fhir/us/mcode/StructureDefinition/mcode-radiotherapy-modality-and-technique')",
                        ),
                    ),
                    MeasureGroupStratifier(
                        id="Procedure.extension:modalityAndTechnique.extension:modality",
                        code=CodeableConcept(
                            coding=[
                                Coding(
                                    system="http://fhir-data-evaluator/strat/system",
                                    code="Procedure.extension:modalityAndTechnique.extension:modality",
                                )
                            ]
                        ),
                        criteria=Expression(
                            language="text/fhirpath",
                            expression="Procedure.extension.where(url = 'http://hl7.org/fhir/us/mcode/StructureDefinition/mcode-radiotherapy-modality-and-technique').extension.exists(url = 'http://hl7.org/fhir/us/mcode/StructureDefinition/mcode-radiotherapy-modality')",
                        ),
                    ),
                    MeasureGroupStratifier(
                        id="Procedure.extension:modalityAndTechnique.extension:modality.value[x]",
                        code=CodeableConcept(
                            coding=[
                                Coding(
                                    system="http://fhir-data-evaluator/strat/system",
                                    code="Procedure.extension:modalityAndTechnique.extension:modality.value[x]",
                                )
                            ]
                        ),
                        criteria=Expression(
                            language="text/fhirpath",
                            expression="Procedure.extension.where(url = 'http://hl7.org/fhir/us/mcode/StructureDefinition/mcode-radiotherapy-modality-and-technique').extension.where(url = 'http://hl7.org/fhir/us/mcode/StructureDefinition/mcode-radiotherapy-modality').value.ofType(CodeableConcept).exists(extension('http://hl7.org/fhir/StructureDefinition/data-absent-reason').empty())",
                        ),
                    ),
                    MeasureGroupStratifier(
                        id="Procedure.extension:modalityAndTechnique.extension:technique",
                        code=CodeableConcept(
                            coding=[
                                Coding(
                                    system="http://fhir-data-evaluator/strat/system",
                                    code="Procedure.extension:modalityAndTechnique.extension:technique",
                                )
                            ]
                        ),
                        criteria=Expression(
                            language="text/fhirpath",
                            expression="Procedure.extension.where(url = 'http://hl7.org/fhir/us/mcode/StructureDefinition/mcode-radiotherapy-modality-and-technique').extension.exists(url = 'http://hl7.org/fhir/us/mcode/StructureDefinition/mcode-radiotherapy-technique')",
                        ),
                    ),
                    MeasureGroupStratifier(
                        id="Procedure.extension:modalityAndTechnique.extension:technique.value[x]",
                        code=CodeableConcept(
                            coding=[
                                Coding(
                                    system="http://fhir-data-evaluator/strat/system",
                                    code="Procedure.extension:modalityAndTechnique.extension:technique.value[x]",
                                )
                            ]
                        ),
                        criteria=Expression(
                            language="text/fhirpath",
                            expression="Procedure.extension.where(url = 'http://hl7.org/fhir/us/mcode/StructureDefinition/mcode-radiotherapy-modality-and-technique').extension.where(url = 'http://hl7.org/fhir/us/mcode/StructureDefinition/mcode-radiotherapy-technique').value.ofType(CodeableConcept).exists(extension('http://hl7.org/fhir/StructureDefinition/data-absent-reason').empty())",
                        ),
                    ),
                ],
                id="complex-extension-elem-def-with-external-extension-def",
            ),
            pytest.param(
                "Procedure.performed[x]",
                "https://www.medizininformatik-initiative.de/fhir/core/modul-prozedur/StructureDefinition/Procedure",
                {
                    "Procedure": "Procedure",
                    "Procedure.performed[x]": "Procedure.performed[x]",
                },
                [
                    MeasureGroupStratifier(
                        id="Procedure.performed[x]",
                        code=CodeableConcept(
                            coding=[
                                Coding(
                                    system="http://fhir-data-evaluator/strat/system",
                                    code="Procedure.performed[x]",
                                )
                            ]
                        ),
                        criteria=Expression(
                            language="text/fhirpath",
                            expression="Procedure.performed.exists(extension('http://hl7.org/fhir/StructureDefinition/data-absent-reason').empty())",
                        ),
                    ),
                    MeasureGroupStratifier(
                        id="Procedure.performed[x]:performedDateTime",
                        code=CodeableConcept(
                            coding=[
                                Coding(
                                    system="http://fhir-data-evaluator/strat/system",
                                    code="Procedure.performed[x]:performedDateTime",
                                )
                            ]
                        ),
                        criteria=Expression(
                            language="text/fhirpath",
                            expression="Procedure.performed.ofType(dateTime).hasValue()",
                        ),
                    ),
                    MeasureGroupStratifier(
                        id="Procedure.performed[x]:performedPeriod",
                        code=CodeableConcept(
                            coding=[
                                Coding(
                                    system="http://fhir-data-evaluator/strat/system",
                                    code="Procedure.performed[x]:performedPeriod",
                                )
                            ]
                        ),
                        criteria=Expression(
                            language="text/fhirpath",
                            expression="Procedure.performed.ofType(Period).exists(extension('http://hl7.org/fhir/StructureDefinition/data-absent-reason').empty())",
                        ),
                    ),
                ],
                id="type-discriminated-slicing-def-elem-def",
            ),
        ],
        indirect=["nav_elem_def", "nav_struct_def"],
    )
    def test__generate_stratifiers_for_elem_def(
        self,
        nav_elem_def,
        nav_struct_def,
        elem_expr_cache,
        expected,
        package_manager,
    ):
        gen = StratifierGenerator(nav_struct_def, package_manager)
        gen._elem_expr_cache = elem_expr_cache
        values = gen._generate_stratifiers_for_elem_def(nav_elem_def)
        assert values == expected


@pytest.mark.parametrize(
    "nav_struct_def, id_num, expected",
    [
        (
            NavStructureDefinition(
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
                            base=ElementDefinitionBase(
                                path="Condition",
                                min=0,
                                max="*",
                            ),
                        ),
                        ElementDefinition(
                            id="Condition.subject",
                            path="Condition.subject",
                            type=[
                                ElementDefinitionType(
                                    code="Reference",
                                ),
                            ],
                            base=ElementDefinitionBase(
                                path="Condition.subject",
                                min=0,
                                max="1",
                            ),
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
                            slicing=ElementDefinitionSlicing(
                                discriminator=[
                                    ElementDefinitionSlicingDiscriminator(
                                        type="type",
                                        path="$this"
                                    )
                                ],
                                rules="closed"
                            ),
                            base=ElementDefinitionBase(
                                path="Condition.element1[x]",
                                min=0,
                                max="1",
                            ),
                        ),
                        ElementDefinition(
                            id="Condition.element1[x]:element1String",
                            path="Condition.element1",
                            type=[
                                ElementDefinitionType(
                                    code="string",
                                ),
                            ],
                            sliceName="element1String",
                            base=ElementDefinitionBase(
                                path="Condition.element1[x]",
                                min=0,
                                max="1",
                            ),
                        ),
                        ElementDefinition(
                            id="Condition.element1[x]:element1Boolean",
                            path="Condition.element1",
                            type=[
                                ElementDefinitionType(
                                    code="boolean",
                                ),
                            ],
                            sliceName="element1Boolean",
                            base=ElementDefinitionBase(
                                path="Condition.element1[x]",
                                min=0,
                                max="1",
                            ),
                        ),
                    ]
                ),
            ),
            0,
            nullcontext(
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
                                expression="Condition.subject.reference",
                            ),
                        ),
                    ],
                    stratifier=[
                        MeasureGroupStratifier(
                            id="Condition.element1[x]",
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
                            id="Condition.element1[x]:element1Boolean",
                            code=CodeableConcept(
                                coding=[
                                    Coding(
                                        system="http://fhir-data-evaluator/strat/system",
                                        code="Condition.element1[x]:element1Boolean",
                                    )
                                ]
                            ),
                            criteria=Expression(
                                language="text/fhirpath",
                                expression="Condition.element1.ofType(boolean).hasValue()",
                            ),
                        ),
                        MeasureGroupStratifier(
                            id="Condition.element1[x]:element1String",
                            code=CodeableConcept(
                                coding=[
                                    Coding(
                                        system="http://fhir-data-evaluator/strat/system",
                                        code="Condition.element1[x]:element1String",
                                    )
                                ]
                            ),
                            criteria=Expression(
                                language="text/fhirpath",
                                expression="Condition.element1.ofType(string).hasValue()",
                            ),
                        ),
                    ],
                )
            ),
        ),
        (
            NavStructureDefinition(
                url="http://organization.org/fhir/StructureDefinition/profile2",
                version="1.0.0",
                name="profile2",
                status="active",
                kind="resource",
                abstract=False,
                type="Specimen",
                snapshot=fhir.resources.R4B.structuredefinition.StructureDefinitionSnapshot(
                    element=[
                        ElementDefinition(
                            id="Specimen",
                            path="Specimen",
                            base=ElementDefinitionBase(
                                path="Specimen",
                                min=0,
                                max="*",
                            ),
                        ),
                        ElementDefinition(
                            id="Specimen.subject",
                            path="Specimen.subject",
                            type=[
                                ElementDefinitionType(
                                    code="Reference",
                                ),
                            ],
                            base=ElementDefinitionBase(
                                path="Specimen.subject",
                                min=0,
                                max="1",
                            ),
                        ),
                        ElementDefinition(
                            id="Specimen.extension",
                            path="Specimen.extension",
                            type=[
                                ElementDefinitionType(
                                    code="Extension",
                                ),
                            ],
                            slicing=ElementDefinitionSlicing(
                                discriminator=[
                                    ElementDefinitionSlicingDiscriminator(
                                        type="value", path="url"
                                    )
                                ],
                                rules="open",
                            ),
                            base=ElementDefinitionBase(
                                path="DomainResource.extension",
                                min=0,
                                max="*",
                            ),
                        ),
                        ElementDefinition(
                            id="Specimen.extension:festgestellteDiagnose",
                            path="Specimen.extension",
                            sliceName="festgestellteDiagnose",
                            type=[
                                ElementDefinitionType(
                                    code="Extension",
                                    profile=[
                                        "https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Diagnose"
                                    ],
                                ),
                            ],
                            base=ElementDefinitionBase(
                                path="DomainResource.extension",
                                min=0,
                                max="*",
                            ),
                        ),
                    ]
                ),
            ),
            0,
            nullcontext(
                MeasureGroup(
                    id="grp_profile2",
                    extension=[
                        Extension(
                            url="http://hl7.org/fhir/StructureDefinition/elementSource",
                            valueUri="http://organization.org/fhir/StructureDefinition/profile2#1.0.0",
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
                                expression="Specimen?_profile:below=http://organization.org/fhir/StructureDefinition/profile2",
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
                                expression="Specimen",
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
                                expression="Specimen.subject.reference",
                            ),
                        ),
                    ],
                    stratifier=[
                        MeasureGroupStratifier(
                            id="Specimen.extension",
                            code=CodeableConcept(
                                coding=[
                                    Coding(
                                        system="http://fhir-data-evaluator/strat/system",
                                        code="Specimen.extension",
                                    )
                                ]
                            ),
                            criteria=Expression(
                                language="text/fhirpath",
                                expression="Specimen.extension.exists()",
                            ),
                        ),
                        MeasureGroupStratifier(
                            id="Specimen.extension:festgestellteDiagnose",
                            code=CodeableConcept(
                                coding=[
                                    Coding(
                                        system="http://fhir-data-evaluator/strat/system",
                                        code="Specimen.extension:festgestellteDiagnose",
                                    )
                                ]
                            ),
                            criteria=Expression(
                                language="text/fhirpath",
                                expression="Specimen.extension.exists(url = 'https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Diagnose')",
                            ),
                        ),
                        MeasureGroupStratifier(
                            id="Specimen.extension:festgestellteDiagnose.value[x]",
                            code=CodeableConcept(
                                coding=[
                                    Coding(
                                        system="http://fhir-data-evaluator/strat/system",
                                        code="Specimen.extension:festgestellteDiagnose.value[x]",
                                    )
                                ]
                            ),
                            criteria=Expression(
                                language="text/fhirpath",
                                expression="Specimen.extension.where(url = 'https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Diagnose').value.ofType(Reference).reference.hasValue()",
                            ),
                        ),
                    ],
                )
            ),
        ),
        (
            Path("struct_def_with_internally_defined_extension.json"),
            0,
            nullcontext(
                MeasureGroup(
                    id="grp_mii_pr_fall_kontaktgesundheitseinrichtung",
                    extension=[
                        Extension(
                            url="http://hl7.org/fhir/StructureDefinition/elementSource",
                            valueUri="https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung#2025.0.1",
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
                                expression="Encounter?_profile:below=https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
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
                                expression="Encounter",
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
                                expression="Encounter.subject.reference",
                            ),
                        ),
                    ],
                    stratifier=[
                        MeasureGroupStratifier(
                            id="Encounter.extension",
                            code=CodeableConcept(
                                coding=[
                                    Coding(
                                        code="Encounter.extension",
                                        system="http://fhir-data-evaluator/strat/system",
                                    )
                                ],
                            ),
                            criteria=Expression(
                                expression="Encounter.extension.exists()",
                                language="text/fhirpath",
                            ),
                        ),
                        MeasureGroupStratifier(
                            id="Encounter.extension:Aufnahmegrund",
                            code=CodeableConcept(
                                coding=[
                                    Coding(
                                        code="Encounter.extension:Aufnahmegrund",
                                        system="http://fhir-data-evaluator/strat/system",
                                    )
                                ],
                            ),
                            criteria=Expression(
                                expression="Encounter.extension.exists(url = 'http://fhir.de/StructureDefinition/Aufnahmegrund')",
                                language="text/fhirpath",
                            ),
                        ),
                        MeasureGroupStratifier(
                            id="Encounter.extension:Aufnahmegrund.extension:DritteStelle",
                            code=CodeableConcept(
                                coding=[
                                    Coding(
                                        code="Encounter.extension:Aufnahmegrund.extension:DritteStelle",
                                        system="http://fhir-data-evaluator/strat/system",
                                    )
                                ],
                            ),
                            criteria=Expression(
                                expression="Encounter.extension.where(url = 'http://fhir.de/StructureDefinition/Aufnahmegrund').extension.exists(url = 'DritteStelle')",
                                language="text/fhirpath",
                            ),
                        ),
                        MeasureGroupStratifier(
                            id="Encounter.extension:Aufnahmegrund.extension:DritteStelle.value[x]",
                            code=CodeableConcept(
                                coding=[
                                    Coding(
                                        code="Encounter.extension:Aufnahmegrund.extension:DritteStelle.value[x]",
                                        system="http://fhir-data-evaluator/strat/system",
                                    )
                                ],
                            ),
                            criteria=Expression(
                                expression="Encounter.extension.where(url = 'http://fhir.de/StructureDefinition/Aufnahmegrund').extension.where(url = 'DritteStelle').value.ofType(Coding).exists(extension('http://hl7.org/fhir/StructureDefinition/data-absent-reason').empty())",
                                language="text/fhirpath",
                            ),
                        ),
                        MeasureGroupStratifier(
                            id="Encounter.extension:Aufnahmegrund.extension:ErsteUndZweiteStelle",
                            code=CodeableConcept(
                                coding=[
                                    Coding(
                                        code="Encounter.extension:Aufnahmegrund.extension:ErsteUndZweiteStelle",
                                        system="http://fhir-data-evaluator/strat/system",
                                    )
                                ],
                            ),
                            criteria=Expression(
                                expression="Encounter.extension.where(url = 'http://fhir.de/StructureDefinition/Aufnahmegrund').extension.exists(url = 'ErsteUndZweiteStelle')",
                                language="text/fhirpath",
                            ),
                        ),
                        MeasureGroupStratifier(
                            id="Encounter.extension:Aufnahmegrund.extension:ErsteUndZweiteStelle.value[x]",
                            code=CodeableConcept(
                                coding=[
                                    Coding(
                                        code="Encounter.extension:Aufnahmegrund.extension:ErsteUndZweiteStelle.value[x]",
                                        system="http://fhir-data-evaluator/strat/system",
                                    )
                                ],
                            ),
                            criteria=Expression(
                                expression="Encounter.extension.where(url = 'http://fhir.de/StructureDefinition/Aufnahmegrund').extension.where(url = 'ErsteUndZweiteStelle').value.ofType(Coding).exists(extension('http://hl7.org/fhir/StructureDefinition/data-absent-reason').empty())",
                                language="text/fhirpath",
                            ),
                        ),
                        MeasureGroupStratifier(
                            id="Encounter.extension:Aufnahmegrund.extension:VierteStelle",
                            code=CodeableConcept(
                                coding=[
                                    Coding(
                                        code="Encounter.extension:Aufnahmegrund.extension:VierteStelle",
                                        system="http://fhir-data-evaluator/strat/system",
                                    )
                                ],
                            ),
                            criteria=Expression(
                                expression="Encounter.extension.where(url = 'http://fhir.de/StructureDefinition/Aufnahmegrund').extension.exists(url = 'VierteStelle')",
                                language="text/fhirpath",
                            ),
                        ),
                        MeasureGroupStratifier(
                            id="Encounter.extension:Aufnahmegrund.extension:VierteStelle.value[x]",
                            code=CodeableConcept(
                                coding=[
                                    Coding(
                                        code="Encounter.extension:Aufnahmegrund.extension:VierteStelle.value[x]",
                                        system="http://fhir-data-evaluator/strat/system",
                                    )
                                ],
                            ),
                            criteria=Expression(
                                expression="Encounter.extension.where(url = 'http://fhir.de/StructureDefinition/Aufnahmegrund').extension.where(url = 'VierteStelle').value.ofType(Coding).exists(extension('http://hl7.org/fhir/StructureDefinition/data-absent-reason').empty())",
                                language="text/fhirpath",
                            ),
                        ),
                    ],
                )
            ),
        ),
        (
            "http://hl7.org/fhir/StructureDefinition/Parameters",
            0,
            pytest.raises(
                ValueError,
                match="no suitable subject reference element and thus no measure group can be generated",
            ),
        ),
    ],
    ids=[
        "basic",
        "profile-with-constrained-but-externally-defined-extension",
        "profile-with-internally-defined-extension",
        "profile-without-subject-ref-elem",
    ],
    indirect=["nav_struct_def"],
)
def test_generate_measure_group_for_struct_def(
    nav_struct_def: NavStructureDefinition,
    id_num: int,
    expected,
    package_manager: FhirPackageManager,
):
    with expected as e:
        value = generate_measure_group_for_struct_def(nav_struct_def, package_manager, id_num)
        value.stratifier = sorted(value.stratifier, key=lambda s: s.id)
        assert value.model_dump_json(indent=2) == e.model_dump_json(indent=2)


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
    assert value.model_dump_json(indent=2) == expected.model_dump_json(indent=2)


def test_generate_measure(project: Project):
    measure = generate_element_availability_measure(project)
    assert isinstance(measure, Measure)
