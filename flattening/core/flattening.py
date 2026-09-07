import json
import re
from typing import Dict, List, Mapping

import yaml
from fhir.resources.R4B.elementdefinition import ElementDefinition
from fhir.resources.R4B.structuredefinition import StructureDefinition

from availability.constants.fhir import (
    FLATTENING_PACKAGE_PATTERN,
)
from common.model.fhir.nav_element_definition import NavElementDefinition
from common.model.fhir.structure_definition import StructureDefinitionSnapshot
from common.util.collections.functions import first
from common.util.fhir.package.manager import FhirPackageManager
from common.util.fhirpath.functions import (
    fhirpath_filter_for_slice,
    fhirpath_filter_from_value_discriminated_elem_def,
)
from common.util.http.terminology.client import FhirTerminologyClient
from common.util.log.functions import get_logger
from common.util.structure_definition.functions import (
    get_available_slices,
    get_parent_element_id,
)
from flattening import DEFAULT_CONFIG
from flattening.model.FlatteningConfigModels import FlatteningConfig
from flattening.model.FlatteningLookupModels import (
    FlatteningLookup,
    FlatteningLookupElement,
    ViewDefinitionColumn,
    ViewDefinitionSelect,
    ViewDefinitionSnippet,
)

GENERIC_COMPLEX_TYPES: List[str] = [
    "Period",
    "Ratio",
    "Range",
    "Quantity",
    "Age",
    "Count",
    "Duration",
    "Distance",
    "SimpleQuantity",
    "MoneyQuantity",
    "Reference",
    "TriggerDefinition",
    "Timing",
    "Timing.repeat",
    "Attachment",
    "Contributor",
    "ContactDetail",
    "SampledData",
    "Expression",
    "ContactPoint",
    "Address",
    "UsageContext",
    "DataRequirement",
    "DataRequirement.codeFilter",
    "DataRequirement.dateFilter",
    "DataRequirement.sort",
    "Annotation",
    "Dosage",
    "Dosage.doseAndRate",
    "Meta",
    "ParameterDefinition",
    "Money",
    "RelatedArtifact",
    "HumanName",
    "Signature",
]

FHIR_PRIMITIVES = [
    "boolean",
    "string",
    "code",
    "decimal",
    "integer",
    "integer64",
    "unsignedInt",
    "positiveInt",
    "uri",
    "canonical",
    "url",
    "markdown",
    "xhtml",
    "date",
    "dateTime",
    "instant",
    "time",
    "oid",
    "uuid",
    "base64Binary",
    "id",
]


def merge_config_with_default(project_flattening_config: FlatteningConfig) -> None:
    # if emtpy => copy default config
    if project_flattening_config.required_children_per_element is None:
        project_flattening_config.required_children_per_element = (
            DEFAULT_CONFIG.required_children_per_element
        )
        return

    # else merge default config into the one provided by the user
    default_keys = set(DEFAULT_CONFIG.required_children_per_element.keys())
    types_to_be_added = default_keys - set(
        project_flattening_config.required_children_per_element.keys()
    )

    for type_id in types_to_be_added:
        project_flattening_config.required_children_per_element.update(
            {type_id: DEFAULT_CONFIG.required_children_per_element[type_id]}
        )


_logger = get_logger(__file__)


def check_if_root(element_id: str, profile: StructureDefinitionSnapshot) -> str | None:
    """
    Function to handle the existence of the ``.parent`` attribute of the LookupElement.
    It was agreed upon removing the ``.parent`` attribute entirely when pointing to the root of the profile
    :param element_id: ID of Element defining the element to be checked
    :param profile: profile of element_id
    :return: None if element_id matches the profile type
    """
    return None if element_id == profile.type else element_id


def id_to_column_name(element_id: str) -> str:
    """
    Return the column name given an element.
        Column name is created by striping characters which are not allowed by pathling
    :param element_id: ID of the element for which the column name should be returned
    :return: column name for the given element
    """
    el_id = re.compile(r":([a-zA-Z][a-zA-Z0-9_-]*)").sub(
        lambda m: ":" + m.group(1).capitalize(), element_id
    )
    # ':' and '.' and '-' and '[x]' are not allowed by pathling in column names, using '#' and '_' instead
    el_id = el_id.replace(":", "")
    el_id = el_id.replace(".", "_")
    el_id = el_id.replace("-", "")
    el_id = el_id.replace("[x]", "_X_")
    return el_id


def is_polymorphic(element: ElementDefinition) -> bool:
    """
    Returns true if element is polymorphic
    :param element: ElementDefinition of element of interest
    :return: true if polymorphic
    """
    return (
        element.type is not None and "[x]" in element.id.split(".")[-1]
        # len > 1 does not apply as there are polymorphic elements with only one defined type
        # Laboruntersuchung.effective[x]
        # and len(element.type) > 1
    )


def get_element_type(
    element: ElementDefinition,
) -> str | None:
    """
    Returns the list of supported types
    :param element: ElementDefinition of element of which the type should be returned
    :return: supported types
    """
    if element.type is not None:
        return element.type[0].code

    # on root node
    if element.id == element.path:
        return None
    else:
        _logger.warning(f"No type found for element {element.id} => Skipping")

    return None


def get_direct_children_ids(
    element: str, profile: StructureDefinitionSnapshot
) -> List[str]:
    """
    Returns the list of ids of direct children. All elements 1 level below.
    Example::

        get_direct_children_ids(ElementDefinition("Condition.code.coding"), profile)
        ->  ["code", "system", "version", "display", "userSelected", ":sct", ":icd10-gm"]

    :param element: ID of element for which the children should be returned
    :param profile: snapshot of the profile of the element in question
    :return: list of children ids
    """
    if elem_def := profile.get_element_by_id(element):
        return [child.id for child in elem_def.children]
    else:
        return []


