import json
import time
from typing import List

import pytest
from fhir.resources.R4B.elementdefinition import ElementDefinition
from pytest_lazy_fixtures import lf

from cohort_selection_ontology.model.ui_data import (
    TranslationDisplayElement,
    Translation,
)
from common.util.structure_definition.functions import (
    extract_reference_type,
    get_element_defining_elements,
    get_element_defining_elements_with_source_snapshots,
    resolve_defining_id,
    extract_value_type,
    get_display_from_element_definition,
    get_common_ancestor_id,
    get_parent_slice_id,
    is_element_slice_base,
    structure_definition_from_path,
    translate_element_to_fhir_path_expression,
    find_polymorphic_value, ProcessedElementResult,
)
from tests.unit.StructureDefinitionSnapshot_test.conftest import sample_snapshot_bioprobe
from common.model.structure_definition import (
    StructureDefinitionSnapshot,
)
from common.util.project import Project


@pytest.mark.parametrize(
    "search_term",
    [
        "Observation.code.coding",
        "Specimen.code",
        "Specimen.type",
        "Specimen.type.coding",
        "Specimen.type.coding:sct",
        "Specimen.collection.bodySite.coding",
        "Specimen.collection.bodySite.coding:sct",
    ],
)
def test_sds_get_element_by_id(
    search_term: str,
    sample_snapshot_bioprobe: StructureDefinitionSnapshot,
    sample_snapshot_bioprobe_json: dict,
):
    start = time.perf_counter_ns()
    found_in_class: ElementDefinition | None = (
        sample_snapshot_bioprobe.get_element_by_id(search_term)
    )
    result_class = time.perf_counter_ns() - start

    found_in_snapshot: ElementDefinition | None = None

    start = time.perf_counter_ns()
    for element in sample_snapshot_bioprobe_json.get("snapshot").get("element"):
        if element.get("id") == search_term:
            found_in_snapshot = ElementDefinition.model_validate_json(
                json.dumps(element)
            )
            break
    result_snapshot = time.perf_counter_ns() - start

    print(f"\nSearchTerm: {search_term}")
    print(
        f"Found iterative: "
        f"{found_in_snapshot.id if found_in_snapshot else found_in_snapshot }"
        f"\t\t\t in {result_snapshot} ns"
    )
    print(
        f"Found   indexed: "
        f"{found_in_class.id if found_in_class else found_in_class}"
        f"\t\t\t in {result_class} ns"
    )

    assert found_in_class == found_in_snapshot

@pytest.mark.parametrize(
    "search_term",
    [
        "Specimen",
        "Specimen.collection.bodySite.coding",
        "Specimen.collection.bodySite.coding.id",
        "Specimen.collection.bodySite.coding:sct.id",
    ],
)
def test_sds_get_elements_by_path(
    search_term: str,
    sample_snapshot_bioprobe: StructureDefinitionSnapshot,
    sample_snapshot_bioprobe_json: dict,
):
    start = time.perf_counter_ns()
    found_in_class: List[ElementDefinition] | None = (
        sample_snapshot_bioprobe.get_element_by_path(search_term)
    )
    result_class = time.perf_counter_ns() - start

    found_in_snapshot: List[ElementDefinition] | None = None

    start = time.perf_counter_ns()
    for element in sample_snapshot_bioprobe_json.get("snapshot").get("element"):
        if element.get("path") == search_term:
            if found_in_snapshot is None:
                found_in_snapshot = []
            found_in_snapshot.append(
                ElementDefinition.model_validate_json(json.dumps(element))
            )
    result_snapshot = time.perf_counter_ns() - start

    print(f"\nSearchTerm: {search_term}")
    print(
        f"Found iterative: "
        f"{len(found_in_snapshot) if found_in_snapshot else found_in_snapshot}"
        f"\t\t\t in {result_snapshot} ns"
    )
    print(
        f"Found   indexed: "
        f"{len(found_in_class) if found_in_class else found_in_class}"
        f"\t\t\t in {result_class} ns"
    )

    assert found_in_class == found_in_snapshot


