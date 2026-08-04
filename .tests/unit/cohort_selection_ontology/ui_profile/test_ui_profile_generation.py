import json
from typing import Dict

import pytest

from cohort_selection_ontology.core.generators.ui_profile import UIProfileGenerator
from cohort_selection_ontology.core.resolvers.querying_metadata import (
    StandardDataSetQueryingMetaDataResolver,
)
from common.model.fhir.structure_definition import StructureDefinitionSnapshot
from common.util.project import Project


@pytest.mark.parametrize(
    argnames=["profile", "attribute_id", "attribute_type", "load_json_file"],
    argvalues=[
        (
            "https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Specimen",
            "Specimen.collection.bodySite.coding:icd-o-3",
            "concept",
            "attr_slice_specified.json",
        ),
        (
            "https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Specimen",
            "Specimen.collection.bodySite.coding",
            "concept",
            "attr_slice_not_specified.json",
        ),
        (
            "https://www.medizininformatik-initiative.de/fhir/ext/modul-onko/StructureDefinition/mii-pr-onko-tnm-t-kategorie",
            "Observation.value[x]",
            "concept",
            "attr_slice_no_existing_slice.json",
        ),
    ],
    ids=[
        "Bioprobe-bodySite:icd-o-3 attr_slice_specified",
        "Bioprobe-bodySite attr_slice_not_specified",
        "TNM-Kategorie-T attr_slice_no_existing_slice",
    ],
    indirect=["profile", "load_json_file"],
)
def test_get_attribute_definition(
    project: Project,
    profile: StructureDefinitionSnapshot,
    attribute_id: str,
    attribute_type: str,
    load_json_file: Dict,
):
    meta_res = StandardDataSetQueryingMetaDataResolver(project=project)
    ui_gen = UIProfileGenerator(project, meta_res)

    ui_profile = ui_gen.get_attribute_definition(
        profile, attribute_id, attribute_type=attribute_type
    )

    print(json.dumps(ui_profile.to_dict(), indent=4))

    assert json.dumps(ui_profile.to_dict(), indent=4) == json.dumps(
        load_json_file, indent=4
    )
