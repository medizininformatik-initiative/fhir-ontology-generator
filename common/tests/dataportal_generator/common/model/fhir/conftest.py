from collections.abc import Mapping
from pathlib import Path

import pytest

from dataportal_generator.common.model.fhir.idx_structure_definition import (
    IdxStructureDefinition,
)


@pytest.fixture(scope="module")
def struct_def_map(resources: Path) -> Mapping[str, IdxStructureDefinition]:
    lookup = dict()
    struct_def_dir = resources / "structure_definitions"
    for struct_def_f in struct_def_dir.glob("*.json"):
        with open(struct_def_f, mode="r", encoding="utf-8") as fp:
            struct_def = IdxStructureDefinition.model_validate_json(fp.read())
            lookup[struct_def.name] = struct_def
    return lookup


@pytest.fixture(scope="module")
def struct_def(
    request: pytest.FixtureRequest, struct_def_map
) -> IdxStructureDefinition:
    match request.param:
        case str(name):
            if name in struct_def_map:
                return struct_def_map[name]
            else:
                raise KeyError(
                    f"No structure definition with name {repr(name)} in resources"
                )
        case _ as param:
            raise ValueError(
                f"Unsupported type '{type(param)}' for fixture 'struct_def'. Expected type 'str'"
            )