def test_sds_get_multiple_elements(
    sample_snapshot_bioprobe: StructureDefinitionSnapshot, project: Project
):
    chained_element_id = (
        "((Specimen.extension:festgestellteDiagnose).value[x]).code.coding:icd10-gm"
    )
    actual_result = (
        get_element_defining_elements_with_source_snapshots(
            sample_snapshot_bioprobe,
            chained_element_id,
            "Bioprobe",
            project.input.cso.path / "modules",
        )
    )

    p1 = ProcessedElementResult(
        element=sample_snapshot_bioprobe.get_element_by_id(
            "Specimen.extension:festgestellteDiagnose"
        ),
        profile_snapshot=sample_snapshot_bioprobe,
        module_dir=project.input.cso.path / "modules" / "Bioprobe",
        last_short_desc=None,
    )

    p2_snap = structure_definition_from_path(
        project.input.cso.path
        / "modules"
        / "Bioprobe"
        / "differential"
        / "package"
        / "extension"
        / "FDPG_DiagnoseExtension-snapshot.json"
    )
    p2 = ProcessedElementResult(
        element=p2_snap.get_element_by_id("Extension.value[x]"),
        profile_snapshot=p2_snap,
        module_dir=project.input.cso.path / "modules" / "Bioprobe",
        last_short_desc=None,
    )
    p3_snap = structure_definition_from_path(
        project.input.cso.path
        / "modules"
        / "Diagnose"
        / "differential"
        / "package"
        / "FDPG_Diagnose-snapshot.json",
    )
    p3 = ProcessedElementResult(
        element=p3_snap.get_element_by_id("Condition.code.coding:icd10-gm"),
        profile_snapshot=p3_snap,
        module_dir=project.input.cso.path / "modules" / "Diagnose",
        last_short_desc=None,
    )

    assert actual_result[0].element == p1.element
    assert actual_result[1].element == p2.element
    assert actual_result[2].element == p3.element


def test_get_parent_slice_id():

    assert (
        get_parent_slice_id(
            "Observation.component:Diastolic.code.coding:sct"
        )
        == "Observation.component:Diastolic.code.coding:sct"
    )
    assert (
        get_parent_slice_id(
            "Observation.component:Diastolic.code.coding"
        )
        == "Observation.component:Diastolic"
    )
    assert get_parent_slice_id("Observation.component") is None


@pytest.mark.parametrize(
    "element_id, polymorphic_elem_prefix, expected, sample_snapshot",
    [
        (
            "Condition.code.coding:icd10-gm.system",
            "fixed",
            True,
            lf("sample_snapshot_diagnose"),
        ),
        (
            "Condition.code.coding:icd10-gm",
            "pattern",
            True,
            lf("sample_snapshot_diagnose"),
        ),
        (
            "Observation.code.coding",
            "fixed",
            False,
            lf("sample_snapshot_diagnose"),
        )
    ],
)
def test_sds_find_polymorphic_value(
    sample_snapshot: StructureDefinitionSnapshot,
    element_id: str,
    polymorphic_elem_prefix: str,
    expected: bool,
):
    elem = sample_snapshot.get_element_by_id(element_id)
    if expected:
        assert find_polymorphic_value(elem, polymorphic_elem_prefix) is not None
    else:
        assert find_polymorphic_value(elem, polymorphic_elem_prefix) is None

@pytest.mark.parametrize(
    "element_id, expected",
    [
        ("Observation.code.coding", False),
        ("Specimen.code", False),
        ("Specimen.type", False),
        ("Specimen.type.coding", False),
        ("Specimen.type.coding:sct", True),
        ("Specimen.collection.bodySite.coding", False),
        ("Specimen.collection.bodySite.coding:sct", True),
        ("Observation.component:Diastolic", True),
        ("Observation.component:Diastolic.code", False),
    ],
)
def test_is_element_slice_base(
    element_id: str,
    expected: bool,
):
    assert is_element_slice_base(element_id) == expected


@pytest.mark.parametrize(
    "element_id1, element_id2, expected",
    [
        (
            "Observation.component:Systolic.short",
            "Observation.component:Diastolic.code.short",
            "Observation.component",
        ),
        (
            "Observation.component:Diastolic.short",
            "Observation.component:Diastolic.code.short",
            "Observation.component:Diastolic",
        ),
        (
            "Observation.component",
            "Observation.component",
            "Observation.component",
        ),
    ],
)
def test_common_ancestor_id(
    element_id1: str,
    element_id2: str,
    expected: str,
):
    assert (
        get_common_ancestor_id(element_id1, element_id2)
        == expected
    )


