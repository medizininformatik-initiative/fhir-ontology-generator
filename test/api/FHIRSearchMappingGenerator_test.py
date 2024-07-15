import json
import unittest

from core.FHIRSearchMappingGenerator import FHIRSearchMappingGenerator
from example.mii_core_data_set.generate_cds import MIICoreDataSetQueryingMetaDataResolver
from example.gecco.generate_gecco import GeccoDataSetQueryingMetaDataResolver, GeccoSearchParameterResolver


class MyTestCase(unittest.TestCase):

    # def test_resolve_composite_code_quantity_search_parameter(self):
    #     resolver = GeccoDataSetQueryingMetaDataResolver
    #     gecco_search_parameter_resolver = GeccoSearchParameterResolver()
    #     mapping_generator = FHIRSearchMappingGenerator(resolver)
    #     mapping_generator.module_dir = "../../example/gecco/resources/differential/gecco/"
    #     mapping_generator.data_set_dir = "../../example/gecco/resources/differential/"
    #     with open("../../example/gecco/resources/differential/gecco/package/Profile-Observation-BloodPressure-snapshot.json") as f:
    #         profile_snapshot = json.load(f)
    #         actual_search_parameter = mapping_generator.resolve_fhir_search_parameter(
    #             "Observation.component.where(Observation.component:systolicBloodPressure.code):systolicBloodPressure.value[x]",
    #             profile_snapshot, "composite")
    #         print(actual_search_parameter)
    #         expected_search_parameter = [
    #             "component-code-value-quantity"]
    #         self.assertEqual(expected_search_parameter, actual_search_parameter)  # add assertion here


    def test_complex_specimen_id_to_path_translation(self):
        resolver = MIICoreDataSetQueryingMetaDataResolver()
        mapping_generator = FHIRSearchMappingGenerator(resolver)
        mapping_generator.module_dir = "../../example/mii_core_data_set/resources/fdpg_differential/Bioprobe/"
        mapping_generator.data_set_dir = "../../example/mii_core_data_set/resources/fdpg_differential/"

        with open('../../example/mii_core_data_set/resources/fdpg_differential/Bioprobe/package/'
                  'FDPG_Bioprobe-snapshot.json', 'r') as f:
            profile_snapshot = json.load(f)
            actual_fhir_paths = mapping_generator.translate_element_id_to_fhir_path_expressions(
                "((Specimen.extension:festgestellteDiagnose)"
                ".value[x]).code.coding:icd10-gm",
                profile_snapshot)
            expected_fhir_paths = [
                "Specimen.extension.where(url='https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/"
                "StructureDefinition/Diagnose').value", 'Extension.value as Reference',
                'Condition.code.coding']
            self.assertEqual(expected_fhir_paths, actual_fhir_paths)  # add assertion here

    def test_complex_medication_administration_id_to_path_translation(self):
        resolver = MIICoreDataSetQueryingMetaDataResolver()
        mapping_generator = FHIRSearchMappingGenerator(resolver)
        mapping_generator.module_dir = "../../example/mii_core_data_set/resources/fdpg_differential/" \
                                       "Medikamentenverabreichung/"
        mapping_generator.data_set_dir = "../../example/mii_core_data_set/resources/fdpg_differential/"

        with open("../../example/mii_core_data_set/resources/fdpg_differential/Medikamentenverabreichung/package/"
                  "ABIDE_MedicationAdministration_Ref.StructureDefinition-snapshot.json", 'r', encoding="utf-8") as f:
            profile_snapshot = json.load(f)
            actual_fhir_paths = mapping_generator.translate_element_id_to_fhir_path_expressions(
                "(MedicationAdministration.medication[x]:medicationReference).code.coding:atcClassDe",
                profile_snapshot)
            expected_fhir_paths = [
                "MedicationAdministration.medication as Reference", 'Medication.code.coding']
            self.assertEqual(expected_fhir_paths, actual_fhir_paths)  # add assertion here

    def test_resolve_fhir_search_parameter_medication_administration(self):
        resolver = MIICoreDataSetQueryingMetaDataResolver()
        mapping_generator = FHIRSearchMappingGenerator(resolver)
        mapping_generator.module_dir = "../../example/mii_core_data_set/resources/fdpg_differential/" \
                                       "Medikamentenverabreichung/"
        mapping_generator.data_set_dir = "../../example/mii_core_data_set/resources/fdpg_differential/"

        with open("../../example/mii_core_data_set/resources/fdpg_differential/Medikamentenverabreichung/package/"
                  "ABIDE_MedicationAdministration_Ref.StructureDefinition-snapshot.json", 'r', encoding="utf-8") as f:
            profile_snapshot = json.load(f)
            actual_search_parameter = mapping_generator.resolve_fhir_search_parameter(
                "(MedicationAdministration.medication[x]:medicationReference).code.coding:atcClassDe",
                profile_snapshot)
            print(actual_search_parameter)
            expected_search_parameter = [
                "medication", 'code']
            self.assertEqual(expected_search_parameter, actual_search_parameter)  # add assertion here

    def test_resolve_fhir_search_parameter_specimen(self):
        resolver = MIICoreDataSetQueryingMetaDataResolver()
        mapping_generator = FHIRSearchMappingGenerator(resolver)
        mapping_generator.module_dir = "../../example/mii_core_data_set/resources/fdpg_differential/Bioprobe/"
        mapping_generator.data_set_dir = "../../example/mii_core_data_set/resources/fdpg_differential/"

        with open('../../example/mii_core_data_set/resources/fdpg_differential/Bioprobe/package/'
                  'FDPG_Bioprobe-snapshot.json', 'r') as f:
            profile_snapshot = json.load(f)
            actual_search_parameter = mapping_generator.resolve_fhir_search_parameter(
                "((Specimen.extension:festgestellteDiagnose)"
                ".value[x]).code.coding:icd10-gm",
                profile_snapshot)
            print(actual_search_parameter)
            expected_search_parameter = [
                "diagnose", 'code']
            self.assertEqual(expected_search_parameter, actual_search_parameter)  # add assertion here

    def test_resolve_fhir_search_parameter_condition_on_set(self):
        resolver = MIICoreDataSetQueryingMetaDataResolver()
        mapping_generator = FHIRSearchMappingGenerator(resolver)
        mapping_generator.module_dir = "../../example/mii_core_data_set/resources/fdpg_differential/Diagnose/"
        mapping_generator.data_set_dir = "../../example/mii_core_data_set/resources/fdpg_differential/"

        with open("../../example/mii_core_data_set/resources/fdpg_differential/Diagnose/package/"
                  "FDPG_Diagnose-snapshot.json", 'r') as f:
            profile_snapshot = json.load(f)
            actual_search_parameter = mapping_generator.resolve_fhir_search_parameter(
                "Condition.onset[x]",
                profile_snapshot)
            print(actual_search_parameter)
            expected_search_parameter = [
                "onset-date"]
            self.assertEqual(expected_search_parameter, actual_search_parameter)


if __name__ == '__main__':
    unittest.main()
