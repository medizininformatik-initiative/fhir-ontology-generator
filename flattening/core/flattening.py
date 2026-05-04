import re
from typing import List, Dict, Tuple, Callable, Mapping, Any

from fhir.resources.R4B.elementdefinition import ElementDefinition
from fhir.resources.R4B.structuredefinition import StructureDefinition

from availability.constants.fhir import (
    FLATTENING_PACKAGE_PATTERN,
)
from common.model.fhir.structure_definition import StructureDefinitionSnapshot
from common.util.fhir.package.manager import FhirPackageManager
from common.util.http.exceptions import ClientError
from common.util.http.terminology.client import FhirTerminologyClient
from common.util.log.functions import get_logger
from common.util.project import Project
from common.util.structure_definition.functions import (
    get_parent_element_id,
    get_parent_element,
    get_available_slices, is_element_slice_base,
)
from flattening.model.FlatteningLookupModels import (
    FlatteningLookupElement,
    FlatteningLookup,
    ViewDefinitionColumn,
    ViewDefinitionSelect,
    ViewDefinitionSnippet,
)

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
]

# Children of elements which are required for meaningful flattening.
# Note: These children will be added even if they are not explicitly defined in the profile
REQUIRED_PRIMITIVE_PER_ELEMENT = {
    "Period": [("start", "dateTime"), ("end", "dateTime")],
    "Ratio": [("numerator", "Quantity"), ("denominator", "Quantity")],
    "Range": [("low", "Quantity"), ("high", "Quantity")],
    "Quantity": [("value", "code"), ("code", "code"), ("system", "uri")],
    "Age": [("value", "code"), ("code", "code"), ("system", "uri")],
    "Count": [("value", "code"), ("code", "code"), ("system", "uri")],
    "Duration": [("value", "code"), ("code", "code"), ("system", "uri")],
    "Distance": [("value", "code"), ("code", "code"), ("system", "uri")],
    "SimpleQuantity": [("value", "code"), ("code", "code"), ("system", "uri")],
    "MoneyQuantity": [("value", "code"), ("code", "code"), ("system", "uri")],
    "Coding": [("code", "code"), ("system", "uri")],
    "Reference": [("reference", "string")],
    "Identifier": [
        ("use", "code"),
        ("type", "CodeableConcept"),
        ("system", "uri"),
        ("value", "string"),
        ("period", "Period"),
        ("assigner", "Reference"),
    ],
}

# Children of Codings which will be excluded when generating.
# This works exactly as REQUIRED_PRIMITIVE_PER_ELEMENT but for codings
INCLUDED_CHILDREN_CODINGS = ["code", "system"]

# Exclude .id from flattening
EXCLUDED_CHILDREN = [".id"]


_logger = get_logger(__file__)

# A Dictionary holding flattening functions
FLATTEN_FUNCTIONS: dict[str, Callable[..., FlatteningLookupElement | None]] = {}


def register_flattener(*fhir_types: str):
    """
    Function to handle Flatteners for different datatypes and also to avoid massive switch case statements
    Usage::

        @register_flattener("Coding")
        def flatten_coding(element_id: str, ) . . .

    :param fhir_types: Fhir types as they appear in the structure definitions
    """

    def wrapper(fn):
        for t in fhir_types:
            if t in FLATTEN_FUNCTIONS:
                raise RuntimeError(f"Flattener already registered for FHIR type '{t}'")
            FLATTEN_FUNCTIONS[t] = fn
        return fn

    return wrapper


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
        element.type is not None
        and "[x]" in element.id.split(".")[-1]
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


def get_direct_children_ids(element: str, profile: StructureDefinitionSnapshot) -> List[str]:
    """
    Returns the list of ids of direct children . All elements 1 level below.
    Example::

        get_direct_children_ids(ElementDefinition("Condition.code.coding"), profile)
        ->  ["code", "system", "version", "display", "userSelected", ":sct", ":icd10-gm"]

    :param element: ID of element for which the children should be returned
    :param profile: snapshot of the profile of the element in question
    :return: list of children ids
    """
    return [
        el.id for el in profile.snapshot.element if get_parent_element_id(el) == element
    ]


