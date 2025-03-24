import json
import unittest

from core.FHIRSearchMappingGenerator import FHIRSearchMappingGenerator
from core.UIProfileGenerator import UIProfileGenerator
from example.mii_core_data_set.generate_ontology import StandardDataSetQueryingMetaDataResolver
from model.ResourceQueryingMetaData import ResourceQueryingMetaData
from model.UiDataModel import TermCode, AttributeDefinition


class UIProfileGeneratorTestCases(unittest.TestCase):
    def test_translate_element_id_to_fhir_search_parameter(self):
        resolver = StandardDataSetQueryingMetaDataResolver()
        mapper = FHIRSearchMappingGenerator(resolver)
        mapper.data_set_dir = '../../example/mii_core_data_set/resources/fdpg_differential'
        mapper.module_dir = '../../example/mii_core_data_set/resources/fdpg_differential/Bioprobe'
        with open('../../example/mii_core_data_set/resources/fdpg_differential/Bioprobe/package/'
                  'FDPG_Bioprobe-snapshot.json', 'r') as f:
            fhir_path = mapper.translate_element_id_to_fhir_path_expressions(
                '((Specimen.extension:festgestellteDiagnose).value[x]).code.coding:icd10-gm',
                json.load(f))
            self.assertEqual(["Specimen.extension.where(url='https://www.medizininformatik-initiative.de/"
                              "fhir/ext/modul-biobank/StructureDefinition/Diagnose').value",
                              "Extension.value as Reference", "Condition.code.coding"], fhir_path)

    def test_generate_ui_profile(self):
        resolver = StandardDataSetQueryingMetaDataResolver()
        with open('../../example/mii_core_data_set/CDS_Module/Bioprobe/differential/package/FDPG_Bioprobe-snapshot.json', 'r') as f:
            profile_snapshot = json.load(f)
            with open('../../example/mii_core_data_set/CDS_Module/Bioprobe/QueryingMetaData/SpecimenQueryingMetaData.json',
                      'r') as g:
                querying_meta_data = ResourceQueryingMetaData.from_json(g)
                generator = UIProfileGenerator(resolver)
                generator.data_set_dir = '../../example/mii_core_data_set/CDS_Module'
                generator.module_dir = '../../example/mii_core_data_set/CDS_Module/Bioprobe/differential/package'
                ui_profile = generator.generate_ui_profile(profile_snapshot, querying_meta_data)

                print(ui_profile)

                attribute_code = TermCode("http://hl7.org/fhir/StructureDefinition", "festgestellteDiagnose",
                                          "Festgestellte Diagnose")
                expected_attribute_definition = AttributeDefinition(attribute_code, "reference")
                expected_attribute_definition.optional = True
                expected_attribute_definition.referenceCriteriaSet = "http://fhir.de/ValueSet/bfarm/icd-10-gm"
                self.assertEqual(expected_attribute_definition.__dict__, ui_profile.attribute_definitions[0].__dict__)


if __name__ == '__main__':
    unittest.main()
