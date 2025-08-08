import json

import pytest
from fhir.resources.R4B.elementdefinition import (
    ElementDefinition,
    ElementDefinitionType,
    ElementDefinitionBase,
    ElementDefinitionSlicing,
    ElementDefinitionSlicingDiscriminator,
)
from fhir.resources.R4B.fhirtypes import ElementDefinitionSlicingDiscriminatorType
from fhir.resources.R4B.structuredefinition import (
    StructureDefinition,
    StructureDefinitionSnapshot,
)

from cohort_selection_ontology.core.generators.cql.attributes import ElementChain
from cohort_selection_ontology.util.fhir.structure_definition import get_element_chain
from common.util.fhir.structure_definition import Snapshot
from common.util.project import Project
from integration.conftest import project


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
                        ElementDefinition(
                            id="Condition.extension",
                            path="Condition.extension",
                            type=[ElementDefinitionType(code="Extension")],
                            slicing=ElementDefinitionSlicing(
                                discriminator=[
                                    ElementDefinitionSlicingDiscriminator(
                                        type="value", path="url"
                                    )
                                ],
                                ordered=False,
                                rules="open",
                            ),
                        ),
                        ElementDefinition(
                            id="Condition.extension:slice1",
                            path="Condition.extension",
                            type=[
                                ElementDefinitionType(
                                    code="Extension",
                                    profile=[
                                        "http://organization.org/fhir/StructureDefinition/extension1"
                                    ],
                                )
                            ],
                            sliceName="slice1",
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
                        ElementDefinition(
                            id="Procedure.element3",
                            path="Procedure.element3",
                            base=ElementDefinitionBase(path="Quantity", min=0, max="1"),
                            type=[ElementDefinitionType(code="Quantity")],
                        ),
                        ElementDefinition(
                            id="Procedure.element4",
                            path="Procedure.element4",
                            base=ElementDefinitionBase(path="Period", min=0, max="1"),
                            type=[ElementDefinitionType(code="Period")],
                        )
                    ]
                ),
            ).model_dump_json()
        )

    extension_dir_path = package_dir_path / "extension"
    extension_dir_path.mkdir(exist_ok=True)
    with open(
        extension_dir_path / "extension1-snapshot.json",
        mode="w+",
        encoding="utf-8",
    ) as f:
        f.write(
            StructureDefinition(
                url="http://organization.org/fhir/StructureDefinition/extension1",
                name="extension1",
                status="active",
                kind="complex-type",
                abstract=False,
                type="Extension",
                baseDefinition="http://hl7.org/fhir/StructureDefinition/Extension",
                derivation="constraint",
                snapshot=StructureDefinitionSnapshot(
                    element=[
                        ElementDefinition(
                            id="Extension", path="Extension", min=0, max="*"
                        ),
                        ElementDefinition(
                            id="Extension.value[x]",
                            path="Extension.value[x]",
                            base=ElementDefinitionBase(
                                path="Extension.value[x]", min=0, max="1"
                            ),
                            type=[
                                ElementDefinitionType(
                                    code="Reference",
                                    targetProfile=[
                                        "http://organization.org/fhir/StructureDefinition/procedure1"
                                    ],
                                )
                            ],
                        ),
                    ]
                ),
            ).model_dump_json()
        )

    return project


@pytest.fixture(scope="session")
def root_snapshot(attribute_test_project: Project) -> Snapshot:
    path = (
            attribute_test_project.input.cso
            / "modules"
            / "module"
            / "differential"
            / "package"
            / "condition1-snapshot.json"
    )
    with path.open(mode="r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def chain(root_snapshot: Snapshot, attribute_test_project: Project) -> ElementChain:
    return get_element_chain(
        "Condition.extension:slice1.value[x].resolve().element2",
        root_snapshot,
        "module",
        attribute_test_project,
    )
