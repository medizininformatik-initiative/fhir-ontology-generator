import json
import os
import unittest

from core.CQLMappingGenerator import CQLMappingGenerator
from core.ResourceQueryingMetaDataResolver import ResourceQueryingMetaDataResolver
from core.UIProfileGenerator import UIProfileGenerator
from example.mii_core_data_set.generate_ontology import StandardDataSetQueryingMetaDataResolver
from model.MappingDataModel import CQLMapping
from model.ResourceQueryingMetaData import ResourceQueryingMetaData


class CompositeTestCases(unittest.TestCase):
    def test_cql_composite_attributes(self):
        resolver = StandardDataSetQueryingMetaDataResolver()
        cql_generator = CQLMappingGenerator(resolver)

        with open(os.path.join("module", "ICU", "expected","cql_mapping.json")) as f:
            expected = json.load(f)
            if expected.get("key"):
                # key is optional, compatability with v1
                del expected["key"]

        with open(os.path.join("module", "ICU", "QueryingMetaData",
                               "SD_MII_ICU_Arterieller_BlutdruckQueryingMetaData.json")) as f:
            querying_meta_data = ResourceQueryingMetaData.from_json(f)

        with open(os.path.join("module", "ICU", "differential", "package",
                               "sd-mii-icu-muv-arterieller-blutdruck-snapshot.json"), 'r', encoding="utf-8") as f:
            profile_snapshot = json.load(f)

        cql_mapping = cql_generator.generate_cql_mapping(profile_snapshot, querying_meta_data)
        cql_mapping.context = querying_meta_data.context
        cql_mapping_json = json.loads(cql_mapping.to_json())
        # sometimes the types are not in alphabetical order
        if cql_mapping_json.get("timeRestriction").get("type"):
            cql_mapping_json["timeRestriction"]["type"].sort()

        self.assertEqual(expected,cql_mapping_json)

    def test_ui_profile_composite_attributes(self):
        resolver = StandardDataSetQueryingMetaDataResolver()
        generator = UIProfileGenerator(resolver)

        with open(os.path.join("module","ICU","differential","package","sd-mii-icu-muv-arterieller-blutdruck-snapshot.json"), 'r', encoding="UTF-8") as f:
            profile_snapshot = json.load(f)
        with open(os.path.join("module","ICU","QueryingMetaData","SD_MII_ICU_Arterieller_BlutdruckQueryingMetaData.json"), 'r', encoding="UTF-8") as f:
            querying_meta_data = ResourceQueryingMetaData.from_json(f)

        generator.data_set_dir = os.path.join("module","ICU","differential","package")
        generator.module_dir = os.path.join("module","ICU")
        ui_profile = generator.generate_ui_profile(profile_snapshot, querying_meta_data)

        print(ui_profile.to_json())

        with open(os.path.join("module","ICU","expected","ui_profile.json"), 'r', encoding="UTF-8") as f:
            expected_ui_profile = json.load(f)
        self.assertEqual(json.loads(ui_profile.to_json()), expected_ui_profile)

    if __name__ == '__main__':
        unittest.main()
