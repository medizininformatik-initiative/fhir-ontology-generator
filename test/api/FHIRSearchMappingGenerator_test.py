import copy
import json
import unittest
from typing import List

from core.CQLMappingGenerator import CQLMappingGenerator
from core.FHIRSearchMappingGenerator import FHIRSearchMappingGenerator
from core.ResourceQueryingMetaDataResolver import ResourceQueryingMetaDataResolver
from core.SearchParameterResolver import SearchParameterResolver
from core.UIProfileGenerator import UIProfileGenerator
from model.MappingDataModel import MapEntryList
from model.ResourceQueryingMetaData import ResourceQueryingMetaData
from model.UiDataModel import TermCode, TermEntry


class TestSearchParameterResolver(SearchParameterResolver):
    def _load_module_search_parameters(self):
        return []


class TestQueryMetaDataResolver(ResourceQueryingMetaDataResolver):
    def __init__(self):
        super().__init__()

    def get_query_meta_data(self, fhir_profile_snapshot: dict, _context: TermCode) -> List[ResourceQueryingMetaData]:
        """
        Implementation as simple look up table.
        :param fhir_profile_snapshot:
        :param _context:
        :return: List of ResourceQueryingMetaData
        """
        result = []
        key = fhir_profile_snapshot.get("name")
        mapping = self._get_query_meta_data_mapping()
        for value in mapping[key]:
            try:
                with open(f"../resources/QueryingMetaData/{value}QueryingMetaData.json", "r") as file:
                    result.append(ResourceQueryingMetaData.from_json(file))
            except FileNotFoundError:
                raise FileNotFoundError(f"{value}QueryingMetaData.json is missing!")
        return result

    @staticmethod
    def _get_query_meta_data_mapping():
        with open("../resources/test_query_meta_data_mapping.json", "r") as f:
            return json.load(f)


def denormalize_mapping(mapping):
    def denormalize_mapping_to_old_format(term_code_to_mapping_name, mapping_name_to_mapping):
        """
        Denormalizes the mapping to the old format

        :param term_code_to_mapping_name: mapping from term codes to mapping names
        :param mapping_name_to_mapping: mappings to use
        :return: denormalized entries
        """
        result = MapEntryList()
        for context_and_term_code, mapping_name in term_code_to_mapping_name.items():
            try:
                mapping = copy.copy(mapping_name_to_mapping[mapping_name])
                mapping.key = context_and_term_code[1]
                mapping.context = context_and_term_code[0]
                result.entries.append(mapping)
            except KeyError:
                print("No mapping found for term code " + context_and_term_code[1].code)
        return result

    return denormalize_mapping_to_old_format(mapping[0], mapping[1])


def denormalize_ui_profile(ui_profile_mapping):
    def denormalize_ui_profile(contextualized_term_code_to_ui_profile_name, ui_profile_name_to_ui_profile):
        for context_and_term_code, ui_profile_name in contextualized_term_code_to_ui_profile_name.items():
            try:
                context, term_code = context_and_term_code
                ui_profile = copy.copy(ui_profile_name_to_ui_profile[ui_profile_name])
                term_entry = TermEntry([term_code], context=context)
                term_entry.id = "0000-0000-0000-0000"
                term_entry.to_v1_entry(ui_profile)
                return term_entry


            except KeyError:
                print("No mapping found for term code " + context_and_term_code[1].code)
    return denormalize_ui_profile(ui_profile_mapping[0], ui_profile_mapping[1])