def recontextualize_extension_lookup(
    ext_lookup: Dict[str, FlatteningLookupElement],
    element_id: str,
    profile: StructureDefinitionSnapshot,
) -> Dict[str, FlatteningLookupElement]:
    """

    After flattening an extension, a lookup (:ext_lookup) for the extension profile is generated which
        is scoped for said extension profile.
    For the flattening to make sense the ext_lookup needs to be brought back to the original profile context.
    This is done by replacing "Extension" with the element id

    :param ext_lookup: lookup generated by flattening elements in the context of the extension profile
    :param element_id: ID of the Extension to which the lookup should be attached to
    :param profile: original profile
    :return: recontextualized lookup
    """
    res_lookup = {}

    if not ext_lookup:
        return {}

    for key, lookup in ext_lookup.items():
        new_key = key.replace("Extension", element_id)
        new_lookup = lookup.model_copy(deep=True)

        # Recontextualize column names
        for select_el in (
            new_lookup.view_definition.select
            if new_lookup
            and new_lookup.view_definition
            and new_lookup.view_definition.select
            else []
        ):
            for col in select_el.column:
                col.name = col.name.replace("Extension", id_to_column_name(element_id))

        for column_el in (
            new_lookup.view_definition.column
            if new_lookup
            and new_lookup.view_definition
            and new_lookup.view_definition.column
            else []
        ):
            column_el.name = column_el.name.replace(
                "Extension", id_to_column_name(element_id)
            )

        # Recontextualize children ids
        new_lookup.children = [
            child.replace("Extension", element_id)
            for child in (new_lookup.children if new_lookup.children else [])
        ]

        if lookup.parent:
            new_lookup.parent = lookup.parent.replace("Extension", element_id)
        else:
            new_lookup.parent = check_if_root(
                element_id, profile
            )
        res_lookup[new_key] = new_lookup

    return res_lookup


def flattening_get_parent(
    flat_element_id: str, lookup_elements: Dict[str, FlatteningLookupElement]
):
    return next(
        (k for k, v in lookup_elements.items() if flat_element_id in v.children),
        None,
    )


def flattening_post_process(
    lookup_elements: Dict[str, FlatteningLookupElement],
) -> Dict[str, FlatteningLookupElement]:
    """
    Applies postprocessing:
        1. Prunes leafless branches
        2. Removes elements and branches with "resolve()" in forEachOrNull as it's not supported
        3. Removes empty children arrays
        4. Removes references to non-existing children
        5. Sorts entries by index to enable easy comparison between versions
    :param lookup_elements: Generated Lookup
    :return: Post processed lookup
    """
    # 1 Prunes leafless branches and 2 Removes elements and branches with "resolve()"
    for key in reversed(list(lookup_elements.keys())):
        el: FlatteningLookupElement = lookup_elements.get(key)
        if not el:
            continue

        if is_leafless_branch_root(key, lookup_elements) or (
            el.view_definition
            and el.view_definition.for_each_or_null
            and "resolve()" in el.view_definition.for_each_or_null
        ):
            # remove itself and all children
            for child_id in el.children:
                lookup_elements.pop(child_id)

            lookup_elements.pop(key)

            # delete upward until parent is root or without any valid children
            parent_key: str = key
            while (
                parent_key := flattening_get_parent(parent_key, lookup_elements)
            ) and len(
                [
                    sibling_id
                    for sibling_id in lookup_elements.get(parent_key).children
                    if lookup_elements.get(sibling_id)
                ]
            ) == 0:
                lookup_elements.pop(parent_key)

    res = lookup_elements
    # 3 Remove empty children arrays and 4 remove refs to invalid children
    for key, el in lookup_elements.items():
        el: FlatteningLookupElement
        new_el = el.model_copy(deep=True)
        new_el.children = sorted(
            [child for child in (el.children or []) if child in lookup_elements]
        )
        if len(new_el.children) == 0:
            new_el.children = None

        res[key] = new_el

    # 5 Sorting by index
    return dict(sorted(res.items(), key=lambda item: item[0]))


def is_leafless_branch_root(
    element_id: str, lookup: Dict[str, FlatteningLookupElement]
) -> bool:
    """
    LookupElement determined by ``element_id`` is *not* root of a
    leafless branch if any of following conditions apply:
        1. has at least one valid child
        2. has column definition
        3. has select which contains column definition (example below)
    :param element_id: id of the element, root of the lookup
    :param lookup: flatteningLookup with element_id at root
    :return: {} is of correct structure
    """
    lookup_element: FlatteningLookupElement | None = lookup.get(element_id)
    if not lookup_element:
        return False

    # if at least one referenced children exists
    if lookup_element.children:
        for child_id in lookup_element.children:
            if lookup.get(child_id):
                return False

    # if lookupElement has columns
    if  lookup_element.view_definition.column:
        return False

    # if non-empty select already carries its own content
    # (e.g. columns wrapped for a polymorphic child like `value[x]:valueCoding`)
    if lookup_element.view_definition and lookup_element.view_definition.select:
        return False

    return True


def prune_leafless_branches(
    element_id: str, lookup: Dict[str, FlatteningLookupElement]
) -> Dict[str, FlatteningLookupElement]:
    """
    By using this function after each flattening function, deletion of leafless branches propagate up the tree
    leaving no flatteningLookup branches without any valid leafs

    LookupElement determined by ``element_id`` is *not* root of a
    leafless branch if any of following conditions apply:
        1. has at least one valid child
        2. has column definition
        3. has select which contains column definition (example below)
    :param element_id: id of the element, root of the lookup
    :param lookup: flatteningLookup with element_id at root
    :return: {} is of correct structure
    """
    lookup_element: FlatteningLookupElement | None = lookup.get(element_id)
    if not lookup_element:
        return {}

    # if at least one referenced children exists
    if lookup_element.children:
        for child_id in lookup_element.children:
            if lookup.get(child_id):
                return lookup
        return {}

    if not lookup_element.view_definition:
        return {}

    # if non-empty select already carries its own content
    # (e.g. columns wrapped for a polymorphic child like `value[x]:valueCoding`)
    if lookup_element.view_definition.select:
        return lookup

    # if lookupElement has columns
    if lookup_element.view_definition.column is not None:
        return lookup

    return {}


