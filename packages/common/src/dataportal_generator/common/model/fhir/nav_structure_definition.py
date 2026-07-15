from fhir.resources.R4B.elementdefinition import ElementDefinition
from fhir.resources.R4B.structuredefinition import StructureDefinition
from pydantic import model_validator

from dataportal_generator.common.model.fhir.pydantic import construct_model
from dataportal_generator.common.model.fhir.idx_structure_definition import (
    IdxStructureDefinitionSnapshot,
)
from dataportal_generator.common.model.fhir.nav_element_definition import (
    NavElementDefinition,
)


def _get_struct_def_root_element(
    struct_def: IdxStructureDefinitionSnapshot,
) -> ElementDefinition:
    # We cannot use `get_element_by_id` since it would lead to indexing of the ``StructureDefinition.snapshot.element``
    # before replacement of its element definitions with their navigable variant
    root_elem_def = next(
        filter(lambda ed: ed.id == struct_def.type, struct_def.snapshot.element), None
    )
    if root_elem_def:
        return root_elem_def
    else:
        raise ValueError(
            f"No root element definition (ElementDefinition.id = '{struct_def.type}') could be found"
        )


def _elem_def_tree_to_list(
    nav_root_elem_def: "NavElementDefinition",
) -> list["NavElementDefinition"]:
    eds = [nav_root_elem_def]
    for sub_eds in nav_root_elem_def.sub_elem_defs:
        eds.extend(_elem_def_tree_to_list(sub_eds))
    return eds


class NavStructureDefinition(IdxStructureDefinitionSnapshot):
    @model_validator(mode="after")
    def _make_elem_defs_navigable(self) -> "NavStructureDefinition":
        root_elem_def = _get_struct_def_root_element(self)
        nav_root_elem_def = NavElementDefinition.construct_from(self, root_elem_def)
        self.snapshot.element = sorted(
            _elem_def_tree_to_list(nav_root_elem_def), key=lambda ed: ed.id
        )
        return self


def ensure_struct_def_is_navigable(
    struct_def: StructureDefinition,
) -> "NavStructureDefinition":
    """
    Ensures that the passed ``StructureDefinition`` is navigable by constructing an ``NavStructureDefinition`` object
    from it. If it already is an instance of the ``NavStructureDefinition`` class then it is returned unchanged

    :param struct_def: ``StructureDefinition`` object
    :return: ``NavElementDefinition`` object
    """
    if isinstance(struct_def, NavStructureDefinition):
        return struct_def
    else:
        # Hack to ensure that even invalid instances can be handled (e.g. if `snapshot.element[*].slicing.rules` is
        # missing again ...)
        nav_struct_def = construct_model(
            NavStructureDefinition, **struct_def.model_dump()
        )
        nav_struct_def._make_elem_defs_navigable()
        return nav_struct_def
