import json
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def modules_dir(tmp_path_factory) -> Path:
    modules_dir = tmp_path_factory.mktemp("modules", numbered=False)
    module1_dir = modules_dir / "module1" / "differential" / "package"
    module1_dir.mkdir(parents=True, exist_ok=True)
    with open(
        module1_dir / "constrained-condition1-snapshot.json",
        mode="w+",
        encoding="utf-8",
    ) as f:
        json.dump(
            dict(
                url="http://organization.org/fhir/StructureDefinition/constrained-condition1",
                name="constrained-condition1",
                status="draft",
                abstract=False,
                baseDefinition="http://organization.org/fhir/StructureDefinition/Condition",
            ),
            f,
        )
    with open(
        module1_dir / "specimen1-snapshot.json", mode="w+", encoding="utf-8"
    ) as f:
        json.dump(
            dict(
                url="http://organization.org/fhir/StructureDefinition/specimen1",
                name="specimen1",
                status="draft",
                abstract=False,
                type="Specimen",
            ),
            f,
        )
    module2_dir = modules_dir / "module2" / "differential" / "package"
    module2_dir.mkdir(parents=True, exist_ok=True)
    with open(
        module2_dir / "condition2-snapshot.json", mode="w+", encoding="utf-8"
    ) as f:
        json.dump(
            dict(
                url="http://organization.org/fhir/StructureDefinition/condition2",
                name="condition2",
                status="draft",
                abstract=False,
                type="Condition",
            ),
            f,
        )
    module3_dir = modules_dir / "module3" / "differential" / "package"
    module3_dir.mkdir(parents=True, exist_ok=True)
    with open(
        module3_dir / "condition1-snapshot.json", mode="w+", encoding="utf-8"
    ) as f:
        json.dump(
            dict(
                url="http://organization.org/fhir/StructureDefinition/Condition",
                name="Condition",
                status="draft",
                abstract=False
            ),
            f,
        )
    return modules_dir
