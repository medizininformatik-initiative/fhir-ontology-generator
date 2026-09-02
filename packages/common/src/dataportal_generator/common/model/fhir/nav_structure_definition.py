from typing import Any

from fhir.resources.R4B.elementdefinition import ElementDefinition
from fhir.resources.R4B.structuredefinition import StructureDefinition
from pydantic import PrivateAttr, model_validator

from dataportal_generator.common.model.fhir.idx_structure_definition import (
    IdxStructureDefinitionSnapshot,
)
from dataportal_generator.common.model.fhir.nav_element_definition import (
    NavElementDefinition,
)
from dataportal_generator.common.model.fhir.pydantic import construct_model


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
    for sub_eds in nav_root_elem_def.children:
        eds.extend(_elem_def_tree_to_list(sub_eds))
    return eds


class NavStructureDefinition(IdxStructureDefinitionSnapshot):
    __root: NavElementDefinition = PrivateAttr(default=None)

    def model_post_init(self, context: Any, /):
        root_elem_def = _get_struct_def_root_element(self)
        nav_root_elem_def = NavElementDefinition.construct_from(self, root_elem_def)
        self.snapshot.element = sorted(
            _elem_def_tree_to_list(nav_root_elem_def), key=lambda ed: ed.id
        )
        self.__root = nav_root_elem_def
    
    @property
    def root(self) -> NavElementDefinition:
        return self.__root


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
        return nav_struct_def