@pytest.mark.parametrize(
    "attribute_id, module_dir_name, expected",
    [
        (
            "Specimen.collection.bodySite.coding:icd-o-3",
            "Bioprobe",
            "Coding",
        ),
        (
            "((Specimen.extension:festgestellteDiagnose).value[x]).code.coding:icd10-gm",
            "Bioprobe",
            "Coding",
        ),
    ],
)
def test_extract_value_type(
    sample_snapshot_bioprobe: StructureDefinitionSnapshot,
    project: Project,
    attribute_id: str,
    module_dir_name: str,
    expected: str,
):
    modules_dir = project.input.cso.path / "modules"
    attribute_element = resolve_defining_id(
        sample_snapshot_bioprobe, attribute_id, str(modules_dir), module_dir_name
    )
    assert (
        extract_value_type(
            attribute_element, sample_snapshot_bioprobe.name
        )
        == expected
    )


@pytest.mark.parametrize(
    "sample_snapshot, value_defining_id, expected",
    [
        (
            lf("sample_snapshot_bioprobe"),
            "((Specimen.extension:festgestellteDiagnose).value[x]).code.coding:icd10-gm",
            "Condition",
        )
    ],
)
def test_extract_reference_type(
    sample_snapshot: StructureDefinitionSnapshot,
    project: Project,
    value_defining_id: str,
    expected: str,
):
    modules_dir = project.input.cso.path / "modules"

    elements = get_element_defining_elements(
        sample_snapshot, value_defining_id, sample_snapshot.name, modules_dir
    )

    found_reference_type = ""

    for element in elements:
        for element_type in element.type:
            if element_type.code == "Reference":
                found_reference_type = extract_reference_type(
                    element_type, modules_dir, sample_snapshot.name
                )
                break
    assert found_reference_type == expected


@pytest.mark.parametrize(
    "sample_snapshot, element_id, default, expected_display",
    [
        (
            lf("sample_snapshot_diagnose"),
            "Condition.code.coding:icd10-gm",
            "icd10-gm",
            TranslationDisplayElement(
                original="ICD-10-GM Code",
                translations=[
                    Translation(language="de-DE", value="ICD-10-GM Code"),
                    Translation(language="en-US", value="ICD-10-GM code"),
                ],
            ),
        ),
        (
            lf("sample_snapshot_bioprobe"),
            "Specimen.collection.bodySite.coding:icd-o-3",
            "icd-o-3",
            TranslationDisplayElement(
                original="Code defined by a terminology system",
                translations=[
                    Translation(language="de-DE", value=""),
                    Translation(language="en-US", value=""),
                ],
            ),
        ),
    ],
)
def test_get_display_from_element_definition(
    sample_snapshot: StructureDefinitionSnapshot,
    element_id: str,
    default: str,
    expected_display: TranslationDisplayElement,
):

    element = sample_snapshot.get_element_by_id(element_id)

    assert (
        get_display_from_element_definition(element, default)
        == expected_display
    )


@pytest.mark.parametrize(
    "element_id, sample_snapshot, module_dir_name, expected, is_composite",
    [
        (
            "Specimen.collection.collected[x]",
            lf("sample_snapshot_bioprobe"),
            "Bioprobe",
            ["(Specimen.collection.collected as dateTime)"],
            False
        ),
        (
            "((Specimen.extension:festgestellteDiagnose).value[x]).code.coding:icd10-gm",
            lf("sample_snapshot_bioprobe"),
            "Bioprobe",
            [
                "(Specimen.extension.where(url='https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Diagnose').value as Reference)",
                "Extension.value[x]",
                "Condition.code.coding"
            ],
            False
        ),
        (
            "Specimen.collection.bodySite",
            lf("sample_snapshot_bioprobe"),
            "Bioprobe",
            [
                'Specimen.collection.bodySite'
            ],
            False
        ),
        (
            "Specimen.type.coding:sct",
            lf("sample_snapshot_bioprobe"),
            "Bioprobe",
            [
                'Specimen.type.coding'
            ],
            False
        )
    ],
)
def test_translate_element_to_fhir_path_expression (
    element_id: str,
    sample_snapshot: StructureDefinitionSnapshot,
    module_dir_name: str,
    expected: List[str],
    is_composite: bool,
    project: Project
):

    modules_dir = project.input.cso.mkdirs("modules")
    elements = get_element_defining_elements(
        sample_snapshot, element_id, module_dir_name, modules_dir
    )

    result = translate_element_to_fhir_path_expression(sample_snapshot, elements, is_composite)

    assert result == expected