def get_required_children_for_element(
    element: str,
    type: str,
) -> List[Tuple[str, str]]:
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
        (f"{element}.{part_prim_id}", part_prim_type)
        for (part_prim_id, part_prim_type) in (
            REQUIRED_PRIMITIVE_PER_ELEMENT.get(type, [])
        )
    ]


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
            if new_lookup and new_lookup.view_definition and new_lookup.view_definition.column else []
        ):
            column_el.name = column_el.name.replace("Extension", id_to_column_name(element_id))

        # Recontextualize children ids
        new_lookup.children = [
            child.replace("Extension", element_id)
            for child in (new_lookup.children if new_lookup.children else [])
        ]

        new_lookup.parent = check_if_root(get_parent_element_id(element_id), profile)
        res_lookup[new_key] = new_lookup

    return res_lookup


def extract_where_clause_for_slice(
    element: ElementDefinition, profile: StructureDefinitionSnapshot, client: FhirTerminologyClient = None, **kwargs
) -> str | None:
    """
    Extract codesystem for given element.
        1. Extract from Pattern
        2. Binding
        3. coding:slice.system.fixedUri
    :param client: client used to resolve bindingsh
    :param element: ElementDefinition defining the element from which the codeSystem should be extracted
    :param profile: profile of element
    :return: codesystem url or None
    """
    code_system_el = profile.get_element_by_id(f"{element.id}.system")
    if element.patternCoding or (code_system_el and code_system_el.patternUri):
        return (
            f"system = '{code_system_el.patternUri}'"
            if code_system_el and code_system_el.patternUri
            else f"system = '{element.patternCoding.system}'"
        )

    elif element.binding:
        binding_url = element.binding.valueSet
        if not client:
            _logger.error(
                f"No client provided. Without a FHIR client no binding can be extracted "
                f"=> defaulting to generic flattening"
                f"{element.id}: {binding_url}"
            )
            return None

        try:
            value_set = client.expand_value_set(url=binding_url)

            used_codes = [
                code.get("code")
                for code in value_set.get("expansion").get("contains")
            ]
            where_clause = " or ".join(f"code = '{code}'" for code in used_codes)
            return where_clause
        except ClientError as e:
            _logger.error(f"Could not expand valueSet: {binding_url} \n" f"{e}")

    elif (system_el := profile.get_element_by_id(f"{element.id}.system")) and system_el.fixedUri:
        return f"system = '{system_el.fixedUri}'"

    return None


def extract_code_system_for_identifier(
    element: ElementDefinition, profile: StructureDefinitionSnapshot, **kwargs
) -> str | None:
    """
    Attempts to extract code system of identifier slice from patterUri and fixedUri
    :param element: ID of the element which represents the slice of the identifier for which the code system should be extracted
    :param profile: profile containing element
    :return: codesystem url or None
    """

    if (
        element
        and (system_el := profile.get_element_by_id(f"{element.id}.system"))
        and system_el.fixedUri
    ):
        if system_el.fixedUri:
            return f"type.coding.system = '{system_el.fixedUri}'"
        if system_el.patternUri:
            return f"type.coding.system = '{system_el.patternUri}'"

    if element and element.patternIdentifier:
        if (
            element.patternIdentifier.type
            and element.patternIdentifier.type.coding
            and element.patternIdentifier.type.coding[0].system
        ):
            return f"type.coding.system = '{element.patternIdentifier.type.coding[0].system}'"
        if element.patternIdentifier.system:
            return f"type.coding.system = '{element.patternIdentifier.system}'"
    if (
        element
        and element.sliceName
        and profile.get_element_by_id(f"{element.id}.type.coding")
    ):
        where_clause = extract_where_clause_for_slice(
            profile.get_element_by_id(f"{element.id}.type.coding"), profile
        )
        if where_clause:
            return where_clause

    if (
        element
        and element.type
        and (type_el := profile.get_element_by_id(f"{element.id}.type"))
        and type_el.patternCodeableConcept
        and type_el.patternCodeableConcept.coding
        and len(type_el.patternCodeableConcept.coding) > 0
        and type_el.patternCodeableConcept.coding[0].system
    ):
        # edge case from Observation.identifier from profile: https://simplifier.net/mii-basismodul-labor-2025/mii_pr_labor_laboruntersuchung
        return f"type.coding.system = '{type_el.patternCodeableConcept.coding[0].system}'"
    return None


