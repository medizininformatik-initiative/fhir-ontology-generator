import json
import os


from cohort_selection_ontology.core.generators.cql import CQLMappingGenerator
from cohort_selection_ontology.core.resolvers.querying_metadata import ResourceQueryingMetaDataResolver, StandardDataSetQueryingMetaDataResolver
from cohort_selection_ontology.core.generators.ui_profile import UIProfileGenerator
from cohort_selection_ontology.model.mapping import CQLMapping
from cohort_selection_ontology.model.query_metadata import ResourceQueryingMetaData
from common.util.project import Project


def test_cql_composite_attributes(test_dir):
    test_project_dir = os.path.join(test_dir, "..", "projects_for_testing", "projects", "composite")
    test_project = Project("test-cql-mapping-composite",path=test_project_dir)
    module_dir = os.path.join(test_project_dir, "input","modules","ICU")

    with open(os.path.join(module_dir, "expected", "cql_mapping.json")) as f:
        expected = json.load(f)
        if expected.get("key"):
            # key is optional, compatability with v1
            del expected["key"]

    with open(os.path.join(module_dir, "QueryingMetaData",
                           "SD_MII_ICU_Arterieller_BlutdruckQueryingMetaData.json")) as f:
        querying_meta_data = ResourceQueryingMetaData.from_json(f)

    with open(os.path.join(module_dir, "differential", "package",
                           "sd-mii-icu-muv-arterieller-blutdruck-snapshot.json"), 'r', encoding="utf-8") as f:
        profile_snapshot = json.load(f)

    # set path so that generate_cql_mapping works as expected
    working_directory = os.path.realpath(os.path.join(test_dir, ".."))
    os.chdir(working_directory)


    resolver = StandardDataSetQueryingMetaDataResolver(test_project)
    cql_generator = CQLMappingGenerator(test_project,resolver)

    cql_mapping = cql_generator.generate_cql_mapping(profile_snapshot, querying_meta_data,"ICU")
    cql_mapping.context = querying_meta_data.context
    cql_mapping_json = json.loads(cql_mapping.to_json())
    # sometimes the types are not in alphabetical order
    if cql_mapping_json.get("timeRestriction").get("types"):
        cql_mapping_json["timeRestriction"]["types"].sort()
    if expected.get("timeRestriction").get("types"):
        expected["timeRestriction"]["types"].sort()

    assert (expected == cql_mapping_json)


def test_ui_profile_composite_attributes(test_dir):
    test_project_dir = os.path.join(test_dir, "..", "projects_for_testing", "projects", "composite")
    test_project = Project("test-cql-mapping-composite", path=test_project_dir)
    module_dir = os.path.join(test_project_dir, "input","modules","ICU")

    resolver = StandardDataSetQueryingMetaDataResolver(test_project)
    generator = UIProfileGenerator(test_project,resolver)

    with open(os.path.join(module_dir, "differential", "package", "sd-mii-icu-muv-arterieller-blutdruck-snapshot.json"),
              'r', encoding="UTF-8") as f:
        profile_snapshot = json.load(f)
    with open(os.path.join(module_dir, "QueryingMetaData", "SD_MII_ICU_Arterieller_BlutdruckQueryingMetaData.json"),
              'r', encoding="UTF-8") as f:
        querying_meta_data = ResourceQueryingMetaData.from_json(f)

    generator.data_set_dir = os.path.join(module_dir, "differential", "package")
    generator.module_dir = module_dir
    ui_profile = generator.generate_ui_profile(profile_snapshot, querying_meta_data)

    with open(os.path.join(module_dir, "expected", "ui_profile.json"), 'r', encoding="UTF-8") as f:
        expected_ui_profile = json.load(f)
    assert (json.loads(ui_profile.to_json()) == expected_ui_profile)
