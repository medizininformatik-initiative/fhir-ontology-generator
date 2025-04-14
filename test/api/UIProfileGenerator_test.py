import json
import unittest

from core.FHIRSearchMappingGenerator import FHIRSearchMappingGenerator
from core.UIProfileGenerator import UIProfileGenerator
from core.resolvers.querying_metadata import StandardDataSetQueryingMetaDataResolver
from core.resolvers.search_parameter import StandardSearchParameterResolver
from model.ResourceQueryingMetaData import ResourceQueryingMetaData
from model.UiDataModel import TermCode, AttributeDefinition
from common.util.project import Project


class UIProfileGeneratorTestCases(unittest.TestCase):
    __project = Project(name="fdpg-ontology")


    def test_translate_element_id_to_fhir_search_parameter(self):
        qmr_resolver = StandardDataSetQueryingMetaDataResolver(self.__project)
        sp_resolver = StandardSearchParameterResolver("Bioprobe")
        mapper = FHIRSearchMappingGenerator(self.__project, qmr_resolver, sp_resolver)
        mapper.data_set_dir = '../../projects/mii_core_data_set/resources/fdpg_differential'
        mapper.module_dir = '../../projects/mii_core_data_set/resources/fdpg_differential/Bioprobe'
        with open('../../projects/mii_core_data_set/resources/fdpg_differential/Bioprobe/package/'
                  'FDPG_Bioprobe-snapshot.json', 'r') as f:
            fhir_path = mapper.translate_element_id_to_fhir_path_expressions(
                '((Specimen.extension:festgestellteDiagnose).value[x]).code.coding:icd10-gm',
                json.load(f), "Bioprobe")
            self.assertEqual(["Specimen.extension.where(url='https://www.medizininformatik-initiative.de/"
                              "fhir/ext/modul-biobank/StructureDefinition/Diagnose').value",
                              "Extension.value as Reference", "Condition.code.coding"], fhir_path)

    def test_generate_ui_profile(self):
        resolver = StandardDataSetQueryingMetaDataResolver(self.__project)
        with open('../../projects/mii_core_data_set/resources/fdpg_differential/Bioprobe/package/'
                  'FDPG_Bioprobe-snapshot.json', 'r') as f:
            profile_snapshot = json.load(f)
            with open('../../projects/mii_core_data_set/resources/QueryingMetaData/SpecimenQueryingMetaData.json',
                      'r') as g:
                querying_meta_data = ResourceQueryingMetaData.from_json(g)
                generator = UIProfileGenerator(self.__project, resolver)
                generator.data_set_dir = '../../projects/mii_core_data_set/resources/fdpg_differential'
                generator.module_dir = '../../projects/mii_core_data_set/resources/fdpg_differential/Bioprobe'
                ui_profile = generator.generate_ui_profile(profile_snapshot, querying_meta_data)
                attribute_code = TermCode("http://hl7.org/fhir/StructureDefinition", "festgestellteDiagnose",
                                          "Festgestellte Diagnose")
                expected_attribute_definition = AttributeDefinition(attribute_code, "reference")
                expected_attribute_definition.optional = True
                expected_attribute_definition.referenceCriteriaSet = "http://fhir.de/ValueSet/bfarm/icd-10-gm"
                self.assertEqual(expected_attribute_definition.__dict__, ui_profile.attribute_definitions[0].__dict__)


if __name__ == '__main__':
    unittest.main()
