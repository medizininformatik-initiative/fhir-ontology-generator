import pytest

from common.model.fhir.structure_definition import StructureDefinitionSnapshot
from common.util.project import Project
from dimp_dup_config.core.dimp_config_functions import (
    DimpConfigGenerator,
    ElementDimpConfig,
    ProfileDimpConfig,
    is_more_specific_keep,
    post_process_profile_dimp_config,
)


@pytest.fixture
def dimp_generator(project: Project) -> DimpConfigGenerator:
    return DimpConfigGenerator(project)


@pytest.mark.parametrize(
    argnames="profile, elem_def, expected_paths",
    argvalues=[
        (
            "https://www.medizininformatik-initiative.de/fhir/core/modul-diagnose/StructureDefinition/Diagnose",
            "Condition.recordedDate",
            ["Condition.recordedDate"],
        ),
        (
            "https://gematik.de/fhir/isik/StructureDefinition/ISiKPatient",
            "Patient.address:Strassenanschrift.country",
            ["Patient.address:Strassenanschrift.country"],
        ),
    ],
    ids=[
        "primitive dateTime - Condition.recordedDate",
        "primitive string - Patient.address.country",
    ],
    indirect=["profile", "elem_def"],
)
def test_generates_keep_for_must_support_primitive(
    profile: StructureDefinitionSnapshot,
    elem_def,
    expected_paths: list[str],
    dimp_generator: DimpConfigGenerator,
):
    result = dimp_generator.generate_dimp_config_for_element(elem_def, profile)

    assert [element.path for element in result] == expected_paths


@pytest.mark.parametrize(
    argnames="profile, elem_def, expected_paths",
    argvalues=[
        (
            "https://gematik.de/fhir/isik/StructureDefinition/ISiKPatient",
            "Patient.gender",
            ["Patient.gender"],
        ),
    ],
    ids=["primitive code binding - Patient.gender"],
    indirect=["profile", "elem_def"],
)
def test_primitive_code_binding_ignores_binding(
    profile: StructureDefinitionSnapshot,
    elem_def,
    expected_paths: list[str],
    dimp_generator: DimpConfigGenerator,
):
    result = dimp_generator.generate_dimp_config_for_element(elem_def, profile)

    assert [element.path for element in result] == expected_paths


@pytest.mark.parametrize(
    argnames="profile, elem_def, expected_paths",
    argvalues=[
        (
            "https://www.medizininformatik-initiative.de/fhir/core/modul-prozedur/StructureDefinition/Procedure",
            "Procedure.performed[x]",
            ["Procedure.performed"],
        ),
    ],
    ids=["polymorphic complex - Procedure.performed[x]"],
    indirect=["profile", "elem_def"],
)
def test_normalizes_polymorphic_keep_path(
    profile: StructureDefinitionSnapshot,
    elem_def,
    expected_paths: list[str],
    dimp_generator: DimpConfigGenerator,
):
    result = dimp_generator.generate_dimp_config_for_element(elem_def, profile)

    assert [element.path for element in result] == expected_paths


@pytest.mark.parametrize(
    argnames="profile, elem_def, expected_paths",
    argvalues=[
        (
            "https://www.medizininformatik-initiative.de/fhir/core/modul-diagnose/StructureDefinition/Diagnose",
            "Condition.code.coding",
            [
                "Condition.code.coding.where(system = 'http://fhir.de/CodeSystem/bfarm/alpha-id')",
                "Condition.code.coding.where(system = 'http://fhir.de/CodeSystem/bfarm/icd-10-gm')",
                "Condition.code.coding.where(system = 'http://snomed.info/sct')",
                "Condition.code.coding.where(system = 'http://www.orpha.net')",
            ],
        ),
    ],
    ids=["sliced coding - Condition.code.coding"],
    indirect=["profile", "elem_def"],
)
def test_coding_keep_paths_do_not_duplicate_coding_segment(
    profile: StructureDefinitionSnapshot,
    elem_def,
    expected_paths: list[str],
    dimp_generator: DimpConfigGenerator,
):
    result = dimp_generator.generate_dimp_config_for_element(elem_def, profile)

    assert sorted(element.path for element in result) == expected_paths
    assert all(".coding.coding" not in element.path for element in result)


@pytest.mark.parametrize(
    argnames="profile, elem_def, expected_paths",
    argvalues=[
        (
            "https://gematik.de/fhir/isik/StructureDefinition/ISiKKontaktGesundheitseinrichtung",
            "Encounter.class",
            [
                "Encounter.class.where(system = 'http://terminology.hl7.org/CodeSystem/v3-ActCode')"
            ],
        ),
    ],
    ids=["bound coding - Encounter.class"],
    indirect=["profile", "elem_def"],
)
def test_coding_binding_generates_system_level_keep_from_package_value_set(
    profile: StructureDefinitionSnapshot,
    elem_def,
    expected_paths: list[str],
    dimp_generator: DimpConfigGenerator,
):
    result = dimp_generator.generate_dimp_config_for_element(elem_def, profile)

    assert [element.path for element in result] == expected_paths


@pytest.mark.parametrize(
    argnames="profile, elem_def, expected_paths",
    argvalues=[
        (
            "https://gematik.de/fhir/isik/StructureDefinition/ISiKAlkoholAbusus",
            "Observation.category",
            [
                "Observation.category.coding.where(system = 'http://terminology.hl7.org/CodeSystem/observation-category')"
            ],
        ),
    ],
    ids=["pattern codeable concept - Observation.category"],
    indirect=["profile", "elem_def"],
)
def test_codeable_concept_pattern_generates_coding_level_keep(
    profile: StructureDefinitionSnapshot,
    elem_def,
    expected_paths: list[str],
    dimp_generator: DimpConfigGenerator,
):
    result = dimp_generator.generate_dimp_config_for_element(elem_def, profile)

    assert [element.path for element in result] == expected_paths


