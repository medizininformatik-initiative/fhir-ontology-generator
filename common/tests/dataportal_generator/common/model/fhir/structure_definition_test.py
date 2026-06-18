import pytest

from dataportal_generator.common.model.fhir.idx_structure_definition import (
    IdxStructureDefinition,
)


class TestIdxStructureDefinition:
    @pytest.mark.parametrize(
        argnames=["struct_def", "elem_def_id", "present"],
        argvalues=[
            pytest.param("MII_PR_Diagnose_Condition", "Condition.code.coding", True),
            pytest.param("MII_PR_Biobank_Specimen_Bioprobe", "Specimen.code", False),
            pytest.param("MII_PR_Biobank_Specimen_Bioprobe", "Specimen.type", True),
            pytest.param(
                "MII_PR_Biobank_Specimen_Bioprobe", "Specimen.type.coding", True
            ),
            pytest.param(
                "MII_PR_Biobank_Specimen_Bioprobe", "Specimen.type.coding:sct", True
            ),
            pytest.param(
                "MII_PR_Biobank_Specimen_Bioprobe",
                "Specimen.collection.bodySite.coding",
                True,
            ),
            pytest.param(
                "MII_PR_Biobank_Specimen_Bioprobe",
                "Specimen.collection.bodySite.coding:sct",
                True,
            ),
        ],
        indirect=["struct_def"],
    )
    def test_get_element_by_id(
        self,
        struct_def: IdxStructureDefinition,
        elem_def_id: str,
        present: bool,
    ):
        elem_def = struct_def.get_element_by_id(elem_def_id)
        assert bool(elem_def) == present
        if present:
            assert elem_def.id == elem_def_id
            match = next(
                filter(lambda ed: ed.id == elem_def_id, struct_def.snapshot.element)
            )
            assert (
                match.id == elem_def.id
            ), "The lookup should return the same results as list filtering"

    @pytest.mark.parametrize(
        argnames=["struct_def", "elem_path", "present"],
        argvalues=[
            pytest.param("MII_PR_Biobank_Specimen_Bioprobe", "Specimen", True),
            pytest.param(
                "MII_PR_Biobank_Specimen_Bioprobe",
                "Specimen.collection.bodySite.coding",
                True,
            ),
            pytest.param(
                "MII_PR_Biobank_Specimen_Bioprobe",
                "Specimen.collection.bodySite.coding.id",
                True,
            ),
            pytest.param(
                "MII_PR_Biobank_Specimen_Bioprobe",
                "Specimen.collection.bodySite.coding:sct.id",
                False,
            ),
        ],
        indirect=["struct_def"],
    )
    def test_sds_get_elements_by_path(
        self,
        struct_def: IdxStructureDefinition,
        elem_path: str,
        present: bool,
    ):
        elem_defs = struct_def.get_element_by_path(elem_path)
        assert bool(elem_defs) == present
        if present:
            errors = list()
            for ed in elem_defs:
                try:
                    assert ed.path == elem_path
                except AssertionError as err:
                    errors.append(err)
            if errors:
                raise ExceptionGroup(
                    "Path-based element definition lookup returned unexpected results",
                    errors,
                )
        matches = list(
            filter(lambda ed: ed.path == elem_path, struct_def.snapshot.element)
        )
        ids = set(ed.id for ed in matches)
        assert len(matches) == len(
            elem_defs
        ), "The lookup should return the same number of matching element definitions"
        assert all(
            ed.id in ids for ed in elem_defs
        ), "The lookup should return the same results as list filtering"