@register_flattener("Coding")
def flatten_coding(
    element_id: str,
    profile: StructureDefinitionSnapshot,
    codeable_concept_parent: str = None,
    **kwargs,
) -> Dict[str, FlatteningLookupElement] | None:
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
            for_each_or_null=element_id.split(".")[-1],
            column=[
                ViewDefinitionColumn(
                    name=f"{id_to_column_name(element_id)}_system", path="system"
                ),
                ViewDefinitionColumn(
                    name=f"{id_to_column_name(element_id)}_code", path="code"
                ),
            ],
        )
        return {element_id: flat_element}

    else:
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
        if where_clause := extract_where_clause_for_slice(element, profile, **kwargs):
            flat_element.view_definition = ViewDefinitionSnippet(
                for_each_or_null=f"{element.path.split('.')[-1]}.where({where_clause})",
                select=[],
            )

            flat_element.children = [
                el.id
                for el in profile.snapshot.element
                if element.id in el.id
                   and get_parent_element(profile, el).id == element.id
                   and el.id.split(".")[-1] in [k for (k,v) in REQUIRED_PRIMITIVE_PER_ELEMENT.get("Coding")]
            ]

            clean_kwargs = {
                k: v
                for k, v in kwargs.items()
                if k not in ["type", "polymorphic_child"]
            }
            lookup = {}
            for child in flat_element.children:
                lookup.update(flatten_element(child, profile, **clean_kwargs))

            required_primitives = get_required_children_for_element(
                element_id, "Coding"
            )
            for prim_id, prim_type in required_primitives:
                # filter for duplicates with .children
                if prim_id not in flat_element.children:
                    flat_element.children.append(prim_id)
                    lookup.update(flatten_primitive(prim_id, profile, type=prim_type))

            lookup.update({element.id: flat_element})

            return lookup
        else:
            flat_element = FlatteningLookupElement(
                parent=check_if_root(get_parent_element_id(element), profile)
            )

            flat_element.view_definition = ViewDefinitionSnippet(
                for_each_or_null=element.id.split(".")[-1],
                column=[
                    ViewDefinitionColumn(
                        name=f"{id_to_column_name(element.id)}_system", path="system"
                    ),
                    ViewDefinitionColumn(
                        name=f"{id_to_column_name(element.id)}_code", path="code"
                    ),
                ],
            )

            return {element.id: flat_element}


@register_flattener("BackboneElement")
def flatten_backbone_element(
    element_id: str, profile: StructureDefinitionSnapshot, **kwargs
) -> Dict[str, FlatteningLookupElement]:
    """
    Function to flatten a backboneElement. This element does not hold any information itself, but the children do.
    :param element_id: ID of element definition defining ``BackboneElement-typed`` element
    :param profile: profile of backboneElement
    :param kwargs: kwargs passing through things like the profile manager and the terminology client
    :return: flattened backbone element with flattened children
    """
    # element = profile.get_element_by_id(element_id)
    flat_backbone = FlatteningLookupElement(
        parent=check_if_root(get_parent_element_id(element_id), profile)
    )
    # determine children, base.path
    flat_backbone.children = get_direct_children_ids(element_id, profile)

    flat_backbone.view_definition = ViewDefinitionSnippet(
        for_each_or_null=element_id.split(".")[-1], select=[]
    )

    lookup = {element_id: flat_backbone}
    clean_kwargs = {k: v for k, v in kwargs.items() if k != "type"}
    for child in flat_backbone.children:
        lookup.update(flatten_element(child, profile, **clean_kwargs))

    return lookup


