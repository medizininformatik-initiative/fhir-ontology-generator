import json
import unittest

from api.FHIRSearchMappingGenerator import FHIRSearchMappingGenerator
from example.mii_core_data_set.generate_cds import MIICoreDataSetQueryingMetaDataResolver


class UIProfileGeneratorTestCases(unittest.TestCase):
    def test_translate_element_id_to_fhir_search_parameter(self):
        resolver = MIICoreDataSetQueryingMetaDataResolver()
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


if __name__ == '__main__':
    unittest.main()
