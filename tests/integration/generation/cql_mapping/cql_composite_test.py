import json
import os
import pytest

from cohort_selection_ontology.core.generators.cql import CQLMappingGenerator
from cohort_selection_ontology.core.resolvers.querying_metadata import StandardDataSetQueryingMetaDataResolver
from cohort_selection_ontology.model.query_metadata import ResourceQueryingMetaData
from common.util.project import Project


def test_cql_composite_attributes():
    test_dir = os.path.dirname(os.path.realpath(__file__))

    test_project_dir = os.path.join(test_dir, "composite")
    test_project = Project("composite", path=test_project_dir)
    module_dir = test_project.input.cso / "modules" / "ICU"

    with open(module_dir / "expected" / "cql_mapping.json") as f:
        expected = json.load(f)
        if expected.get("key"):
            # key is optional, compatibility with v1
            del expected["key"]

    with open(module_dir / "QueryingMetaData" / "SD_MII_ICU_Arterieller_BlutdruckQueryingMetaData.json") as f:
        querying_meta_data = ResourceQueryingMetaData.from_json(f)

    with open(module_dir / "differential" / "package" / "sd-mii-icu-muv-arterieller-blutdruck-snapshot.json", 'r',
              encoding="utf-8") as f:
        profile_snapshot = json.load(f)

    resolver = StandardDataSetQueryingMetaDataResolver(test_project)
    cql_generator = CQLMappingGenerator(test_project, resolver)

    cql_mapping = cql_generator.generate_cql_mapping(profile_snapshot, querying_meta_data, "ICU")
    cql_mapping.context = querying_meta_data.context
    cql_mapping_json = json.loads(cql_mapping.to_json())
    # sometimes the types are not in alphabetical order
    if cql_mapping_json.get("timeRestriction").get("types"):
        cql_mapping_json["timeRestriction"]["types"].sort()
    if expected.get("timeRestriction").get("types"):
        expected["timeRestriction"]["types"].sort()

    assert (cql_mapping_json == expected)