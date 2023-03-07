import json
import unittest

from api.FHIRSearchMappingGenerator import FHIRSearchMappingGenerator
from example.mii_core_data_set.generate_cds import MIICoreDataSetQueryingMetaDataResolver


class MyTestCase(unittest.TestCase):

    def test_complex_specimen_id_to_path_translation(self):
        resolver = MIICoreDataSetQueryingMetaDataResolver()
        mapping_generator = FHIRSearchMappingGenerator(resolver)
        mapping_generator.module_dir = "../../example/mii_core_data_set/resources/fdpg_differential/Bioprobe/"
        mapping_generator.data_set_dir = "../../example/mii_core_data_set/resources/fdpg_differential/"

        with open("../../example/mii_core_data_set/resources/fdpg_differential/Bioprobe/package/"
                  "StructureDefinition-FDPG_Specimen.StructureDefinition-snapshot.json", 'r') as f:
            profile_snapshot = json.load(f)
            actual_fhir_paths = mapping_generator.translate_element_id_to_fhir_path_expressions(
                "((Specimen.extension:festgestellteDiagnose)"
                ".value[x]).code.coding:icd10-gm",
                profile_snapshot)
            expected_fhir_paths = [
                "Specimen.extension.where(url='https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/"
                "StructureDefinition/Diagnose').value",
                'Condition.code']
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
                "MedicationAdministration.medication as Reference", 'Medication.code']
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

        with open("../../example/mii_core_data_set/resources/fdpg_differential/Bioprobe/package/"
                  "StructureDefinition-FDPG_Specimen.StructureDefinition-snapshot.json", 'r') as f:
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
                  "FDPG_Condition_ICD10.StructureDefinition-snapshot.json", 'r') as f:
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
