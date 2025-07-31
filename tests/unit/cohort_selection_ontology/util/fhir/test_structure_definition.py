from pathlib import Path

from cohort_selection_ontology.util.fhir.structure_definition import (
    get_profiles_with_base_definition,
)
from common.util.functions import first


def test_get_profiles_with_base_definition(modules_dir: Path):
    profiles = get_profiles_with_base_definition(
        modules_dir, "http://organization.org/fhir/StructureDefinition/Condition"
    )
    assert len(profiles) == 3
    assert first(
        profiles, lambda t: t[0].get("name") == "Condition"
    ), "StructureDefinition instances with matching values in the 'url' element should be returned"
    assert first(profiles, lambda t: t[0].get("name") == "constrained-condition1"), (
        "StructureDefinition instances constraining or specializing the profile identified by provided url should be "
        "returned"
    )
    assert first(profiles, lambda t: t[0].get("name") == "condition2"), (
        "StructureDefinition instances matching the type " "should be returned"
    )
