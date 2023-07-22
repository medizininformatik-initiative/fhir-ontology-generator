import json
import unittest

from api.StrucutureDefinitionParser import get_element_defining_elements


class StructureDefinitionParserTestCase(unittest.TestCase):
    @unittest.skip("Not implemented yet")
    def test_get_element_defining_elements(self):
        with open("../../example/mii_core_data_set/resources/fdpg_differential/Laboruntersuchung/package/"
                  "FDPG_Observation_Digitoxin-snapshot.json", 'r') as f:
            profile = json.load(f)
            for element in profile.get("snapshot").get("element"):
                element_id = element.get("id")
                if not element_id:
                    continue
                if not element_id.startswith("Observation"):
                    continue
                if not "." in element_id:
                    continue
                print(element_id)
                resolved_element = get_element_defining_elements(element_id, profile,
                                                                 "../../example/mii_core_data_set/resources/"
                                                                 "fdpg_differential/Laboruntersuchung",
                                                                 "../../example/mii_core_data_set/resources/"
                                                                 "fdpg_differential")
                self.assertEqual(element, resolved_element[0])

    def test_get_element_defining_elements_complex(self):
        with open('../../example/mii_core_data_set/resources/fdpg_differential/Bioprobe/package/'
                  'FDPG_Bioprobe-snapshot.json', 'r') as f:
            profile = json.load(f)
            resolved_element = get_element_defining_elements("((Specimen.extension:festgestellteDiagnose).value[x])"
                                                             ".code.coding:icd10-gm", profile,
                                                             "../../example/mii_core_data_set/resources/"
                                                             "fdpg_differential/Bioprobe",
                                                             "../../example/mii_core_data_set/resources/"
                                                             "fdpg_differential")
            self.assertEqual(resolved_element[0].get("id"), "Specimen.extension:festgestellteDiagnose")
            self.assertEqual(resolved_element[1].get("id"), "Extension.value[x]")
            self.assertEqual(resolved_element[2].get("id"), "Condition.code.coding:icd10-gm")


if __name__ == '__main__':
    unittest.main()
