import json
import time
from typing import List

import pytest
from fhir.resources.R4B.elementdefinition import ElementDefinition

from cohort_selection_ontology.core.generators.cql import CQLMappingGenerator
from cohort_selection_ontology.model.mapping import SimpleCardinality
from cohort_selection_ontology.model.ui_data import (
    TranslationDisplayElement,
    Translation,
)
from common.model.structure_definition import (
    StructureDefinitionSnapshot,
    ProcessedElementResult,
)
from common.util.project import Project
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
    find_polymorphic_value,
    select_element_compatible_with_cql_operations,
)


@pytest.mark.parametrize(
    argnames="search_term",
    argvalues=[
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
    actual_result = get_element_defining_elements_with_source_snapshots(
        sample_snapshot_bioprobe,
        chained_element_id,
        "Bioprobe",
        project.input.cso.path / "modules",
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
        get_parent_slice_id("Observation.component:Diastolic.code.coding:sct")
        == "Observation.component:Diastolic.code.coding:sct"
    )
    assert (
        get_parent_slice_id("Observation.component:Diastolic.code.coding")
        == "Observation.component:Diastolic"
    )
    assert get_parent_slice_id("Observation.component") is None


@pytest.mark.parametrize(
    argnames=["elem_def", "polymorphic_elem_prefix", "expected", "profile"],
    argvalues=[
        (
            "Condition.code.coding:icd10-gm.system",
            "fixed",
            True,
            "https://www.medizininformatik-initiative.de/fhir/core/modul-diagnose/StructureDefinition/Diagnose",
        ),
        (
            "Condition.code.coding:icd10-gm",
            "pattern",
            True,
            "https://www.medizininformatik-initiative.de/fhir/core/modul-diagnose/StructureDefinition/Diagnose",
        ),
        (
            "Observation.code.coding",
            "fixed",
            False,
            "https://www.medizininformatik-initiative.de/fhir/core/modul-diagnose/StructureDefinition/Diagnose",
        ),
    ],
    indirect=["elem_def", "profile"],
)
def test_sds_find_polymorphic_value(
    profile: StructureDefinitionSnapshot,
    elem_def: ElementDefinition,
    polymorphic_elem_prefix: str,
    expected: bool,
):
    if expected:
        assert find_polymorphic_value(elem_def, polymorphic_elem_prefix) is not None
    else:
        assert find_polymorphic_value(elem_def, polymorphic_elem_prefix) is None


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
    assert get_common_ancestor_id(element_id1, element_id2) == expected


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
        extract_value_type(attribute_element, sample_snapshot_bioprobe.name) == expected
    )


@pytest.mark.parametrize(
    argnames=["profile", "value_defining_id", "module_name", "expected"],
    argvalues=[
        (
            "https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Specimen",
            "((Specimen.extension:festgestellteDiagnose).value[x]).code.coding:icd10-gm",
            "Bioprobe",
            "Condition",
        )
    ],
    indirect=["profile"],
)
def test_extract_reference_type(
    profile: StructureDefinitionSnapshot,
    project: Project,
    value_defining_id: str,
    module_name: str,
    expected: str,
):
    modules_dir = project.input.cso.path / "modules"

    elements = get_element_defining_elements(
        profile, value_defining_id, module_name, modules_dir
    )

    found_reference_type = ""

    for element in elements:
        for element_type in element.type:
            if element_type.code == "Reference":
                found_reference_type = extract_reference_type(
                    element_type, modules_dir, module_name
                )
                break
    assert found_reference_type == expected


@pytest.mark.parametrize(
    argnames=["profile", "elem_def", "default", "expected_display"],
    argvalues=[
        (
            "https://www.medizininformatik-initiative.de/fhir/core/modul-diagnose/StructureDefinition/Diagnose",
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
            "https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Specimen",
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
    indirect=["elem_def", "profile"],
)
def test_get_display_from_element_definition(
    profile: StructureDefinitionSnapshot,
    elem_def: ElementDefinition,
    default: str,
    expected_display: TranslationDisplayElement,
):

    # element = sample_snapshot.get_element_by_id(element_id)

    assert get_display_from_element_definition(elem_def, default) == expected_display


@pytest.mark.parametrize(
    argnames=["element_id", "profile", "module_dir_name", "expected", "is_composite"],
    argvalues=[
        (
            "Specimen.collection.collected[x]",
            "https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Specimen",
            "Bioprobe",
            ["(Specimen.collection.collected as dateTime)"],
            False,
        ),
        (
            "((Specimen.extension:festgestellteDiagnose).value[x]).code.coding:icd10-gm",
            "https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Specimen",
            "Bioprobe",
            [
                "(Specimen.extension.where(url='https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Diagnose').value as Reference)",
                "Extension.value[x]",
                "Condition.code.coding",
            ],
            False,
        ),
        (
            "Specimen.collection.bodySite",
            "https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Specimen",
            "Bioprobe",
            ["Specimen.collection.bodySite"],
            False,
        ),
        (
            "Specimen.type.coding:sct",
            "https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Specimen",
            "Bioprobe",
            ["Specimen.type.coding"],
            False,
        ),
    ],
    indirect=["profile"],
)
def test_translate_element_to_fhir_path_expression(
    element_id: str,
    profile: StructureDefinitionSnapshot,
    module_dir_name: str,
    expected: List[str],
    is_composite: bool,
    project: Project,
):

    modules_dir = project.input.cso.mkdirs("modules")
    elements = get_element_defining_elements(
        profile, element_id, module_dir_name, modules_dir
    )

    result = translate_element_to_fhir_path_expression(profile, elements, is_composite)

    assert result == expected


@pytest.mark.parametrize(
    argnames="elem_def, profile, expected_el, expected_type, expected_card",
    argvalues=[
        (
            "Specimen.type.coding:sct",
            "https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Specimen",
            "Specimen.type",
            "CodeableConcept",
            SimpleCardinality.SINGLE,
        ),
        (
            "Specimen.extension:festgestellteDiagnose",
            "https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Specimen",
            "Specimen.extension:festgestellteDiagnose",
            "Extension",
            SimpleCardinality.MANY,
        ),
        (
            "Encounter.type:Kontaktebene",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
            "Encounter.type:Kontaktebene",
            "CodeableConcept",
            SimpleCardinality.MANY,
        ),
        (
            "Encounter.type:KontaktArt",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
            "Encounter.type:KontaktArt",
            "CodeableConcept",
            SimpleCardinality.MANY,
        ),
        (
            "Encounter.serviceType.coding:Fachabteilungsschluessel",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
            "Encounter.serviceType",
            "CodeableConcept",
            SimpleCardinality.SINGLE,
        ),
        (
            "Encounter.serviceType.coding:ErweiterterFachabteilungsschluessel",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
            "Encounter.serviceType",
            "CodeableConcept",
            SimpleCardinality.SINGLE,
        ),
        (
            "Observation.component:SystolicBP.code",
            "https://www.medizininformatik-initiative.de/fhir/ext/modul-icu/StructureDefinition/arterieller-blutdruck",
            "Observation.component:SystolicBP.code",
            "CodeableConcept",
            SimpleCardinality.MANY,
        ),
        (
            "MedicationStatement.medication[x]:medicationCodeableConcept.coding:atcClassDe",
            "https://www.medizininformatik-initiative.de/fhir/ext/modul-onko/StructureDefinition/mii-pr-onko-systemische-therapie-medikation",
            "MedicationStatement.medication[x]:medicationCodeableConcept",
            "CodeableConcept",
            SimpleCardinality.SINGLE,
        ),
        (
            "Condition.category:todesDiagnose.coding:loinc",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-person/StructureDefinition/Todesursache",
            "Condition.category:todesDiagnose",
            "CodeableConcept",
            SimpleCardinality.MANY,
        ),
    ],
    ids=[
        "Specimen.type.coding:sct -> Specimen.type",
        "Specimen.extension:festgestellteDiagnose -> Specimen.extension:festgestellteDiagnose",
        "Encounter.type:Kontaktebene -> Encounter.type:Kontaktebene",
        "Encounter.type:KontaktArt -> Encounter.type:KontaktArt",
        "Encounter.serviceType.coding:Fachabteilungsschluessel -> Encounter.serviceType",
        "Encounter.serviceType.coding:ErweiterterFachabteilungsschluessel -> Encounter.serviceType",
        "Observation.component:SystolicBP.code -> Observation.component:SystolicBP.code",
        "MedicationStatement.medication[x]:medicationCodeableConcept.coding:atcClassDe -> MedicationStatement.medication[x]:medicationCodeableConcept",
        "Condition.category:todesDiagnose.coding:loinc -> Condition.category:todesDiagnose",
    ],
    indirect=["elem_def", "profile"],
)
def test_select_element_compatible_with_cql_operations(
    project: Project,
    elem_def: ElementDefinition,
    profile: StructureDefinitionSnapshot,
    expected_el: str,
    expected_type: str,
    expected_card: SimpleCardinality,
):
    if elem_def is None:
        pytest.fail(f"No element with id: {elem_def} in snapshot {profile.name}")

    assert (
        CQLMappingGenerator.aggregate_cardinality_using_element(
            element=elem_def, snapshot=profile
        )
        == expected_card
    )

    # something aint right here. see prameter list
    el_id, el_type = select_element_compatible_with_cql_operations(elem_def, profile)

    assert el_id.id == profile.get_element_by_id(expected_el).id
    assert el_type == {expected_type}