@register_flattener(
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
)
def flatten_generic_complex_element(
    element_id: str, profile: StructureDefinitionSnapshot, type: str = None, **kwargs
) -> Dict[str, FlatteningLookupElement]:
    """
    This function flattens complex datatypes in a generic way. All types flattened should not contain any information
    themselves, but rather, similar to the backboneElements, the children contain all information.
    Also required children are checked (Period needs ".start" and ".end" to be flattened properly)
    :param element_id: ID of element definition defining a generic complex-typed element
    :param profile: StructureDefinition of profile of element
    :param type: type of the element, to check for required children (specified explicitly when flattening a 'pseudo' element)
    :param kwargs: kwargs passing through things like the profile manager and the terminology client
    :return: flattened complex element with flattened children
    """

    element_type = type
    if element := profile.get_element_by_id(element_id):
        element_type = get_element_type(element)
    flat_generic_complex = FlatteningLookupElement(
        parent=check_if_root(get_parent_element_id(element_id), profile)
    )

    flat_generic_complex.view_definition = ViewDefinitionSnippet(
        for_each_or_null=element_id.split(".")[-1], select=[]
    )

    clean_kwargs = {k: v for k, v in kwargs.items() if k != "polymorphic_child"}

    lookup = {}
    # flatten extensions if any present
    for child_id in get_direct_children_ids(element_id, profile):
        if get_element_type(profile.get_element_by_id(child_id)) == "Extension":
            flat_generic_complex.children.append(child_id)
            lookup.update(flatten_element(child_id, profile, **clean_kwargs))

    # add the defined required primitive children
    required_primitives = get_required_children_for_element(element_id, element_type)
    for prim_id, prim_type in required_primitives:
        flat_generic_complex.children.append(prim_id)
        lookup.update(
            flatten_element(prim_id, profile, type=prim_type, **clean_kwargs)
        )

    lookup.update({element_id: flat_generic_complex})
    return lookup