class MyTestCase(unittest.TestCase):
    def test_composite_fhir_mapping(self):
        resolver = TestQueryMetaDataResolver()
        search_mapping_resolver = TestSearchParameterResolver()
        mapping_generator = FHIRSearchMappingGenerator(resolver, search_mapping_resolver)
        mapping_generator.module_dir = "../resources/Profiles"
        mapping_generator.data_set_dir = "../resources/Profiles"
        with open("../resources/Profiles/Profile-Observation-BloodPressure-snapshot.json") as f:
            profile_snapshot = json.load(f)
            mapping = mapping_generator.generate_normalized_term_code_fhir_search_mapping(profile_snapshot, "Test")
            result_mapping = denormalize_mapping(mapping)
            actual = json.loads(result_mapping.to_json())
            expected = json.loads("""[
            {
                "attributeSearchParameters": [
                    {
                        "attributeKey": {
                            "code": "8480-6",
                            "display": "Systolic blood pressure",
                            "system": "http://loinc.org"
                        },
                        "attributeSearchParameter": "component-code-value-quantity",
                        "attributeType": "composite-quantity",
                        "compositeCode": {
                            "code": "8480-6",
                            "display": "Systolic blood pressure",
                            "system": "http://loinc.org"
                        }
                    },
                    {
                        "attributeKey": {
                            "code": "8462-4",
                            "display": "Diastolic blood pressure",
                            "system": "http://loinc.org"
                        },
                        "attributeSearchParameter": "component-code-value-quantity",
                        "attributeType": "composite-quantity",
                        "compositeCode": {
                            "code": "8462-4",
                            "display": "Diastolic blood pressure",
                            "system": "http://loinc.org"
                        }
                    }
                ],
                "context": {
                    "code": "BloodPressure",
                    "display": "Blood Pressure",
                    "system": "fdpg.mii.test"
                },
                "fhirResourceType": "Observation",
                "key": {
                    "code": "85354-9",
                    "display": "Blood pressure panel with all children optional",
                    "system": "http://loinc.org"
                },
                "name": "BloodPressure",
                "termCodeSearchParameter": "code"
            }
        ]
        """)
        self.assertEqual(expected, actual)

    def test_composite_cql_mapping(self):
        resolver = TestQueryMetaDataResolver()
        mapping_generator = CQLMappingGenerator(resolver)
        mapping_generator.module_dir = "../resources/Profiles"
        mapping_generator.data_set_dir = "../resources/Profiles"
        with open("../resources/Profiles/Profile-Observation-BloodPressure-snapshot.json") as f:
            profile_snapshot = json.load(f)
            mapping = mapping_generator.generate_normalized_term_code_cql_mapping(profile_snapshot, "Test")
            result_mapping = denormalize_mapping(mapping)
            actual = json.loads(result_mapping.to_json())
            expected = json.loads("""[
            {
                "attributeFhirPaths": [
                    {
                        "attributeKey": {
                            "code": "8480-6",
                            "display": "Systolic blood pressure",
                            "system": "http://loinc.org"
                        },
                        "attributePath": "Observation.component.where(code.coding.exists(system = http://loinc.org and code = 8480-6)).value as Quantity",
                        "attributeType": "Quantity"
                    },
                    {
                        "attributeKey": {
                            "code": "8462-4",
                            "display": "Diastolic blood pressure",
                            "system": "http://loinc.org"
                        },
                        "attributePath": "Observation.component.where(code.coding.exists(system = http://loinc.org and code = 8462-4)).value as Quantity",
                        "attributeType": "Quantity"
                    }
                ],
                "context": {
                    "code": "BloodPressure",
                    "display": "Blood Pressure",
                    "system": "fdpg.mii.test"
                },
                "key": {
                    "code": "85354-9",
                    "display": "Blood pressure panel with all children optional",
                    "system": "http://loinc.org"
                },
                "name": "BloodPressure",
                "resourceType": "Observation"
            }
        ]
        """)
        self.assertEqual(expected, actual)

    def test_composite_ui_profile(self):
        query_meta_data_resolver = TestQueryMetaDataResolver()
        ui_profile_generator = UIProfileGenerator(query_meta_data_resolver)
        ui_profile_generator.module_dir = "../resources/Profiles"
        ui_profile_generator.data_set_dir = "../resources/Profiles"
        with open("../resources/Profiles/Profile-Observation-BloodPressure-snapshot.json") as f:
            profile_snapshot = json.load(f)
            ui_profile = ui_profile_generator.generate_normalized_term_code_ui_profile_mapping(profile_snapshot, "Test")
            result_ui_profile = denormalize_ui_profile(ui_profile)
            actual = json.loads(result_ui_profile.to_json())
            expected = json.loads("""
            {
            "attributeDefinitions": [
                {
                    "allowedUnits": [
                        {
                            "code": "mm[Hg]",
                            "display": "mm[Hg]",
                            "system": "http://unitsofmeasure.org"
                        }
                    ],
                    "attributeCode": {
                        "code": "8480-6",
                        "display": "Systolic blood pressure",
                        "system": "http://loinc.org"
                    },
                    "optional": true,
                    "precision": 1,
                    "type": "composite"
                },
                {
                    "allowedUnits": [
                        {
                            "code": "mm[Hg]",
                            "display": "mm[Hg]",
                            "system": "http://unitsofmeasure.org"
                        }
                    ],
                    "attributeCode": {
                        "code": "8462-4",
                        "display": "Diastolic blood pressure",
                        "system": "http://loinc.org"
                    },
                    "optional": true,
                    "precision": 1,
                    "type": "composite"
                }
            ],
            "context": {
                "code": "BloodPressure",
                "display": "Blood Pressure",
                "system": "fdpg.mii.test"
            },
            "display": "Blood pressure panel with all children optional",
            "id": "0000-0000-0000-0000",
            "leaf": true,
            "name": "BloodPressure",
            "selectable": true,
            "termCodes": [
                {
                    "code": "85354-9",
                    "display": "Blood pressure panel with all children optional",
                    "system": "http://loinc.org"
                }
            ],
            "timeRestrictionAllowed": false
        }
        """)

        self.assertEqual(actual, expected)


    # def test_complex_specimen_id_to_path_translation(self):
    #     resolver = MIICoreDataSetQueryingMetaDataResolver()
    #     mapping_generator = FHIRSearchMappingGenerator(resolver)
    #     mapping_generator.module_dir = "../../example/mii_core_data_set/resources/fdpg_differential/Bioprobe/"
    #     mapping_generator.data_set_dir = "../../example/mii_core_data_set/resources/fdpg_differential/"
    #
    #     with open('../../example/mii_core_data_set/resources/fdpg_differential/Bioprobe/package/'
    #               'FDPG_Bioprobe-snapshot.json', 'r') as f:
    #         profile_snapshot = json.load(f)
    #         actual_fhir_paths = mapping_generator.translate_element_id_to_fhir_path_expressions(
    #             "((Specimen.extension:festgestellteDiagnose)"
    #             ".value[x]).code.coding:icd10-gm",
    #             profile_snapshot)
    #         expected_fhir_paths = [
    #             "Specimen.extension.where(url='https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/"
    #             "StructureDefinition/Diagnose').value", 'Extension.value as Reference',
    #             'Condition.code.coding']
    #         self.assertEqual(expected_fhir_paths, actual_fhir_paths)  # add assertion here
    #
    # def test_complex_medication_administration_id_to_path_translation(self):
    #     resolver = MIICoreDataSetQueryingMetaDataResolver()
    #     mapping_generator = FHIRSearchMappingGenerator(resolver)
    #     mapping_generator.module_dir = "../../example/mii_core_data_set/resources/fdpg_differential/" \
    #                                    "Medikamentenverabreichung/"
    #     mapping_generator.data_set_dir = "../../example/mii_core_data_set/resources/fdpg_differential/"
    #
    #     with open("../../example/mii_core_data_set/resources/fdpg_differential/Medikamentenverabreichung/package/"
    #               "ABIDE_MedicationAdministration_Ref.StructureDefinition-snapshot.json", 'r', encoding="utf-8") as f:
    #         profile_snapshot = json.load(f)
    #         actual_fhir_paths = mapping_generator.translate_element_id_to_fhir_path_expressions(
    #             "(MedicationAdministration.medication[x]:medicationReference).code.coding:atcClassDe",
    #             profile_snapshot)
    #         expected_fhir_paths = [
    #             "MedicationAdministration.medication as Reference", 'Medication.code.coding']
    #         self.assertEqual(expected_fhir_paths, actual_fhir_paths)  # add assertion here
    #
    # def test_resolve_fhir_search_parameter_medication_administration(self):
    #     resolver = MIICoreDataSetQueryingMetaDataResolver()
    #     mapping_generator = FHIRSearchMappingGenerator(resolver)
    #     mapping_generator.module_dir = "../../example/mii_core_data_set/resources/fdpg_differential/" \
    #                                    "Medikamentenverabreichung/"
    #     mapping_generator.data_set_dir = "../../example/mii_core_data_set/resources/fdpg_differential/"
    #
    #     with open("../../example/mii_core_data_set/resources/fdpg_differential/Medikamentenverabreichung/package/"
    #               "ABIDE_MedicationAdministration_Ref.StructureDefinition-snapshot.json", 'r', encoding="utf-8") as f:
    #         profile_snapshot = json.load(f)
    #         actual_search_parameter = mapping_generator.resolve_fhir_search_parameter(
    #             "(MedicationAdministration.medication[x]:medicationReference).code.coding:atcClassDe",
    #             profile_snapshot)
    #         print(actual_search_parameter)
    #         expected_search_parameter = [
    #             "medication", 'code']
    #         self.assertEqual(expected_search_parameter, actual_search_parameter)  # add assertion here
    #
    # def test_resolve_fhir_search_parameter_specimen(self):
    #     resolver = MIICoreDataSetQueryingMetaDataResolver()
    #     mapping_generator = FHIRSearchMappingGenerator(resolver)
    #     mapping_generator.module_dir = "../../example/mii_core_data_set/resources/fdpg_differential/Bioprobe/"
    #     mapping_generator.data_set_dir = "../../example/mii_core_data_set/resources/fdpg_differential/"
    #
    #     with open('../../example/mii_core_data_set/resources/fdpg_differential/Bioprobe/package/'
    #               'FDPG_Bioprobe-snapshot.json', 'r') as f:
    #         profile_snapshot = json.load(f)
    #         actual_search_parameter = mapping_generator.resolve_fhir_search_parameter(
    #             "((Specimen.extension:festgestellteDiagnose)"
    #             ".value[x]).code.coding:icd10-gm",
    #             profile_snapshot)
    #         print(actual_search_parameter)
    #         expected_search_parameter = [
    #             "diagnose", 'code']
    #         self.assertEqual(expected_search_parameter, actual_search_parameter)  # add assertion here
    #
    # def test_resolve_fhir_search_parameter_condition_on_set(self):
    #     resolver = MIICoreDataSetQueryingMetaDataResolver()
    #     mapping_generator = FHIRSearchMappingGenerator(resolver)
    #     mapping_generator.module_dir = "../../example/mii_core_data_set/resources/fdpg_differential/Diagnose/"
    #     mapping_generator.data_set_dir = "../../example/mii_core_data_set/resources/fdpg_differential/"
    #
    #     with open("../../example/mii_core_data_set/resources/fdpg_differential/Diagnose/package/"
    #               "FDPG_Diagnose-snapshot.json", 'r') as f:
    #         profile_snapshot = json.load(f)
    #         actual_search_parameter = mapping_generator.resolve_fhir_search_parameter(
    #             "Condition.onset[x]",
    #             profile_snapshot)
    #         print(actual_search_parameter)
    #         expected_search_parameter = [
    #             "onset-date"]
    #         self.assertEqual(expected_search_parameter, actual_search_parameter)


if __name__ == '__main__':
    unittest.main()
