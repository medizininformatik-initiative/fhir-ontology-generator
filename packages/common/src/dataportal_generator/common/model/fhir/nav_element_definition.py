from functools import cached_property
from typing import List, Mapping, Optional

from fhir.resources.R4B.elementdefinition import ElementDefinition
from pydantic import PrivateAttr, Field

from dataportal_generator.common.model.fhir.idx_structure_definition import IdxStructureDefinition


def _parent_elem_def_id(elem_def: ElementDefinition) -> Optional[str]:
    """
    Computes the ID of the given element's parent element.

    If the element is itself a slice (`sliceName` is set), its parent is the base element that
    defines the slicing, found by dropping the trailing `:<sliceName>` segment of the ID.
    Otherwise, its parent is found by dropping the trailing `.<segment>` of the dotted element ID.

    :param elem_def: element definition to find the parent element ID of
    :return: parent element ID, or `None` if `elem_def` is a root element with no parent
    """
    sep = ":" if elem_def.sliceName else "."
    arr = elem_def.id.rsplit(sep, maxsplit=1)
    return arr[0] if len(arr) > 1 else None


class NavElementDefinition(ElementDefinition):
    """
    `ElementDefinition` subclass that adds navigation across the element tree of a
    `StructureDefinition`: a reference to the owning `struct_def`, the parent element (`parent`),
    the direct child elements, and any slices defined directly on this element.

    Instances are built via `construct_from()`, which wires up `struct_def` and `parent`, and (recursively) discovers
    and builds model instances for descendant element definitions.
    """

    _struct_def: IdxStructureDefinition = PrivateAttr()
    _sub_elems_by_id: Mapping[str, "NavElementDefinition"] = PrivateAttr(
        default_factory=dict
    )
    _slices_by_name: Mapping[str, "NavElementDefinition"] = PrivateAttr(
        default_factory=dict
    )

    parent: Optional["NavElementDefinition"] = Field(default=None, exclude=True)

    @classmethod
    def construct_from(
        cls,
        struct_def: IdxStructureDefinition,
        elem_def: ElementDefinition,
        realm: Optional[List[ElementDefinition]] = None,
        parent: Optional["NavElementDefinition"] = None,
    ) -> "NavElementDefinition":
        """
        Builds a `NavElementDefinition` wrapping `elem_def`, linked to its owning
        `struct_def` and to its parent element (`parent`).

        :param struct_def: indexed structure definition that `elem_def` belongs to
        :param elem_def: element definition to wrap
        :param realm: subset of `struct_def`'s elements to search for `elem_def`'s children and slices
            (see `_model_post_init`); defaults to the full snapshot (or, absent a snapshot, differential) element
            list when omitted. Passing a narrower `realm` avoids rescanning the whole element list on each recursive
            call once the descendants of an element are already known.
        :param parent: Already constructed parent ``NavElementDefinition`` instance. If ``None`` then the `parent`
                       field will also be ``None``
        :return: `NavElementDefinition` wrapping `elem_def`
        """
        val = NavElementDefinition.model_construct(**elem_def.__dict__)
        val._model_post_init(struct_def, parent, realm)
        return val

    def _model_post_init(
        self,
        struct_def: IdxStructureDefinition,
        parent: Optional["NavElementDefinition"] = None,
        realm: Optional[List[ElementDefinition]] = None,
    ) -> None:
        """
        Post-construction initialization method that builds the navigable element definition tree, and makes both the
        defining structure definition (`struct_def`) and parent element definition (`parent`) accessible.

        Its functionality is equivalent to `pydantic`s ``model_post_init`` method. However, since `fhir.resources` fails
        to pass the ``context`` parameter to that method this workaround is required.
        """
        self._struct_def = struct_def
        self.parent = parent
        if not realm:
            realm = (
                self._struct_def.snapshot.element
                if self._struct_def.snapshot
                else self._struct_def.differential.element
            )
        sub_realm = []
        sub_elems = []
        slices = []
        for elem_def in realm:
            if elem_def.id.startswith(self.id) and elem_def.id != self.id:
                rel_id = elem_def.id.removeprefix(self.id)
                # Slice
                if rel_id.startswith(":"):
                    segment = rel_id[1:]
                    if "." not in segment and ":" not in segment:
                        slices.append((segment, elem_def))
                # Sub element
                elif rel_id.startswith("."):
                    segment = rel_id[1:]
                    if "." not in segment and ":" not in segment:
                        sub_elems.append((segment, elem_def))
                sub_realm.append(elem_def)
        self._sub_elems_by_id = {
            key: self.construct_from(self._struct_def, ed, sub_realm, self)
            for key, ed in sub_elems
        }
        self._slices_by_name = {
            key: self.construct_from(self._struct_def, ed, sub_realm, self)
            for key, ed in slices
        }

    @property
    def struct_def(self) -> IdxStructureDefinition:
        return self._struct_def

    def element(
        self, rel_id: Optional[str] = None, full_id: Optional[str] = None
    ) -> Optional["NavElementDefinition"]:
        """
        Finds the definition of a direct child element, by ID segment relative to this element or by full element ID.

        :param rel_id: child's ID segment relative to this element (e.g. `"given"` for the
            child whose ID is `self.id + ".given"`)
        :param full_id: child's full element ID (e.g. `self.id + ".given"`); the relative
            segment is derived by stripping this element's ID and a leading `.`
        :return: matching direct child `NavElementDefinition`, or `None` if there's no
            such child
        :raises ValueError: if neither `rel_id` nor `full_id` is supplied
        """
        if rel_id:
            return self._sub_elems_by_id.get(rel_id)
        elif full_id:
            rel_id = full_id.removeprefix(self.id).removeprefix(".")
            return self._sub_elems_by_id.get(rel_id)
        else:
            raise ValueError("Either 'rel_id' or 'full_id' has to be supplied")

    @property
    def elements(self) -> List["NavElementDefinition"]:
        """All direct child elements of this element."""
        return list(self._sub_elems_by_id.values())

    def slice(
        self, name: Optional[str] = None, full_id: Optional[str] = None
    ) -> Optional["NavElementDefinition"]:
        """
        Finds the definition of a direct slice of this element, by slice name or by full element ID.

        :param name: slice name (the slice element's `sliceName`)
        :param full_id: slice element's full ID (e.g. `self.id + ":mrn"`); the slice name is
            derived by stripping this element's ID and the leading `:`
        :return: matching slice `NavElementDefinition`, or `None` if there's no such slice
        :raises ValueError: if neither `name` nor `full_id` is supplied
        """
        if name:
            return self._slices_by_name.get(name)
        elif full_id:
            name = full_id.removeprefix(self.id).removeprefix(":")
            return self._slices_by_name.get(name)
        else:
            raise ValueError("Either 'name' or 'full_id' has to be supplied")

    @property
    def slices(self) -> List["NavElementDefinition"]:
        """All slices defined directly on this element."""
        return list(self._slices_by_name.values())

    def sub_elem_def(
        self, rel_id: Optional[str] = None, full_id: Optional[str] = None
    ) -> Optional["NavElementDefinition"]:
        """
        Finds a direct child element definition (both of elements and slices).

        :param rel_id: relative ID segment; if it starts with `:`, it's looked up as a slice
            name via `slice()` (stripping the leading `:`), otherwise as a child ID segment via
            `element()`
        :param full_id: full element ID, tried first against `element()` and, if that misses,
            against `slice()`
        :return: matching `NavElementDefinition`, or `None` if neither a child nor a slice
            matches
        :raises ValueError: if neither `rel_id` nor `full_id` is supplied
        """
        if rel_id:
            if rel_id.startswith(":"):
                return self.slice(name=rel_id.removeprefix(":"))
            else:
                return self.element(rel_id=rel_id)
        elif full_id:
            if match := self.element(full_id=full_id):
                return match
            else:
                return self.slice(full_id=full_id)
        else:
            raise ValueError("Either 'rel_id' or 'full_id' has to be supplied")

    @property
    def sub_elem_defs(self) -> List["NavElementDefinition"]:
        """All direct child elements and slices defined directly on this element."""
        return [*self.elements, *self.slices]

    @cached_property
    def rel_id(self) -> str:
        """Relative element definition ID to parent element definition."""
        node = self.id.rsplit(".", 1)[-1]
        if ":" in node:
            return ":" + node.split(":")[-1]
        else:
            return node

    @cached_property
    def is_slice(self) -> bool:
        """Whether this element definition defines a slice or not."""
        return self.rel_id[0] == ":"

    @cached_property
    def rel_path(self) -> Optional[str]:
        """Relative element path to parent element definition. Will be `None` for slice defining element definitions."""
        if self.is_slice:
            return None
        else:
            return self.path.rsplit(".", maxsplit=1)[-1].removesuffix("[x]")