@register_flattener("Extension")
def flatten_extension(
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

    # base extension element
    if element.slicing is not None:
        _logger.debug(
            f"Found children for {element_id}: {get_direct_children_ids(element.id, profile)}"
        )
        flat_ext = FlatteningLookupElement(
            parent=check_if_root(get_parent_element_id(element), profile),
            view_definition=ViewDefinitionSnippet(select=[]),
            children=get_direct_children_ids(element.id, profile),
        )

        lookup = {}
        if len(flat_ext.children) > 0:
            lookup.update({element_id: flat_ext})
        for child in flat_ext.children:
            lookup.update(flatten_element(child, profile, **kwargs))

        return lookup
    else:
        # extension slices
        lookup = {}

        if element.type[0].profile and (ext_profile_url := element.type[0].profile[0]):
            manager: FhirPackageManager
            if kwargs.get("manager"):
                manager = kwargs["manager"]
            else:
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
            content_pattern = {
                "resourceType": "StructureDefinition",
                "url": ext_profile_url,
            }
            if ext_profile := manager.find(content_pattern):
                ext_profile: StructureDefinitionSnapshot
                _logger.debug(
                    f"Found profile ->  following reference: {ext_profile_url}"
                )

                value_ext_el = ext_profile.get_element_by_id("Extension.value[x]")
                if value_ext_el and int(value_ext_el.max) > 0:
                    ext_lookup = flatten_polymorphic(
                        "Extension.value[x]", ext_profile, **kwargs
                    )
                    lookup.update(
                        recontextualize_extension_lookup(
                            ext_lookup, element_id, profile
                        )
                    )
                    flat_ext_el.children = [f"{element_id}.value[x]"]

                else:
                    # case when extension does contain extensions itself => no value[x] allowed -> max=0
                    for child_ext in get_direct_children_ids("Extension", ext_profile):
                        child = ext_profile.get_element_by_id(child_ext)
                        if get_element_type(child) == "Extension":
                            flat_ext_el.children.append(child_ext)
                            ext_lookup = flatten_element(
                                child_ext, ext_profile, **kwargs
                            )
                            lookup.update(
                                recontextualize_extension_lookup(
                                    ext_lookup, element_id, profile
                                )
                            )
            else:
                _logger.error(f"Could not resolve Extension ({element_id}) profile: {ext_profile_url}")

            lookup.update(
                recontextualize_extension_lookup(
                    {element_id: flat_ext_el}, element_id, profile
                )
            )

        elif (children := get_direct_children_ids(element.id, profile)) and len(
            children
        ) > 0:
            # extensions not defined in a separate structure definition
            ext_profile_url = profile.get_element_by_id(element.id + ".url").fixedUri
            flat_ext_el = FlatteningLookupElement(
                parent=check_if_root(get_parent_element_id(element), profile),
                view_definition=ViewDefinitionSnippet(
                    for_each_or_null=f"extension.where(url = '{ext_profile_url}')",
                    select=[],
                ),
            )
            lookup.update(
                flatten_polymorphic(f"{element.id}.value[x]", profile, **kwargs)
            )
            flat_ext_el.children = [f"{element.id}.value[x]"]
            lookup.update({element_id: flat_ext_el})

        return lookup


@register_flattener("CodeableConcept")
def flatten_codeable_concept(
    element_id: str, profile: StructureDefinitionSnapshot, **kwargs
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
            for_each_or_null=element_id.split(".")[-1], select=[]
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
            _logger.debug(f"When flattening codeableConcept {element_id} \t found slices: {list_of_children_slices}")
            flat_element.children = list_of_children_slices

            clean_kwargs = {k: v for k, v in kwargs.items() if k != "type"}
            lookup = {element_id: flat_element}
            for child in flat_element.children:
                lookup.update(
                    flatten_element(
                        child,
                        profile,
                        codeable_concept_parent=element_id,
                        **clean_kwargs,
                    )
                )

            return lookup

    # second case when no child_coding_element is defined
    _logger.debug(
        f"creating two columns for {element_id} because no slice had been found "
        f"for coding: {child_coding_element.id if child_coding_element else ''}. "
        f"Make sure this is correct"
    )
    flat_element.view_definition = ViewDefinitionSnippet(
        for_each_or_null=f"{element_id.split('.')[-1]}", select=[]
    )

    child = f"{element_id}.coding"
    flat_element.children = [child]

    clean_kwargs = {k: v for k, v in kwargs.items() if k != "type"}
    lookup = {element_id: flat_element}
    lookup.update(
        flatten_element(
            child,
            profile,
            codeable_concept_parent=element_id,
            type="Coding",
            **clean_kwargs,
        )
    )

    return lookup


def generate_flattening_polymorphic_child(
    element_id: str, profile: StructureDefinitionSnapshot, polymorphic_parent: ElementDefinition, type: str = None, **kwargs
) -> Dict[str, FlatteningLookupElement] | None:
    """
    Helper function for flattening polymorphic children. This is done by flattening the child (coding, quantity, etc.)
    the correct way and then inserting the generated "columns"
    into the viewDefinition of the polymorphic child(valueCoding, valueQuantity).

    Note: the type is adjusted as some types like "uri" do not work in pathling as a type
    :param element_id: ID of element definition defining one of the possible types of the parent polymorphic element
    :param profile: profile the element is in
    :param polymorphic_parent: parent which the child should point to
    :param type: element type for when dealing with 'pseudo' elements
    :param kwargs: passing through things like the profile manager and the terminology client
    :return: flattened polymorphic child and its children
    """
    element_type = type

    if profile.get_element_by_id(element_id):  # optional
        element_type = get_element_type(profile.get_element_by_id(element_id))

    polymorphic_element_name = polymorphic_parent.id.split(".")[-1].replace("[x]", "")
    fle = FlatteningLookupElement(parent=check_if_root(polymorphic_parent.id, profile))

    fle.view_definition = ViewDefinitionSnippet(
        for_each_or_null=f"{polymorphic_element_name}.ofType({element_type})", select=[]
    )

    # remove polymorphic_child from kwargs to avoid multiple values for keyword error
    clean_kwargs = {k: v for k, v in kwargs.items() if k != "polymorphic_child"}

    subtype_flat_element_lookup = flatten_element(
        element_id, profile, polymorphic_child=True, type=type, **clean_kwargs
    )
    if subtype_flat_element := subtype_flat_element_lookup.get(element_id):
        lookup_list: Dict[str, FlatteningLookupElement] = subtype_flat_element_lookup
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
        return lookup_list

    return {}


@register_flattener("Polymorphic")
def flatten_polymorphic(
    element_id: str, profile: StructureDefinitionSnapshot, **kwargs
) -> Dict[str, FlatteningLookupElement]:
    """
    This function flattens the polymorphic element. This does not contain any data itself, but relais on its children.
    Each type is flattened with ``generate_flattening_polymorphic_child``
    :param element_id: ID of element definition defining the base of a polymorphic element. Ex: Observation.value[x]
    :param profile: profile of the element
    :param kwargs: passing through things like the profile manager and the terminology client
    :return: flattened element and flattened children
    """

    element = profile.get_element_by_id(element_id)

    flat_ext_parent = FlatteningLookupElement(
        parent=check_if_root(get_parent_element_id(element_id), profile)
    )
    flat_ext_parent.view_definition = ViewDefinitionSnippet(select=[])

    possible_types = [t.code for t in element.type]
    slice_prefix = element_id.split(".")[-1].replace("[x]", "")

    # children that the profile does not define but which should be there based on the listed types
    undefined_children = [
        (f"{element_id}:{slice_prefix}{t[0].upper()}{t[1:]}", t) for t in possible_types
    ]

    # children that the profile defined
    # Considering the children of this element, is more bothering then useful
    # and for the flattening we only ever want the type slices anyway
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
    for child, child_type in undefined_children:
        flat_ext_parent.children.append(child)
        lookup_list.update(
            generate_flattening_polymorphic_child(
                child, profile, element, type=child_type, **clean_kwargs
            )
        )

    lookup_list.update({element_id: flat_ext_parent})
    return lookup_list


@register_flattener("Identifier")
def flatten_identifier(
    element_id: str, profile: StructureDefinitionSnapshot, **kwargs
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
        flat_ident_parent = FlatteningLookupElement(
            parent=check_if_root(get_parent_element_id(element_id), profile),
            view_definition=ViewDefinitionSnippet(
                for_each_or_null=f"{element_id.split('.')[-1]}", select=[]
            ),
            children=sorted(
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
            ),
        )

        clean_kwargs = {k: v for k, v in kwargs.items() if k != "type"}
        for child_slice in flat_ident_parent.children:
            lookup.update(
                flatten_element(child_slice, profile, type="Identifier", **clean_kwargs)
            )

        lookup.update({element_id: flat_ident_parent})

    else:
        # handles 2 cases in one: no slices defined and a slice name is defined.
        # Can be handled together because the only difference is the forEachOrNull

        foreach = f"{element_id.split('.')[-1]}"
        if where_clause := extract_code_system_for_identifier(element, profile):
            foreach = f"$this.where({where_clause})"

        flat_ident_child = FlatteningLookupElement(
            parent=check_if_root(get_parent_element_id(element_id), profile),
            view_definition=ViewDefinitionSnippet(
                for_each_or_null=foreach,
                select=[],
            ),
        )
        clean_kwargs = {k: v for k, v in kwargs.items() if k != "type"}
        for child_id, child_type in REQUIRED_PRIMITIVE_PER_ELEMENT.get("Identifier"):
            flat_ident_child.children.append(f"{element_id}.{child_id}")
            lookup.update(
                flatten_element(
                    f"{element_id}.{child_id}", profile, type=child_type, **clean_kwargs
                )
            )

        lookup.update({element_id: flat_ident_child})

    return lookup


@register_flattener(*FHIR_PRIMITIVES)
def flatten_primitive(
    element_id: str,
    profile: StructureDefinitionSnapshot,
    polymorphic_child: bool = False,
    type: str = None,
    **kwargs,
) -> Dict[str, FlatteningLookupElement]:
    """
    Flatten all primitives defined in FHIR_PRIMITIVES.
    All other flatten functions for complex types (apart from some exceptions)
    create the structures around these primitives
    for which a generic pattern like the one below, can be used

    Note: this function supports flattening elements by string id, meaning, even 'pseudo' elements can be flattened
    :param type: type of element when element can't be found in profile
    :param polymorphic_child: if true => element is child of polymorphic element like Condition.onsetDateTime
    :param element_id: ID of element definition defining a primitive(defined above)-typed element
    :param profile: profile of element
    :param kwargs: passing through things like the profile manager and the terminology client
    :return: flattened element
    """
    element_type = (
        get_element_type(profile.get_element_by_id(element_id))
        if profile.get_element_by_id(element_id)
        else (type if type else None)
    )

    flat_element = FlatteningLookupElement(
        parent=check_if_root(get_parent_element_id(element_id), profile)
    )
    flat_element.view_definition = ViewDefinitionSnippet(
        column=[
            ViewDefinitionColumn(
                name=f"{id_to_column_name(element_id)}",
                path=f"{element_id.split('.')[-1] if not polymorphic_child else '$this'}",
                type=element_type,
            )
        ]
    )

    lookup = {element_id: flat_element}
    for child in get_direct_children_ids(element_id, profile):
        lookup.update(flatten_element(child, profile, **kwargs))
    return lookup


def flatten_element(
    element_id: str,
    profile: StructureDefinitionSnapshot,
    client: FhirTerminologyClient = None,
    type: str | None = None,
    **kwargs,
) -> Dict[str, FlatteningLookupElement]:
    """
    This function flattens all FHIR types, as long as there is a flattener defined for that type.
    To add a flattener for a new type, use this decorator: ``@register_flattener("Polymorphic")``
    :param element_id: ID of element definition to be flattened
    :param profile: profile of the element
    :param client: terminology client
    :param type: explicit type for when dealing with 'pseudo' elements
    :param kwargs: passing through things like the profile manager and the terminology client
    :return: flattened element with flattened children
    """
    flat_lookup_els: Dict[str, FlatteningLookupElement] = {}
    element = profile.get_element_by_id(element_id)
    element_type = (
        type
        if type
        else "Polymorphic" if is_polymorphic(element) else get_element_type(element)
    )

    _logger.debug(
        f"Flattening element {element_id} of {'pseudo' if not profile.get_element_by_id(element_id) else ''} type: {element_type}"
    )

    f = FLATTEN_FUNCTIONS.get(element_type)
    if f:
        if res := f(element_id, profile, client=client, type=element_type, **kwargs):
            flat_lookup_els.update(res)

    else:
        _logger.warning(f"No flattener defined for {element_type} for {element_id}")

    return flat_lookup_els


def generate_flattening_lookup_for_profile(
    profile: StructureDefinitionSnapshot,
    client: FhirTerminologyClient,
    manager: FhirPackageManager,
    config: Mapping[str, Mapping[str, Mapping[str, Dict]]]
) -> FlatteningLookup:
    """
    Function to generate flattening for an entire profile.
    :param profile: StructureDefinition of profile to be flattened
    :param client: terminology client
    :param manager: profile manager
    :param config: dictionary containing config and rules
    :return: lookup for the given profile
    """

    lookup_elements = {}

    first_lvl_children = get_direct_children_ids(profile.type, profile)

    for lvl1_el in first_lvl_children:
        lookup_elements.update(
            flatten_element(lvl1_el, profile, client, manager=manager)
        )
    if profile.url in config and config.get(profile.url):
        for el_id, addition in config.get(profile.url).get("lookup_additions", {}).items():
            lookup_elements.update(
                {el_id: FlatteningLookupElement.model_validate(addition)}
            )

    flat_lookup = FlatteningLookup(
        url=profile.url,
        resource_type=profile.type,
        elements=flattening_post_process(lookup_elements),
    )

    return flat_lookup


def flattening_post_process(
    lookup_elements: Dict[str, FlatteningLookupElement]
) -> Dict[str, FlatteningLookupElement]:
    """
    Applies postprocessing to give lookup:
        1. Removes empty children arrays
        2. Removes references to non-existing children
    :param lookup_elements: Generated Lookup
    :return: Post processed lookup
    """
    res = lookup_elements
    for key, el in lookup_elements.items():
        el: FlatteningLookupElement
        new_el = el.model_copy(deep=True)
        new_el.children = sorted([
            child for child in (el.children or []) if child in lookup_elements
        ],key = lambda x: len(x))
        if len(new_el.children) == 0:
            new_el.children = None

        res[key] = new_el

    return res


def generate_flattening_lookup(
    manager: FhirPackageManager, client: FhirTerminologyClient, config: Mapping[str, Mapping[str, Mapping[str, Dict]]]
) -> List[FlatteningLookup]:
    """
    Flatten all available profiles
    :param manager: package manager containing the profiles
    :param client: terminology client
    :param config: dict containing config and rules
    :return: list of lookups of found profiles
    """

    # read all profiles from DSE
    _logger.info("Generating flattening lookup files")
    content_pattern = {"resourceType": "StructureDefinition", "kind": "resource"}
    lookup_file: List[FlatteningLookup] = []

    for profile in manager.iterate_cache(
        FLATTENING_PACKAGE_PATTERN, content_pattern, skip_on_fail=False
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
        lookup = generate_flattening_lookup_for_profile(profile, client, manager, config)
        lookup_file.append(lookup)

    return lookup_file
