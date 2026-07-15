import json
import os
from pathlib import Path

from cohort_selection_ontology.core.resolvers.querying_metadata import (
    StandardDataSetQueryingMetaDataResolver,
)
from cohort_selection_ontology.core.generators.ui_profile import UIProfileGenerator
from cohort_selection_ontology.model.query_metadata import ResourceQueryingMetaData
from common.model.fhir.structure_definition import StructureDefinitionSnapshot
from common.util.project import Project


def test_ui_profile_composite_attributes():
    test_project_dir = Path(os.path.dirname(os.path.realpath(__file__)), "composite")
    test_project = Project("composite", path=test_project_dir)
    module_dir = test_project.input / "modules" / "ICU"

    resolver = StandardDataSetQueryingMetaDataResolver(project=test_project)
    generator = UIProfileGenerator(test_project, querying_meta_data_resolver=resolver)

    with open(
        os.path.join(
            module_dir,
            "differential",
            "package",
            "sd-mii-icu-muv-arterieller-blutdruck-snapshot.json",
        ),
        "r",
        encoding="UTF-8",
    ) as f:
        profile_snapshot = StructureDefinitionSnapshot.model_validate_json(f.read())
    with open(
        os.path.join(
            module_dir,
            "QueryingMetaData",
            "SD_MII_ICU_Arterieller_BlutdruckQueryingMetaData.json",
        ),
        "r",
        encoding="UTF-8",
    ) as f:
        querying_meta_data = ResourceQueryingMetaData.model_validate_json(f.read())

    generator.data_set_dir = Path(os.path.join(module_dir, "differential", "package"))
    generator.module_dir = module_dir
    ui_profile = generator.generate_ui_profile(profile_snapshot, querying_meta_data)

    with open(
        os.path.join(module_dir, "expected", "ui_profile.json"), "r", encoding="UTF-8"
    ) as f:
        expected_ui_profile = json.load(f)
    assert json.loads(ui_profile.to_json()) == expected_ui_profile