# def test_sds_get_multiple_elements(
#     sample_snapshot_bioprobe: StructureDefinitionSnapshot, fdpg_project: Project
# ):
#     chained_element_id = (
#         "((Specimen.extension:festgestellteDiagnose).value[x]).code.coding:icd10-gm"
#     )
#     actual_result = get_element_defining_elements_with_source_snapshots(
#         sample_snapshot_bioprobe,
#         chained_element_id,
#         "Bioprobe",
#         fdpg_project.input.cso.path / "modules",
#     )
#
#     p1 = ProcessedElementResult(
#         element=sample_snapshot_bioprobe.get_element_by_id(
#             "Specimen.extension:festgestellteDiagnose"
#         ),
#         profile_snapshot=sample_snapshot_bioprobe,
#         module_dir=fdpg_project.input.cso.path / "modules" / "Bioprobe",
#         last_short_desc=None,
#     )
#
#     p2_snap = structure_definition_from_path(
#         fdpg_project.input.cso.path
#         / "modules"
#         / "Bioprobe"
#         / "differential"
#         / "package"
#         / "extension"
#         / "FDPG_DiagnoseExtension-snapshot.json"
#     )
#     p2 = ProcessedElementResult(
#         element=p2_snap.get_element_by_id("Extension.value[x]"),
#         profile_snapshot=p2_snap,
#         module_dir=fdpg_project.input.cso.path / "modules" / "Bioprobe",
#         last_short_desc=None,
#     )
#     p3_snap = structure_definition_from_path(
#         fdpg_project.input.cso.path
#         / "modules"
#         / "Diagnose"
#         / "differential"
#         / "package"
#         / "StructureDefinition-mii-pr-diagnose-condition-snapshot.json",
#     )
#     p3 = ProcessedElementResult(
#         element=p3_snap.get_element_by_id("Condition.code.coding:icd10-gm"),
#         profile_snapshot=p3_snap,
#         module_dir=fdpg_project.input.cso.path / "modules" / "Diagnose",
#         last_short_desc=None,
#     )
#
#     assert actual_result[0].element.id == p1.element.id
#     assert actual_result[1].element.id == p2.element.id
#     assert actual_result[2].element.id == p3.element.id
#
#
# def test_get_parent_slice_id():
#
#     assert (
#         get_parent_slice_id("Observation.component:Diastolic.code.coding:sct")
#         == "Observation.component:Diastolic.code.coding:sct"
#     )
#     assert (
#         get_parent_slice_id("Observation.component:Diastolic.code.coding")
#         == "Observation.component:Diastolic"
#     )
#     assert get_parent_slice_id("Observation.component") is None
#
#
# @pytest.mark.parametrize(
#     "element_id, polymorphic_elem_prefix, expected, sample_snapshot",
#     [
#         (
#             "Condition.code.coding:icd10-gm.system",
#             "fixed",
#             True,
#             lf("sample_snapshot_diagnose"),
#         ),
#         (
#             "Condition.code.coding:icd10-gm",
#             "pattern",
#             True,
#             lf("sample_snapshot_diagnose"),
#         ),
#         (
#             "Observation.code.coding",
#             "fixed",
#             False,
#             lf("sample_snapshot_diagnose"),
#         ),
#     ],
# )
# def test_sds_find_polymorphic_value(
#     sample_snapshot: StructureDefinitionSnapshot,
#     element_id: str,
#     polymorphic_elem_prefix: str,
#     expected: bool,
# ):
#     elem = sample_snapshot.get_element_by_id(element_id)
#     if expected:
#         assert find_polymorphic_value(elem, polymorphic_elem_prefix) is not None
#     else:
#         assert find_polymorphic_value(elem, polymorphic_elem_prefix) is None
#
#
# @pytest.mark.parametrize(
#     "element_id, expected",
#     [
#         ("Observation.code.coding", False),
#         ("Specimen.code", False),
#         ("Specimen.type", False),
#         ("Specimen.type.coding", False),
#         ("Specimen.type.coding:sct", True),
#         ("Specimen.collection.bodySite.coding", False),
#         ("Specimen.collection.bodySite.coding:sct", True),
#         ("Observation.component:Diastolic", True),
#         ("Observation.component:Diastolic.code", False),
#     ],
# )
# def test_is_element_slice_base(
#     element_id: str,
#     expected: bool,
# ):
#     assert is_element_slice_base(element_id) == expected
#
#
# @pytest.mark.parametrize(
#     "element_id1, element_id2, expected",
#     [
#         (
#             "Observation.component:Systolic.short",
#             "Observation.component:Diastolic.code.short",
#             "Observation.component",
#         ),
#         (
#             "Observation.component:Diastolic.short",
#             "Observation.component:Diastolic.code.short",
#             "Observation.component:Diastolic",
#         ),
#         (
#             "Observation.component",
#             "Observation.component",
#             "Observation.component",
#         ),
#     ],
# )
# def test_common_ancestor_id(
#     element_id1: str,
#     element_id2: str,
#     expected: str,
# ):
#     assert get_common_ancestor_id(element_id1, element_id2) == expected
#
#
# @pytest.mark.parametrize(
#     "profile, elem_def, expected",
#     [
#         (
#             "https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Specimen",
#             "Specimen.collection.bodySite.coding:icd-o-3",
#             "Coding",
#         ),
#         (
#             "https://www.medizininformatik-initiative.de/fhir/core/modul-diagnose/StructureDefinition/Diagnose",
#             "Condition.code.coding:icd10-gm",
#             "Coding",
#         ),
#     ],
#     indirect=["profile", "elem_def"],
# )
# def test_extract_value_type(
#     profile: StructureDefinition,
#     elem_def: ElementDefinition,
#     expected: str,
#     fdpg_project: Project,
# ):
#     assert extract_value_type(elem_def, profile.name) == expected
#
#
# @pytest.mark.parametrize(
#     "sample_snapshot, value_defining_id, expected",
#     [
#         (
#             lf("sample_snapshot_bioprobe"),
#             "((Specimen.extension:festgestellteDiagnose).value[x]).code.coding:icd10-gm",
#             "Condition",
#         )
#     ],
# )
# def test_extract_reference_type(
#     sample_snapshot: StructureDefinitionSnapshot,
#     fdpg_project: Project,
#     value_defining_id: str,
#     expected: str,
# ):
#     modules_dir = fdpg_project.input.cso.path / "modules"
#
#     elements = get_element_defining_elements(
#         sample_snapshot, value_defining_id, "Bioprobe", modules_dir
#     )
#
#     found_reference_type = ""
#
#     for element in elements:
#         for element_type in element.type:
#             if element_type.code == "Reference":
#                 found_reference_type = extract_reference_type(
#                     element_type, modules_dir, sample_snapshot.name
#                 )
#                 break
#     assert found_reference_type == expected
#
#
# @pytest.mark.parametrize(
#     "sample_snapshot, element_id, default, expected_display",
#     [
#         (
#             lf("sample_snapshot_diagnose"),
#             "Condition.code.coding:icd10-gm",
#             "icd10-gm",
#             TranslationDisplayElement(
#                 original="ICD-10-GM Code",
#                 translations=[
#                     Translation(language="de-DE", value="ICD-10-GM Code"),
#                     Translation(language="en-US", value="ICD-10-GM code"),
#                 ],
#             ),
#         ),
#         (
#             lf("sample_snapshot_bioprobe"),
#             "Specimen.collection.bodySite.coding:icd-o-3",
#             "icd-o-3",
#             TranslationDisplayElement(
#                 original="Code defined by a terminology system",
#                 translations=[
#                     Translation(language="de-DE", value=""),
#                     Translation(language="en-US", value=""),
#                 ],
#             ),
#         ),
#     ],
# )
# def test_get_display_from_element_definition(
#     sample_snapshot: StructureDefinitionSnapshot,
#     element_id: str,
#     default: str,
#     expected_display: TranslationDisplayElement,
# ):
#
#     element = sample_snapshot.get_element_by_id(element_id)
#
#     assert get_display_from_element_definition(element, default) == expected_display
#
#
# @pytest.mark.parametrize(
#     "element_id, sample_snapshot, module_dir_name, expected, is_composite",
#     [
#         (
#             "Specimen.collection.collected[x]",
#             lf("sample_snapshot_bioprobe"),
#             "Bioprobe",
#             ["(Specimen.collection.collected as dateTime)"],
#             False,
#         ),
#         (
#             "((Specimen.extension:festgestellteDiagnose).value[x]).code.coding:icd10-gm",
#             lf("sample_snapshot_bioprobe"),
#             "Bioprobe",
#             [
#                 "(Specimen.extension.where(url='https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Diagnose').value as Reference)",
#                 "Extension.value[x]",
#                 "Condition.code.coding",
#             ],
#             False,
#         ),
#         (
#             "Specimen.collection.bodySite",
#             lf("sample_snapshot_bioprobe"),
#             "Bioprobe",
#             ["Specimen.collection.bodySite"],
#             False,
#         ),
#         (
#             "Specimen.type.coding:sct",
#             lf("sample_snapshot_bioprobe"),
#             "Bioprobe",
#             ["Specimen.type.coding"],
#             False,
#         ),
#     ],
# )
# def test_translate_element_to_fhir_path_expression(
#     element_id: str,
#     sample_snapshot: StructureDefinitionSnapshot,
#     module_dir_name: str,
#     expected: List[str],
#     is_composite: bool,
#     fdpg_project: Project,
# ):
#
#     modules_dir = fdpg_project.input.cso.mkdirs("modules")
#     elements = get_element_defining_elements(
#         sample_snapshot, element_id, module_dir_name, modules_dir
#     )
#
#     result = translate_element_to_fhir_path_expression(
#         sample_snapshot, elements, is_composite
#     )
#
#     assert result == expected
