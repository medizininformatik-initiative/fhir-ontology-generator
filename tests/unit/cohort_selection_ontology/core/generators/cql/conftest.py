import pytest
from fhir.resources.R4B.elementdefinition import (
    ElementDefinition,
    ElementDefinitionType,
    ElementDefinitionBase,
)
from fhir.resources.R4B.structuredefinition import (
    StructureDefinition,
    StructureDefinitionSnapshot,
)

from common.util.project import Project


@pytest.fixture(scope="session")
def attribute_test_project(tmp_path_factory) -> Project:
    project_dir_path = tmp_path_factory.mktemp("attribute_test_project")
    project = Project(path=project_dir_path)

    package_dir_path = project.input.cso.mkdirs(
        "modules", "module", "differential", "package"
    )
    with open(
        package_dir_path / "condition1-snapshot.json", mode="w+", encoding="utf-8"
    ) as f:
        f.write(
            StructureDefinition(
                url="http://organization.org/fhir/StructureDefinition/condition1",
                name="condition1",
                status="active",
                kind="resource",
                abstract=False,
                type="Condition",
                snapshot=StructureDefinitionSnapshot(
                    element=[
                        ElementDefinition(id="Resource", path="Resource"),
                        ElementDefinition(
                            id="Condition.element1",
                            path="Condition.element1",
                            type=[
                                ElementDefinitionType(code="Coding"),
                                ElementDefinitionType(
                                    code="Reference",
                                    targetProfile=[
                                        "http://organization.org/fhir/StructureDefinition/procedure1"
                                    ],
                                ),
                            ],
                        ),
                    ]
                ),
            ).model_dump_json()
        )
    with open(
        package_dir_path / "procedure1-snapshot.json", mode="w+", encoding="utf-8"
    ) as f:
        f.write(
            StructureDefinition(
                url="http://organization.org/fhir/StructureDefinition/procedure1",
                name="procedure1",
                status="active",
                kind="resource",
                abstract=False,
                type="Procedure",
                snapshot=StructureDefinitionSnapshot(
                    element=[
                        ElementDefinition(id="Resource", path="Resource"),
                        ElementDefinition(
                            id="Procedure.element2",
                            path="Procedure.element2",
                            base=ElementDefinitionBase(path="Coding", min=0, max="1"),
                            type=[ElementDefinitionType(code="Coding")],
                        ),
                    ]
                ),
            ).model_dump_json()
        )

    return project
