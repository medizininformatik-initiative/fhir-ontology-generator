from pathlib import Path

from common.util.functions import first
from common.util.structure_definition.functions import (
    get_profiles_with_base_definition,
    parse,
)


def test_get_profiles_with_base_definition(modules_dir: Path):
    profiles = [
        *get_profiles_with_base_definition(
            modules_dir, "http://organization.org/fhir/StructureDefinition/Condition"
        )
    ]
    assert len(profiles) == 3
    assert first(
        profiles, lambda t: t[0].name == "Condition"
    ), "StructureDefinition instances with matching values in the 'url' element should be returned"
    assert first(profiles, lambda t: t[0].name == "constrained-condition1"), (
        "StructureDefinition instances constraining or specializing the profile identified by provided url should be "
        "returned"
    )
    assert first(
        profiles, lambda t: t[0].name == "condition2"
    ), "StructureDefinition instances matching the type should be returned"


def test_parse():
    path = "Resource.extension:slice1.value[x]"
    element_ids = parse(path)
    assert (
        isinstance(element_ids, list) and len(element_ids) == 2
    ), "Parsing a path navigating across the 'extension' element should result in at two element IDs being returned"
    assert element_ids[0] == "Resource.extension:slice1"
    assert element_ids[1] == "value[x]"

    path = "Resource.element1.resolve().element2.element3"
    element_ids = parse(path)
    assert (
        isinstance(element_ids, list) and len(element_ids) == 2
    ), "Parsing a path with a reference resolution should result in two element IDs being returned"
    assert element_ids[0] == "Resource.element1"
    assert element_ids[1] == "element2.element3"