@pytest.mark.parametrize(
    argnames="profile, elem_def, expected_paths",
    argvalues=[
        (
            "https://gematik.de/fhir/isik/StructureDefinition/ISiKDiagnose",
            "Condition.extension",
            [
                "Condition.extension.where(url = 'http://hl7.org/fhir/StructureDefinition/condition-related')"
            ],
        ),
    ],
    ids=["sliced extension base - Condition.extension"],
    indirect=["profile", "elem_def"],
)
def test_extension_slice_base_generates_slice_level_keep(
    profile: StructureDefinitionSnapshot,
    elem_def,
    expected_paths: list[str],
    dimp_generator: DimpConfigGenerator,
):
    result = dimp_generator.generate_dimp_config_for_element(elem_def, profile)

    assert [element.path for element in result] == expected_paths


@pytest.mark.parametrize(
    argnames="profile, elem_def",
    argvalues=[
        (
            "https://gematik.de/fhir/isik/StructureDefinition/ISiKAlkoholAbusus",
            "Observation.component.referenceRange",
        ),
    ],
    ids=["typeless snapshot element - Observation.component.referenceRange"],
    indirect=["profile", "elem_def"],
)
def test_typeless_snapshot_element_is_ignored_without_crashing(
    profile: StructureDefinitionSnapshot,
    elem_def,
    dimp_generator: DimpConfigGenerator,
):
    result = dimp_generator.generate_dimp_config_for_element(elem_def, profile)

    assert result == []


@pytest.mark.parametrize(
    argnames="profile, elem_def",
    argvalues=[
        (
            "https://gematik.de/fhir/isik/StructureDefinition/ISiKBerichtSubSysteme",
            "Composition.relatesTo.target[x]",
        ),
    ],
    ids=["non-must-support multi-type element - Composition.relatesTo.target[x]"],
    indirect=["profile", "elem_def"],
)
def test_non_must_support_multi_type_element_is_ignored_without_crashing(
    profile: StructureDefinitionSnapshot,
    elem_def,
    dimp_generator: DimpConfigGenerator,
):
    result = dimp_generator.generate_dimp_config_for_element(elem_def, profile)

    assert result == []


def test_malformed_package_value_set_is_ignored_without_crashing(
    dimp_generator: DimpConfigGenerator,
):
    result = dimp_generator.get_systems_from_package_value_set(
        "https://gematik.de/fhir/isik/ValueSet/current-smoking-status-uv-ips"
    )

    assert result == []


def test_profile_post_processing_deduplicates_and_removes_parent_keeps():
    profile_config = ProfileDimpConfig(
        url="http://example.org/Profile",
        elements=[
            ElementDimpConfig(path="Patient.gender"),
            ElementDimpConfig(path="Patient.address.country"),
            ElementDimpConfig(path="Patient.address"),
            ElementDimpConfig(path="Patient.address.country"),
        ],
    )

    result = post_process_profile_dimp_config(profile_config)

    assert [element.path for element in result.elements] == [
        "Patient.address.country",
        "Patient.gender",
    ]


@pytest.mark.parametrize(
    argnames="profile, expected_paths",
    argvalues=[
        (
            "https://www.medizininformatik-initiative.de/fhir/core/modul-diagnose/StructureDefinition/Diagnose",
            {
                "Condition.extension.where(url = 'http://hl7.org/fhir/StructureDefinition/condition-related')",
                "Condition.code.coding.where(system = 'http://fhir.de/CodeSystem/bfarm/icd-10-gm')",
                "Condition.recordedDate",
            },
        ),
        (
            "https://www.medizininformatik-initiative.de/fhir/core/modul-prozedur/StructureDefinition/Procedure",
            {
                "Procedure.code.coding.where(system = 'http://fhir.de/CodeSystem/bfarm/ops')",
                "Procedure.extension.where(url = 'http://fhir.de/StructureDefinition/ProzedurDokumentationsdatum')",
                "Procedure.performed",
            },
        ),
    ],
    ids=["diagnose", "procedure"],
    indirect=["profile"],
)
def test_generated_profile_contains_representative_paths_without_structural_regressions(
    profile: StructureDefinitionSnapshot,
    expected_paths: set[str],
    dimp_generator: DimpConfigGenerator,
):
    result = dimp_generator.generate_dimp_config_for_profile(profile)
    paths = [element.path for element in result.elements]

    assert expected_paths.issubset(paths)
    assert paths == sorted(paths)
    assert len(paths) == len(set(paths))
    assert all(".coding.coding" not in path for path in paths)
    assert not any(
        first is not second and is_more_specific_keep(first, second)
        for first in result.elements
        for second in result.elements
    )


def test_generated_dimp_config_has_final_redact_rule_and_stable_order(
    dimp_generator: DimpConfigGenerator,
):
    result = dimp_generator.generate_dimp_config()

    assert result.profiles_configs[-1].elements == [
        ElementDimpConfig(path="Resource", method="redact")
    ]

    profile_urls = [profile.url for profile in result.profiles_configs[:-1]]
    assert profile_urls == sorted(profile_urls)

    dimp_format = result.to_dimp_format()
    assert dimp_format[-1] == {"path": "Resource", "method": "redact"}
