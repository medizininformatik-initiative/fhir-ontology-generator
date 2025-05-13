import json
import os
import pytest

from cohort_selection_ontology.core.resolvers.querying_metadata import StandardDataSetQueryingMetaDataResolver
from cohort_selection_ontology.core.generators.ui_profile import UIProfileGenerator
from cohort_selection_ontology.model.query_metadata import ResourceQueryingMetaData
from common.util.project import Project
from test.integration.backend.conftest import test_dir


def test_ui_profile_composite_attributes(test_dir):
    test_project_dir = os.path.join(test_dir, "..", "projects_for_testing", "projects", "composite")
    test_project = Project("test-cql-mapping-composite", path=test_project_dir)
    module_dir = os.path.join(test_project_dir, "input", "modules", "ICU")

    resolver = StandardDataSetQueryingMetaDataResolver(test_project)
    generator = UIProfileGenerator(test_project, resolver)

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