class FlatteningLookupGenerator:
    """
    Class that generates the flatteningLookup file used for flattening extracted FHIR Resources
    The flatteningLookup file provides the flattening tool with instructions on how each type or structure should be
    handled when flattened on a per-profile basis.

    """

    package_manager: FhirPackageManager
    config: FlatteningConfig
    lookup_additions: Mapping[str, Mapping[str, Mapping[str, Dict]]]
    client: FhirTerminologyClient

    def __init__(self, project):
        """
        :param project: Project for which the flatteningLookup should be generated

        """
        self.package_manager = project.package_manager
        self.client = FhirTerminologyClient.from_project(project)

        # load lookup_additions
        with open(
            project.input.flattening / "flattening_additions.json",
            mode="r",
            encoding="utf-8",
        ) as f:
            self.lookup_additions = json.load(f)

        # load config
        with open(
            project.input.flattening / "config.yaml", mode="r", encoding="utf-8"
        ) as f:
            config = FlatteningConfig(**yaml.safe_load(f))
            merge_config_with_default(project_flattening_config=config)
            self.config = config

    def _get_required_children_for_element(
        self, element: str, type: str
    ) -> list[tuple[str, str, list[str] | None, bool]]:
        """
        Returns the pairs of element definition ID and type which are required to correctly flatten
            the provided parent element and type.
        These are defined in REQUIRED_PRIMITIVE_PER_ELEMENT.
        For example: a Period is required to have children: ".start" and ".end" for the flattening to make sense
        :param element: ID of the element for which the required children should be returned
        :param type: type of element
        :return: List of tuples with format ``(child_id, child_type)``
        """
        return [
            (
                f"{element}.{child_spec.id}",
                child_spec.type,
                child_spec.required_types_for_polymorphic_element,
                child_spec.max_cardinality_multiple,
            )
            for child_spec in self.config.required_children_per_element.get(type, [])
        ]

    def _remove_subtree(
        self, element_id: str, lookup: Dict[str, FlatteningLookupElement]
    ) -> None:
        """
        Removes `element_id` and everything beneath it (its own `children`, recursively) from `lookup` in place
        """
        el = lookup.pop(element_id, None)
        if el:
            for child_id in el.children or []:
                self._remove_subtree(child_id, lookup)

    def _drop_indistinguishable_siblings(
        self,
        sibling_ids: List[str],
        lookup: Dict[str, FlatteningLookupElement],
        profile: StructureDefinitionSnapshot,
    ) -> List[str]:
        """
        Detects slices among `sibling_ids` (each already flattened into its own top-level entry in `lookup`) whose
        resulting ``for_each_or_null`` is identical to another sibling's. This happens when discriminator filter
        generation "succeeds" for each slice individually but still can't actually tell them apart -- e.g. two
        slices that both fall back to the same weak, non-required binding since neither has anything more
        specific. Every slice in such a group is dropped (subtree and all) the same way an outright-failed
        discriminator is, since keeping any of them would silently mix data from multiple slices under one column

        :param sibling_ids: element IDs of the sibling slices to check
        :param lookup: accumulated lookup, updated in place to remove colliding siblings
        :param profile: Profile the siblings belong to, used to pick the log level
        :return: `sibling_ids` with the colliding ones removed
        """
        by_for_each: Dict[str, List[str]] = {}
        for sid in sibling_ids:
            el = lookup.get(sid)
            for_each = (
                el.view_definition.for_each_or_null
                if el and el.view_definition
                else None
            )
            if for_each is not None:
                by_for_each.setdefault(for_each, []).append(sid)

        dropped = set()
        for for_each, ids in by_for_each.items():
            if len(ids) > 1:
                _logger.error(
                    profile,
                    f"Slices {ids} in profile '{profile.url}' all resolve to the identical FHIRPath filter "
                    f"'{for_each}' => nothing distinguishes them, dropping all of them",
                )
                dropped.update(ids)

        for sid in dropped:
            self._remove_subtree(sid, lookup)

        return [sid for sid in sibling_ids if sid not in dropped]

    def _render_generic_coding_columns(
        self, element_id: str
    ) -> List[ViewDefinitionColumn]:
        if not (
            coding_config := self.config.required_children_per_element.get("Coding")
        ):
            # should never happen as long as it exists in the config or the default config
            return []

        return [
            ViewDefinitionColumn(
                name=f"{id_to_column_name(element_id)}_{child_spec.id}",
                path=child_spec.id,
                type=child_spec.type,
            )
            for child_spec in coding_config
        ]

    def _flatten_coding(
        self,
        element_id: str,
        profile: StructureDefinitionSnapshot,
        codeable_concept_parent: str = None,
        **kwargs,
    ) -> Dict[str, FlatteningLookupElement]:
        """
        Function that defines how the complex type "Coding" needs to be flattened:
        1. Coding is not explicitly defined in profile. Its presence is assumed/required by a codeableConcept parent:
            should be flattened the generic way: create columns ``el_code, el_system``
        2. TODO: Coding is defined(maybe even with slices) but is not child of codeableConcept: skip
        3. Coding defined and child of codeableConcept:
            - extract slices from pattern, binding and fixed(?)
            - flatten children elements

        :param element_id: ID of element definition defining Coding-typed element
        :param profile: profile the element is in
        :param codeable_concept_parent: Used to correctly identify parent
        :param kwargs: kwargs passing through things like the profile manager and the terminology client
        :return: flattened element with flattened children
        """

        element = profile.get_element_by_id(element_id)

        if element is None:
            # Case `element is None`
            # when working with "pseudo" Codings, meaning codings that should be there but are not explicitly defined like
            # Extension.value[x]:valueCoding in https://www.medizininformatik-initiative.de/fhir/core/modul-prozedur/StructureDefinition/Durchfuehrungsabsicht
            # => return generic coding flattening

            flat_element = FlatteningLookupElement(
                parent=check_if_root(get_parent_element_id(element_id), profile)
            )

            flat_element.view_definition = ViewDefinitionSnippet(
                for_each_or_null=element_id.split(".")[-1].split(":")[0],
                column=self._render_generic_coding_columns(element_id),
            )
            return {element_id: flat_element}

        else:
            element: NavElementDefinition
            flat_element = FlatteningLookupElement(
                parent=check_if_root(
                    (
                        codeable_concept_parent
                        if codeable_concept_parent
                        else get_parent_element_id(element_id)
                    ),
                    profile,
                )
            )
            # columns based on the extracted code_system
            where_clause = None
            if element.sliceName:
                try:
                    where_clause = fhirpath_filter_for_slice(
                        element, manager=self.package_manager, client=self.client
                    )
                except Exception as err:
                    _logger.error(
                        f"Could not extract discriminator filter for '{element.id}' in profile "
                        f"'{profile.url}' (status={profile.status}) => dropping slice. {err}",
                    )
                    return {}

            if element.sliceName and where_clause:
                flat_element.view_definition = ViewDefinitionSnippet(
                    for_each_or_null=f"{element.path.split('.')[-1]}.{where_clause}",
                    select=[],
                )

                required_child_ids = {
                    child_spec.id
                    for child_spec in self.config.required_children_per_element.get(
                        "Coding", []
                    )
                }
                children: List[str] = [
                    el.id for el in element.elements if el.rel_id in required_child_ids
                ]

                clean_kwargs = {
                    k: v
                    for k, v in kwargs.items()
                    if k not in ["type", "polymorphic_child"]
                }
                lookup = {}
                for child_id in children:
                    if el := self._flatten_element(
                        element_id=child_id, profile=profile, **clean_kwargs
                    ):
                        flat_element.children.append(child_id)
                        lookup.update(el)

                for child_spec in self.config.required_children_per_element.get(
                    "Coding", []
                ):
                    # filter for duplicates with .children
                    full_child_id = f"{element_id}.{child_spec.id}"
                    if full_child_id not in flat_element.children:
                        if el := self._flatten_primitive(
                            element_id=full_child_id,
                            profile=profile,
                            type=child_spec.type,
                        ):
                            flat_element.children.append(full_child_id)
                            lookup.update(el)

                lookup.update({element.id: flat_element})

                return lookup
            else:
                flat_element = FlatteningLookupElement(
                    parent=check_if_root(get_parent_element_id(element), profile)
                )

                flat_element.view_definition = ViewDefinitionSnippet(
                    for_each_or_null=element.path.split(".")[-1],
                    column=self._render_generic_coding_columns(element_id),
                )

                return {element.id: flat_element}

    def _flatten_backbone_element(
        self,
        element_id: str,
        profile: StructureDefinitionSnapshot,
        **kwargs,
    ) -> Dict[str, FlatteningLookupElement]:
        """
        Function to flatten a backboneElement. This element does not hold any information itself, but the children do.
        Prunes itself if none of its children/slices produced anything.
        :param element_id: ID of element definition defining ``BackboneElement-typed`` element
        :param profile: profile of backboneElement
        :param kwargs: kwargs passing through things like the profile manager and the terminology client
        :return: flattened backbone element with flattened children
        """
        lookup = {}
        clean_kwargs = {k: v for k, v in kwargs.items() if k != "type"}
        flat_backbone = FlatteningLookupElement(
            parent=check_if_root(get_parent_element_id(element_id), profile),
            view_definition=ViewDefinitionSnippet(
                for_each_or_null=element_id.split(".")[-1].split(":")[0], select=[]
            ),
        )

        element = profile.get_element_by_id(element_id)
        # if backbone slices are available =>  flatten only slices
        # (flatten Obs.component:meanBP.value[x] and ignore Obs.component.value[x])
        if element and element.slicing:
            candidate_slices = [
                slice_def.id
                for slice_def in get_available_slices(element_id, profile)
                if slice_def
                and slice_def.type
                and len(slice_def.type) > 0
                and "BackboneElement" in slice_def.type[0].code
            ]

            for child in candidate_slices:
                if el := self._flatten_element(
                    element_id=child,
                    profile=profile,
                    **clean_kwargs,
                ):
                    lookup.update(el)
                    flat_backbone.children.append(child)
            flat_backbone.children = self._drop_indistinguishable_siblings(
                flat_backbone.children, lookup, profile
            )
        else:
            if element and element.sliceName:
                # if slice name is available => for each needs to have where clause
                try:
                    expr = f"$this.{fhirpath_filter_for_slice(element, manager=self.package_manager, client=self.client)}"
                except Exception as err:
                    _logger.error(
                        f"Could not extract discriminator filter for '{element.id}' in profile "
                        f"'{profile.url}' (status={profile.status}) => dropping slice. {err}",
                    )
                    return {}
                flat_backbone.view_definition = ViewDefinitionSnippet(
                    for_each_or_null=f"{expr}",
                    select=[],
                )

            for child in get_direct_children_ids(element_id, profile):
                if el := self._flatten_element(
                    element_id=child, profile=profile, **clean_kwargs
                ):
                    lookup.update(el)
                    flat_backbone.children.append(child)

        lookup.update({element_id: flat_backbone})
        return prune_leafless_branches(element_id, lookup)

    def _flatten_generic_complex_element(
        self,
        element_id: str,
        profile: StructureDefinitionSnapshot,
        type: str = None,
        **kwargs,
    ) -> Dict[str, FlatteningLookupElement]:
        """
        This function flattens complex datatypes in a generic way. All types flattened should not contain any information
        themselves, but rather, similar to the backboneElements, the children contain all information.
        Also required children are checked (Period needs ".start" and ".end" to be flattened properly)
        Prunes itself if none of its required children produced anything.
        :param element_id: ID of element definition defining a generic complex-typed element
        :param profile: StructureDefinition of profile of element
        :param type: type of the element, to check for required children (specified explicitly when flattening a 'pseudo' element)
        :param kwargs: kwargs passing through things like the profile manager and the terminology client
        :return: flattened complex element with flattened children
        """

        element_type = type
        if (element := profile.get_element_by_id(element_id)) and not type:
            element_type = get_element_type(element)
        flat_generic_complex = FlatteningLookupElement(
            parent=check_if_root(get_parent_element_id(element_id), profile)
        )

        flat_generic_complex.view_definition = ViewDefinitionSnippet(
            for_each_or_null=element_id.split(".")[-1].split(":")[0], select=[]
        )

        clean_kwargs = {k: v for k, v in kwargs.items() if k != "polymorphic_child"}

        lookup = {}

        required_children = []
        is_slicing_case = bool(
            element and element.slicing and not is_polymorphic(element)
        )
        # add the defined required primitive children if element has no slicing
        if is_slicing_case:
            list_of_children_slices = [
                slice_def.id
                for slice_def in get_available_slices(element_id, profile)
                if slice_def
                and slice_def.type
                and len(slice_def.type) > 0
                and element_type in slice_def.type[0].code
            ]

            for slice_id in list_of_children_slices:
                required_children.append((slice_id, element_type, [], False))
        else:
            expr = None
            if element and element.sliceName:
                try:
                    expr = f"$this.{fhirpath_filter_for_slice(element, manager=self.package_manager, client=self.client)}"
                except Exception as err:
                    _logger.error(
                        f"Could not extract discriminator filter for '{element.id}' in profile "
                        f"'{profile.url}' (status={profile.status}) => dropping slice. {err}",
                    )
                    return {}
            if expr:
                flat_generic_complex.view_definition = ViewDefinitionSnippet(
                    for_each_or_null=f"{expr}",
                    select=[],
                )
            required_children = self._get_required_children_for_element(
                element_id, element_type
            )

        flat_generic_complex.children = []
        for child_id, child_type, polymorph_types, max_card in required_children:
            if child_type == "Polymorphic" and polymorph_types:
                if el := self._flatten_polymorphic(
                    element_id=child_id,
                    profile=profile,
                    type=child_type,
                    required_types=polymorph_types,
                    **clean_kwargs,
                ):
                    flat_generic_complex.children.append(child_id)
                    lookup.update(el)
            elif child_type in FHIR_PRIMITIVES:
                if el := self._flatten_primitive(
                    element_id=child_id,
                    profile=profile,
                    type=child_type,
                    max_cardinality_multiple=max_card,
                    **clean_kwargs,
                ):
                    lookup.update(el)
                    flat_generic_complex.children.append(child_id)
            else:
                if el := self._flatten_element(
                    element_id=child_id,
                    profile=profile,
                    type=child_type,
                    **clean_kwargs,
                ):
                    lookup.update(el)
                    flat_generic_complex.children.append(child_id)

        if is_slicing_case:
            flat_generic_complex.children = self._drop_indistinguishable_siblings(
                flat_generic_complex.children, lookup, profile
            )

        lookup.update({element_id: flat_generic_complex})
        return prune_leafless_branches(element_id, lookup)

    def _flatten_extension(
        self,
        element_id: str,
        profile: StructureDefinitionSnapshot,
        **kwargs,
    ) -> Dict[str, FlatteningLookupElement]:
        """
        This function flattens extensions. Extensions are, by their very nature not necessarily part of a profile, but
        rather added as slices depending on the use case. Which means that everyone can add their own extensions.
        As we can't possibly account for all possible slices,we only flatten an extension if its defined
        as a slice in the profile.

        Handling is defined by the following two cases:
            1. Extensions base (where the slicing should be defined).
                - If a slicing and thus slices are defined,
                the viewDefinition of this extension should contain a single empty
                ``select`` array. This is done so that elements like ``Condition.extension`` can be selected
                - If ``no`` slicing and thus ``no`` slices are defined => return empty {}
            2. An actual Slice of an extensions (Child of type 1).
                - get extension profile, generate lookup and then recontextualize the generated lookup

        :param element_id: ID of element definition defining an Extension
        :param profile: profile the element is in
        :param kwargs: kwargs passing through things like the profile manager and the terminology client
        :return: flattened extension with flattened children
        """
        element = profile.get_element_by_id(element_id)

        if not element:
            return {}

        parent_elem_def = element.parent
        parent_type = get_element_type(parent_elem_def)

        # base extension element
        if element.slicing is not None:
            _logger.debug(
                f"Found children for {element_id}: {get_direct_children_ids(element.id, profile)}"
            )
            flat_ext = FlatteningLookupElement(
                parent=check_if_root(get_parent_element_id(element), profile),
                view_definition=ViewDefinitionSnippet(
                    for_each_or_null=(
                        parent_elem_def.rel_path
                        if parent_type in FHIR_PRIMITIVES
                        else None
                    ),
                    select=[],
                ),
            )

            lookup = {}
            for child in get_direct_children_ids(element.id, profile):
                if el := self._flatten_extension(
                    element_id=child, profile=profile, **kwargs
                ):
                    lookup.update(el)
                    flat_ext.children.append(child)

            lookup.update({element_id: flat_ext})
            return prune_leafless_branches(element_id, lookup)
        else:
            # extension slices
            lookup = {}

            if element.type[0].profile and (
                ext_profile_url := element.type[0].profile[0]
            ):
                if self.package_manager is None:
                    _logger.error(
                        f"No manager was provided. Without a manager extension {element_id} can't be flattened"
                    )
                    return {}

                flat_ext_el = FlatteningLookupElement(
                    parent=check_if_root(get_parent_element_id(element), profile),
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null=f"extension.where(url = '{ext_profile_url}')",
                        select=[],
                    ),
                )

                _logger.debug(f"Found profile for {element_id}: {ext_profile_url}")
                if ext_profile := self.package_manager.find_struct_def(ext_profile_url):
                    ext_profile: StructureDefinitionSnapshot
                    _logger.debug(
                        f"Found profile ->  following reference: {ext_profile_url}"
                    )

                    value_ext_el = ext_profile.get_element_by_id("Extension.value[x]")
                    if value_ext_el and int(value_ext_el.max) > 0:
                        ext_lookup = self._flatten_polymorphic(
                            element_id="Extension.value[x]",
                            profile=ext_profile,
                            **kwargs,
                        )
                        if not ext_lookup:
                            return {}
                        ext_lookup["Extension.value[x]"].parent = "Extension"
                        lookup.update(
                            recontextualize_extension_lookup(
                                ext_lookup, element_id, profile
                            )
                        )
                        flat_ext_el.children = [f"{element_id}.value[x]"]

                    else:
                        # case when extension does contain extensions itself => no value[x] allowed -> max=0
                        for child_ext in get_direct_children_ids(
                            "Extension", ext_profile
                        ):
                            child = ext_profile.get_element_by_id(child_ext)
                            if get_element_type(child) == "Extension":
                                ext_lookup = self._flatten_extension(
                                    child_ext, ext_profile, **kwargs
                                )
                                if ext_lookup:
                                    flat_ext_el.children.append(child_ext)
                                    flat_ext_el.children = [
                                        child_ext.replace("Extension", element_id)
                                    ]
                                    lookup.update(
                                        recontextualize_extension_lookup(
                                            ext_lookup, element_id, profile
                                        )
                                    )
                else:
                    _logger.error(
                        f"Could not resolve Extension ({element_id}) profile: {ext_profile_url}"
                    )

                lookup.update({element_id: flat_ext_el})

            elif (children := get_direct_children_ids(element.id, profile)) and len(
                children
            ) > 0:
                # extensions not defined in a separate structure definition
                ext_profile_url = profile.get_element_by_id(
                    element.id + ".url"
                ).fixedUri
                flat_ext_el = FlatteningLookupElement(
                    parent=check_if_root(get_parent_element_id(element), profile),
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null=f"extension.where(url = '{ext_profile_url}')",
                        select=[],
                    ),
                )
                if ext_el := self._flatten_polymorphic(
                    element_id=f"{element.id}.value[x]", profile=profile, **kwargs
                ):
                    lookup.update(ext_el)
                    flat_ext_el.children = [f"{element.id}.value[x]"]

                lookup.update({element_id: flat_ext_el})
            return prune_leafless_branches(element_id, lookup)

    def _flatten_codeable_concept(
        self,
        element_id: str,
        profile: StructureDefinitionSnapshot,
        **kwargs,
    ) -> Dict[str, FlatteningLookupElement]:
        """
        This function flattens codeableConcepts.
            1. codeableConcept.coding and slices are defined => flatten slices too and return
            2. no codeableConcept.coding or so slices defined => flatten generic (``el_system, el_code``)

        :param element_id: ID of element definition defining a CodeableConcept
        :param profile: profile the element is in
        :param kwargs: kwargs passing through things like the profile manager and the terminology client
        :return: flattened extension with flattened children
        """

        flat_element = FlatteningLookupElement(
            parent=check_if_root(get_parent_element_id(element_id), profile),
            view_definition=ViewDefinitionSnippet(
                for_each_or_null=element_id.split(".")[-1].split(":")[0], select=[]
            ),
        )

        # check if a Coding is defined and has any defined slices -> else col_el_sys + col_el_code
        child_coding_element = profile.get_element_by_id(f"{element_id}.coding")
        if child_coding_element is not None:
            list_of_children_slices = [
                slice_def.id
                for slice_def in get_available_slices(child_coding_element.id, profile)
                if len(slice_def.type) > 0 and "Coding" in slice_def.type[0].code
            ]
            if len(list_of_children_slices) > 0:
                _logger.debug(
                    f"When flattening codeableConcept {element_id} \t found slices: {list_of_children_slices}"
                )

                clean_kwargs = {k: v for k, v in kwargs.items() if k != "type"}
                lookup = {element_id: flat_element}
                for child in list_of_children_slices:
                    if el := self._flatten_element(
                        element_id=child,
                        profile=profile,
                        codeable_concept_parent=element_id,
                        **clean_kwargs,
                    ):
                        lookup.update(el)
                        flat_element.children.append(child)

                flat_element.children = self._drop_indistinguishable_siblings(
                    flat_element.children, lookup, profile
                )

                return prune_leafless_branches(element_id, lookup)
            else:
                _logger.warning(
                    f"No slice has been found => defaulting to generic flattening "
                    f"for coding: {child_coding_element.id if child_coding_element else ''}. "
                    f"Make sure this is correct."
                )

        # second case when no child_coding_element is defined
        flat_element.view_definition = ViewDefinitionSnippet(
            for_each_or_null=f"{element_id.split('.')[-1]}", select=[]
        )

        child = f"{element_id}.coding"
        flat_element.children = [child]

        clean_kwargs = {k: v for k, v in kwargs.items() if k != "type"}
        lookup = {element_id: flat_element}
        lookup.update(
            self._flatten_element(
                element_id=child,
                profile=profile,
                codeable_concept_parent=element_id,
                type="Coding",
                **clean_kwargs,
            )
        )

        return prune_leafless_branches(element_id, lookup)

    def _generate_flattening_polymorphic_child(
        self,
        element_id: str,
        profile: StructureDefinitionSnapshot,
        polymorphic_parent_id: str,
        type: str = None,
        **kwargs,
    ) -> Dict[str, FlatteningLookupElement]:
        """
        Helper function for flattening polymorphic children. This is done by flattening the child (coding, quantity, etc.)
        the correct way and then inserting the generated "columns"
        into the viewDefinition of the polymorphic child(valueCoding, valueQuantity).

        :param element_id: ID of element definition defining one of the possible types of the parent polymorphic element
        :param profile: profile the element is in
        :param polymorphic_parent_id: parent which the child should point to
        :param type: element type for when dealing with 'pseudo' elements
        :param kwargs: passing through things like the profile manager and the terminology client
        :return: flattened polymorphic child and its children
        """
        element_type = type

        if profile.get_element_by_id(element_id):  # optional
            element_type = get_element_type(profile.get_element_by_id(element_id))

        polymorphic_element_name = polymorphic_parent_id.split(".")[-1].replace(
            "[x]", ""
        )
        fle = FlatteningLookupElement(
            parent=check_if_root(polymorphic_parent_id, profile)
        )

        fle.view_definition = ViewDefinitionSnippet(
            for_each_or_null=f"{polymorphic_element_name}.ofType({element_type})",
            select=[],
        )

        # remove polymorphic_child from kwargs to avoid multiple values for keyword error
        clean_kwargs = {k: v for k, v in kwargs.items() if k != "polymorphic_child"}

        subtype_flat_element_lookup = self._flatten_element(
            element_id=element_id,
            profile=profile,
            polymorphic_child=True,
            type=type,
            **clean_kwargs,
        )
        if subtype_flat_element := subtype_flat_element_lookup.get(element_id):
            lookup_list: Dict[str, FlatteningLookupElement] = (
                subtype_flat_element_lookup
            )
            lookup_list.pop(element_id)
            # if element is a primitive element => include the .column of the viewDefinition of the flattened result
            # else if element is a complex element => flatten children accordingly below
            col = subtype_flat_element.view_definition.column
            if col:
                fle.view_definition.select = [ViewDefinitionSelect(column=col)]
            fle.children = (
                subtype_flat_element.children
                if subtype_flat_element.children
                else get_direct_children_ids(element_id, profile)
            )
            lookup_list.update({element_id: fle})
            return prune_leafless_branches(element_id, lookup_list)

        return {}

    def _flatten_polymorphic(
        self,
        element_id: str,
        profile: StructureDefinitionSnapshot,
        required_types: List[str] | None = None,
        **kwargs,
    ) -> Dict[str, FlatteningLookupElement]:
        """
        This function flattens the polymorphic element. This does not contain any data itself, but relais on its children.
        Each type is flattened with ``generate_flattening_polymorphic_child``
        :param element_id: ID of element definition defining the base of a polymorphic element. Ex: Observation.value[x]
        :param profile: profile of the element
        :param required_types: generate lookup for each type in this list
        :param kwargs: passing through things like the profile manager and the terminology client
        :return: flattened element and flattened children
        """

        element = profile.get_element_by_id(element_id)

        flat_ext_parent = FlatteningLookupElement(
            parent=check_if_root(get_parent_element_id(element_id), profile)
        )
        flat_ext_parent.view_definition = ViewDefinitionSnippet(select=[])

        specified_children = {
            (child_id, get_element_type(profile.get_element_by_id(child_id)))
            for child_id in get_direct_children_ids(element_id, profile)
            # filter out any children which do not represent types of the given element
            # Example:
            #   filter out: .id .display  etc.
            if (child_el := profile.get_element_by_id(child_id))
            and child_el.sliceName is not None
        }

        possible_types: List[str] = (
            [t.code for t in element.type] if not required_types else required_types
        )
        slice_prefix = element_id.split(".")[-1].replace("[x]", "")

        # children that the profile does not define but which should be there based on the listed types
        assumed_children = {
            (f"{element_id}:{slice_prefix}{t[0].upper()}{t[1:]}", t)
            for t in possible_types
        }
        unified_children = specified_children.union(assumed_children)

        # children that the profile defined
        # Considering the children of this element, is more bothering then useful
        # and for the flattening we only ever want the type slices anyway.
        # Polymorphic elements which do not have the valueSlices defined as children, will then proceed
        # to add the children of the only type to the list they support. In case of Coding this means that
        # .code, .id, .system all get columns which, as discussed in the flatten_coding, it does not make sense
        # to add these in flattening
        # The only time when this should be considered is in the rare
        # case an extension is defined on the polymorphic element itself
        # defined_children_ids = [
        #     (child_id, get_element_type(profile.get_element_by_id(child_id)))
        #     for child_id in get_direct_children_ids(element_id, profile)
        # ]

        # children_ids = set(undefined_children).union(defined_children_ids)

        clean_kwargs = {k: v for k, v in kwargs.items() if k != "type"}

        flat_ext_parent.children = []
        lookup_list = {}
        for child, child_type in unified_children:
            if el := self._generate_flattening_polymorphic_child(
                element_id=child,
                profile=profile,
                polymorphic_parent_id=element_id,
                type=child_type,
                **clean_kwargs,
            ):
                flat_ext_parent.children.append(child)
                lookup_list.update(el)

        lookup_list.update({element_id: flat_ext_parent})
        return prune_leafless_branches(element_id, lookup_list)

    def _flatten_identifier(
        self,
        element_id: str,
        profile: StructureDefinitionSnapshot,
        **kwargs,
    ) -> Dict[str, FlatteningLookupElement]:
        """

        :param element_id: ID of element definition defining the element of type Identifier. Ex: Patient.identifier
        :param profile: profile of the element
        :param kwargs: passing through things like the profile manager and the terminology client
        :return: flattened element and flattened children
        """

        element: ElementDefinition = profile.get_element_by_id(element_id)
        lookup = {}

        if not element:
            return {}

        if element.slicing:
            candidate_slices = sorted(
                set(
                    [
                        el.id
                        for el in get_available_slices(element_id, profile)
                        if el.id is not None
                        and len(el.type) > 0
                        and "Identifier" in el.type[0].code
                        and el.sliceName is not None
                    ]
                )
            )

            flat_ident_parent = FlatteningLookupElement(
                parent=check_if_root(get_parent_element_id(element_id), profile),
                view_definition=ViewDefinitionSnippet(
                    for_each_or_null=f"{element_id.split('.')[-1]}", select=[]
                ),
            )

            clean_kwargs = {k: v for k, v in kwargs.items() if k != "type"}
            for child_slice in candidate_slices:
                if el := self._flatten_element(
                    element_id=child_slice,
                    profile=profile,
                    type="Identifier",
                    **clean_kwargs,
                ):
                    lookup.update(el)
                    flat_ident_parent.children.append(child_slice)

            flat_ident_parent.children = self._drop_indistinguishable_siblings(
                flat_ident_parent.children, lookup, profile
            )

            lookup.update({element_id: flat_ident_parent})

        else:
            # handles 2 cases in one: no slices defined and a slice name is defined.
            # Can be handled together because the only difference is the forEachOrNull

            foreach = f"{element_id.split('.')[-1]}"
            if where_clause := fhirpath_filter_from_value_discriminated_elem_def(
                element, profile, "$this", client=self.client
            ):
                foreach = "$this." + where_clause

            flat_ident_child = FlatteningLookupElement(
                parent=check_if_root(get_parent_element_id(element_id), profile),
                view_definition=ViewDefinitionSnippet(
                    for_each_or_null=foreach,
                    select=[],
                ),
            )
            clean_kwargs = {
                k: v
                for k, v in kwargs.items()
                if k != "type" and k != "polymorphic_child"
            }
            for child_spec in self.config.required_children_per_element.get(
                "Identifier"
            ):
                if el := self._flatten_element(
                    element_id=f"{element_id}.{child_spec.id}",
                    profile=profile,
                    type=child_spec.type,
                    **clean_kwargs,
                ):
                    flat_ident_child.children.append(f"{element_id}.{child_spec.id}")
                    lookup.update(el)

            lookup.update({element_id: flat_ident_child})

        return lookup

    def _flatten_primitive(
        self,
        element_id: str,
        profile: StructureDefinitionSnapshot,
        polymorphic_child: bool = False,
        type: str = None,
        max_cardinality_multiple: bool = False,
        **kwargs,
    ) -> Dict[str, FlatteningLookupElement]:
        """
        Flatten all primitives defined in FHIR_PRIMITIVES.
        All other flatten functions for complex types (apart from some exceptions)
        create the structures around these primitives
        for which a generic pattern like the one below, can be used

        Note: this function supports flattening elements by string id, meaning, even 'pseudo' elements can be flattened
        :param element_id: ID of element definition defining a primitive(defined above)-typed element
        :param profile: profile of element
        :param polymorphic_child: if true => element is child of polymorphic element like Condition.onsetDateTime
        :param type: type of element when element can't be found in profile
        :param max_cardinality_multiple: True when cardinality max == "*". Further explanation in ChildSpec class
        :param kwargs: passing through things like the profile manager and the terminology client
        :return: flattened element
        """
        element_type = (
            get_element_type(profile.get_element_by_id(element_id))
            if profile.get_element_by_id(element_id)
            else (type if type else None)
        )

        if element_type in self.config.excluded_types:
            return {}

        card_max: bool = max_cardinality_multiple

        if (
            (el := profile.get_element_by_id(element_id))
            and el.max
            and not max_cardinality_multiple
        ):
            card_max = profile.get_element_by_id(element_id).max == "*"

        flat_element = FlatteningLookupElement(
            parent=check_if_root(get_parent_element_id(element_id), profile)
        )
        if not card_max:
            flat_element.view_definition = ViewDefinitionSnippet(
                column=[
                    ViewDefinitionColumn(
                        name=f"{id_to_column_name(element_id)}",
                        path=f"{element_id.split('.')[-1] if not polymorphic_child else '$this'}",
                        type=element_type,
                    )
                ]
            )
        else:
            flat_element.view_definition = ViewDefinitionSnippet(
                select=[
                    ViewDefinitionSelect(
                        column=[
                            ViewDefinitionColumn(
                                name=f"{id_to_column_name(element_id)}",
                                path=f"$this",
                                type=element_type,
                            )
                        ]
                    )
                ],
                for_each_or_null=f"{element_id.split('.')[-1]}",
            )

        lookup = {element_id: flat_element}

        return lookup

    def _flatten_element(
        self,
        element_id: str,
        profile: StructureDefinitionSnapshot,
        type: str | None = None,
        **kwargs,
    ) -> Dict[str, FlatteningLookupElement]:
        """
        This function flattens all FHIR types, as long as there is a flattener defined for that type.
        :param element_id: ID of element definition to be flattened
        :param profile: profile of the element
        :param type: explicit type for when dealing with 'pseudo' elements
        :param kwargs: passing through things like the profile manager and the terminology client
        :return: flattened element with flattened children
        """
        flat_lookup_els: Dict[str, FlatteningLookupElement] = {}
        element = profile.get_element_by_id(element_id)
        element_type = (
            type
            if type
            else "Polymorphic"
            if is_polymorphic(element)
            else get_element_type(element)
        )

        if element_type in self.config.excluded_types or element_type is None:
            return {}

        _logger.debug(
            f"Flattening element {element_id} of {'pseudo' if not profile.get_element_by_id(element_id) else ''} type: {element_type}"
        )

        res: Dict[str, FlatteningLookupElement] = {}

        if element_type == "Extension":
            flat_lookup_els.update(
                self._flatten_extension(
                    element_id=element_id, profile=profile, type=element_type, **kwargs
                )
            )
        else:
            match element_type:
                case x if x in GENERIC_COMPLEX_TYPES:
                    res = self._flatten_generic_complex_element(
                        element_id=element_id,
                        profile=profile,
                        type=element_type,
                        **kwargs,
                    )
                case x if x in FHIR_PRIMITIVES:
                    res = self._flatten_primitive(
                        element_id=element_id,
                        profile=profile,
                        type=element_type,
                        **kwargs,
                    )
                case "Coding":
                    res = self._flatten_coding(
                        element_id=element_id,
                        profile=profile,
                        type=element_type,
                        **kwargs,
                    )
                case "Identifier":
                    res = self._flatten_identifier(
                        element_id=element_id,
                        profile=profile,
                        type=element_type,
                        **kwargs,
                    )
                case "CodeableConcept":
                    res = self._flatten_codeable_concept(
                        element_id=element_id,
                        profile=profile,
                        type=element_type,
                        **kwargs,
                    )
                case "Polymorphic":
                    res = self._flatten_polymorphic(
                        element_id=element_id,
                        profile=profile,
                        type=element_type,
                        **kwargs,
                    )
                case "BackboneElement":
                    res = self._flatten_backbone_element(
                        element_id=element_id,
                        profile=profile,
                        type=element_type,
                        **kwargs,
                    )
                case _:
                    if element_type not in self.config.excluded_types:
                        _logger.warning(
                            f"No flattener defined for `{element_type}` for {element_id}"
                        )

            # Handle possible slices of the 'extension' element
            # FIXME: We have to exclude all extension on primitively-typed elements since Pathling does not seem to
            #        support them ATM
            if (
                element
                and all(t.code not in FHIR_PRIMITIVES for t in element.type)
                and len(res) > 1
            ):
                ext_elem_def_id = element_id + ".extension"
                ext_flattening_lookup_elements = self._flatten_extension(
                    ext_elem_def_id, profile
                )
                # Set extension lookup elements as additional children
                if ext_flattening_lookup_elements:
                    _, parent = first(lambda t: t[0] == element_id, res.items())
                    if ext_elem_def_id not in parent.children:
                        parent.children.append(ext_elem_def_id)
            else:
                ext_flattening_lookup_elements = {}

            if res:
                flat_lookup_els.update(res)
            if ext_flattening_lookup_elements:
                flat_lookup_els.update(ext_flattening_lookup_elements)

        return prune_leafless_branches(element_id, flat_lookup_els)

    def generate_flattening_lookup_for_profile(
        self,
        profile: StructureDefinitionSnapshot,
    ) -> FlatteningLookup:
        """
        Function to generate flattening for an entire profile.

        The lookup_addition dict was designed to add more attributes to PatientPseudonymisiert
        :param profile: StructureDefinition of profile to be flattened
        :return: lookup for the given profile
        """

        lookup_elements = {}

        first_lvl_children = get_direct_children_ids(profile.type, profile)

        lookup_elements.update(
            self._flatten_primitive(
                element_id=f"{profile.type}.id",
                profile=profile,
                type="string",
            )
        )

        for lvl1_el in first_lvl_children:
            lookup_elements.update(
                self._flatten_element(element_id=lvl1_el, profile=profile)
            )
        if profile.url in self.lookup_additions and self.lookup_additions.get(
            profile.url
        ):
            for el_id, addition in (
                self.lookup_additions.get(profile.url)
                .get("lookup_additions", {})
                .items()
            ):
                lookup_elements.update(
                    {el_id: FlatteningLookupElement.model_validate(addition)}
                )

        flat_lookup = FlatteningLookup(
            url=profile.url,
            resource_type=profile.type,
            elements=flattening_post_process(lookup_elements),
        )

        return flat_lookup

    def generate_flattening_lookup(self) -> List[FlatteningLookup]:
        """
        Flatten all available profiles

        :return: list of lookups of found profiles
        """

        # read all profiles from DSE
        _logger.info("Generating flattening lookup files")
        content_pattern = {
            "resourceType": "StructureDefinition",
            "kind": "resource",
            "status": "active",
            # "url": "https://gematik.de/fhir/isik/StructureDefinition/ISiKEKG",
        }
        lookup_file: List[FlatteningLookup] = []

        for profile in self.package_manager.iterate_cache(
            FLATTENING_PACKAGE_PATTERN,
            content_pattern,
            skip_on_fail=False,
        ):
            if profile.type in ["SearchParameter"]:
                continue
            if not isinstance(profile, StructureDefinition) and not profile.snapshot:
                _logger.warning(
                    f"Profile '{profile.url}' is not in snapshot form => Skipping"
                )
                continue

            _logger.info(
                f"Generating flattening lookup for {profile.name}: {profile.id}  |  {profile.url}"
            )

            profile: StructureDefinitionSnapshot
            lookup = self.generate_flattening_lookup_for_profile(profile)
            lookup_file.append(lookup)

        lookup_file.sort(key=lambda lookup: lookup.url or "")
        return lookup_file
