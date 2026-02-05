import copy
import re
from typing import Optional, List, Dict, Tuple, Callable

from fhir.resources.R4B.elementdefinition import ElementDefinition
from fhir.resources.R4B.structuredefinition import StructureDefinition
from pydantic import BaseModel, Field

from availability.constants.fhir import MII_CDS_PACKAGE_PATTERN
from common.model.fhir.structure_definition import StructureDefinitionSnapshot
from common.util.fhir.package.manager import FhirPackageManager
from common.util.http.terminology.client import FhirTerminologyClient
from common.util.log.functions import get_logger
from common.util.structure_definition.functions import (
    get_parent_element_id,
    get_parent_element,
    get_available_slices,
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
PATHLING_SUPPORTED_TYPE_CONVERTER = {"uri": "string"}
REQUIRED_PRIMITIVE_PER_ELEMENT = {
    "Period": [("start", "dateTime"), ("end", "dateTime")],
    "Quantity": [("value", None), ("code", "code"), ("system", None)],
}
EXCLUDED_CHILDREN_CODINGS = ["userSelected", "id", "display", "version"]


_logger = get_logger(__file__)


class FlatteningLookupElement(BaseModel):
    parent: Optional[str] = None
    view_definition: Optional[Dict] = Field(alias="viewDefinition", default=None)
    children: Optional[List[str]] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class FlatteningLookup(BaseModel):
    url: str
    resource_type: str = Field(alias="resourceType")
    elements: Dict[str, FlatteningLookupElement] = {}

    model_config = {"populate_by_name": True}


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
    :param element_id: element_id to be checked
    :param profile: profile of element_id
    :return: None if element_id matches the profile type
    """
    return None if element_id == profile.type else element_id


def id_to_column_name(element_id: str) -> str:
    """
    Return the column name given an element.
        Column name is created by striping characters which are not allowed by pathling
    :param element_id: Element the column should refer to
    :return: column name for the given element
    """
    el_id: str = element_id
    el_id = re.compile(r":([a-zA-Z][a-zA-Z0-9_-]*)").sub(lambda m: ":" + m.group(1).capitalize(), el_id)
    # ':' and '.' and '-' and '[x]' are not allowed by pathling in column names, using '#' and '_' instead
    el_id = el_id.replace(":", "")
    el_id = el_id.replace(".", "_")
    el_id = el_id.replace("-", "")
    el_id = el_id.replace("[x]", "_X_")
    return el_id


def classify_element_type(
    element,
) -> str | None:
    """
    Returns the first of the types of the element, if any present.
        - If an element contains "[x]" in the last part of its id and has more than one type, its Polymorphic
    :param element: element the type should be returned of
    :return: type or "Polymorphic" or None
    """
    if (
        element.type is not None
        and "[x]" in element.id.split(".")[-1]
        and len(element.type) > 1
    ):
        return "Polymorphic"

    if element.type is not None and len(element.type) == 1:
        if element.type in FHIR_PRIMITIVES:
            return "primitive"
        return element.type[0].code

    if element.id == element.path:
        return None
    else:
        _logger.warning(f"No type found for element {element.id} => Skipping")

    return None


def get_direct_children_ids(element: str, profile) -> List[str]:
    """
    Returns the list of ids of direct children . All elements 1 level below.
    Example::

        get_direct_children_ids(ElementDefinition("Condition.code.coding"), profile)
        ->  ["code", "system", "version", "display", "userSelected", ":sct", ":icd10-gm"]

    :param element: element from which to get the children from
    :param profile: snapshot of the profile of the element in question
    :return: list of children ids
    """
    return [
        el.id
        for el in profile.snapshot.element
        if get_parent_element_id(el) == element
    ]


def get_required_children_for_element(
    element: str,
    type: str,
) -> List[Tuple[str, str]]:
    """
    Returns a pairs of elements which are required for defined.
    These are defined in REQUIRED_PRIMITIVE_PER_ELEMENT.
    For example: a Period is required to have children: ".start" and ".end" for the flattening to make sense
    :param element: element id of element in question
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

    After flattening an extension, the resulting lookup needs to be brought back into the
    context of the profile for the flattening to make sense.
    This is done by replacing "Extension" with the element id

    #TODO: needs to be changed in the future as extensions can probably have other types too
    #TODO: which means that replacing "Extension" will not work anymore


    Extension.value[x]": {
      "parent": "Extension",
      "view_definition": {
        "forEachOrNull": "value[x].coding",
        "select": [
            {
                "column": [
                  {
                    "name": "Extension_value_X__system",
                    "path": "system"
                  },
                  {
                    "name": "Extension_value_X__code",
                    "path": "code"
                  }
                ]
            }
        ]
      },
      "children": []
      },
    :param ext_lookup:
    :param element_id:
    :param profile:
    :return: recontextualized lookup
    """
    res_lookup = {}

    for key, lookup in ext_lookup.items():
        new_key = key.replace("Extension", element_id)
        new_lookup = copy.deepcopy(lookup)

        for select_el in new_lookup.view_definition.get("select",[]):
            for col in select_el.get("column",[]):
                col["name"] = col["name"].replace(
                    "Extension", id_to_column_name(element_id)
                )

        new_lookup.children = [
            child.replace("Extension", element_id)
            for child in (new_lookup.children if new_lookup.children else [])
        ]
        new_lookup.parent = check_if_root(get_parent_element_id(element_id), profile)

        res_lookup[new_key] = new_lookup

    return res_lookup


def extract_code_system_for_slice(element: ElementDefinition, profile: StructureDefinitionSnapshot) -> str|None:
    """
    Extract codesystem for given element.
        1. Extract from Pattern
        2. Binding
        3. Fixed
    :param element: id of the element
    :param profile: profile of element
    :return: codesystem url or None
    """
    code_system_el = profile.get_element_by_id(f"{element.id}.system")
    if element.patternCoding or (code_system_el and code_system_el.patternUri):
        return (
            code_system_el.patternUri
            if code_system_el and code_system_el.patternUri
            else element.patternCoding.system
        )

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
    1. For codings which are expected, but not defined explicitly in the profile (for example a polymorphic element)
        should be flattened the generic way: create columns ``el_code, el_system``
    2. TODO: Coding is defined(maybe even with slices) but is not child of codeableConcept: skip
    3. Coding defined and child of codeableConcept:
        - extract slices from pattern, binding and fixed(?)
        - flatten children elements

    :param element_id: element id of the coding
    :param profile: profile the element is in
    :param polymorphic_concrete_type: True if element is subtype of a polymorphic element like .valueCoding
    :param codeable_concept_parent:
    :param kwargs:
    :return: flattened element with flattened children
    """

    element = profile.get_element_by_id(element_id)

    if element is None:
        # when working with "pseudo" Codings, meaning codings that should be there but are not properly defined like
        # Extension.value[x]:valueCoding in https://www.medizininformatik-initiative.de/fhir/core/modul-prozedur/StructureDefinition/Durchfuehrungsabsicht
        # or rather the lack of its definition
        # return generic coding flattening

        flat_element = FlatteningLookupElement(
            parent=check_if_root(get_parent_element_id(element_id), profile)
        )

        flat_element.view_definition = {
            "forEachOrNull": element_id.split(".")[-1],
            "column": [
                {"name": f"{id_to_column_name(element_id)}_system", "path": "system"},
                {"name": f"{id_to_column_name(element_id)}_code", "path": "code"},
            ],
        }
        return {element_id: flat_element}

    # standalone coding
    if not codeable_concept_parent:
        # TODO: implement properly, with checking for slices. For now generic flattening
        _logger.warning("Not implemented yet. Falling back to generic flattening")

        flat_element = FlatteningLookupElement(
            parent=check_if_root(get_parent_element_id(element), profile)
        )
        flat_element.view_definition = {
            "forEachOrNull": element.id.split(".")[-1],
            "column": [
                {"name": f"{id_to_column_name(element.id)}_system", "path": "system"},
                {"name": f"{id_to_column_name(element.id)}_code", "path": "code"},
            ],
        }
        return {element.id:flat_element}

    else:
        flat_element = FlatteningLookupElement(
            parent=check_if_root(codeable_concept_parent, profile)
        )
        # check pattern
        if code_system_url := extract_code_system_for_slice(element, profile):
            flat_element.view_definition = {
                "forEachOrNull": f"{element.path.split('.')[-1]}.where(system = '{code_system_url}')",
                "select": [],
            }

            flat_element.children = [
                el.id
                for el in profile.snapshot.element
                if element.id in el.id
                and get_parent_element(profile, el).id == element.id
                and el.id.split(".")[-1] not in EXCLUDED_CHILDREN_CODINGS
            ]

            lookup = {element.id: flat_element}
            for child in flat_element.children:
                lookup.update(flatten_element(child, profile, **kwargs))
            return lookup

        # TODO: check for Binding

        return None


@register_flattener("Reference")
def flatten_reference(
    element_id: str, profile: StructureDefinitionSnapshot, **kwargs
) -> Dict[str, FlatteningLookupElement]:
    """
    Function to flatten an element of type Reference. In instance data, a reference
    never contains the reference itself, but rather it an element .reference which holds the actual string
    This needs to be accounted for
    :param element_id: element id of the reference
    :param profile: profile of the element
    :param kwargs: kwargs passing through things like the profile manager and the terminology client
    :return: flattened element with flattened children
    """
    _logger.debug(f"Flattening Reference: {element_id}")

    flat_reference_main = FlatteningLookupElement(
        parent=check_if_root(get_parent_element_id(element_id), profile)
    )
    flat_reference_main.view_definition = {
        "forEachOrNull": f"{element_id.split('.')[-1]}",
        "select": [],
    }

    lookup = {}
    flat_reference_main.children = []
    for child in get_direct_children_ids(element_id, profile):
        flat_reference_main.children.append(child)
        lookup.update(flatten_element(child, profile, **kwargs))

    # -----------------------

    ref_element_id = f"{element_id}.reference"

    flat_reference_ref = FlatteningLookupElement(
        parent=check_if_root(element_id, profile)
    )
    flat_reference_ref.view_definition = {
        "forEachOrNull": "reference",
        "select": [
            {
                "column": [
                    {
                        "name": f"{id_to_column_name(ref_element_id)}",
                        "path": "$this",
                    }
                ],
            }
        ],
    }
    flat_reference_main.children.append(ref_element_id)
    lookup.update({element_id: flat_reference_main})
    lookup.update({ref_element_id: flat_reference_ref})

    return lookup


@register_flattener("BackboneElement")
def flatten_backbone_element(
    element_id: str, profile: StructureDefinitionSnapshot, **kwargs
) -> Dict[str, FlatteningLookupElement]:
    """
    Function to flatten a backboneElement. This element does not hold any information itself, but the children do.
    :param element_id: backboneElement id
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
    flat_backbone.view_definition = {
        "forEachOrNull": element_id.split(".")[-1],
        "select": [],
    }

    _logger.debug(
        f"Flatten backbone {element_id} with children: {flat_backbone.children}"
    )

    lookup = {element_id: flat_backbone}
    for child in flat_backbone.children:
        lookup.update(flatten_element(child, profile, **kwargs))

    return lookup


@register_flattener("Period", "Ratio", "Range")
def flatten_generic_complex_element(
    element_id: str, profile: StructureDefinitionSnapshot, type=None, **kwargs
) -> Dict[str, FlatteningLookupElement]:
    """
    This function flattens complex datatypes in a generic way. All types flattened should not contain any information
    themselves, but rather, similar to the backboneElements, the children contain all information
    Also required children are checked (Period needs ".start" and ".end" to be flattened properly)
    :param element_id: element id of the complex element
    :param profile: profile the element is in
    :param type: type of the element, to check for required children (specified explicitly when flattening a 'pseudo' element)
    :param kwargs: kwargs passing through things like the profile manager and the terminology client
    :return: flattened complex element with flattened children
    """

    element_type = type
    if element := profile.get_element_by_id(element_id):
        element_type = classify_element_type(element)
    flat_generic_complex = FlatteningLookupElement(
        parent=check_if_root(get_parent_element_id(element_id), profile)
    )
    # determine children, base.path
    flat_generic_complex.children = get_direct_children_ids(element_id, profile)
    flat_generic_complex.view_definition = {
        "forEachOrNull": element_id.split(".")[-1],
        "select": [],
    }

    lookup = {element_id: flat_generic_complex}
    for child in flat_generic_complex.children:
        lookup.update(flatten_element(child, profile, **kwargs))

    # add if missing, required primitives. These should only be added if not defined in the profile
    required_primitives = get_required_children_for_element(element_id, element_type)
    for prim_id, prim_type in required_primitives:
        # filter for duplicates with .children
        if prim_id not in flat_generic_complex.children:
            flat_generic_complex.children.append(prim_id)
            lookup.update(flatten_primitive(prim_id, profile, type=prim_type))

    _logger.debug(
        f"Flatten {element_id} of type {element_type} with children: {flat_generic_complex.children}"
    )
    return lookup


@register_flattener("Extension")
def flatten_extension(
    element_id: str,
    profile: StructureDefinitionSnapshot,
    **kwargs,
) -> Dict[str, FlatteningLookupElement]:
    """
    This function flattens extensions.
        1. Extensions with a slicing defined.
            - If these really do have slices defined,
            the viewDefinition of this extension should contain a single empty
            "select" array. This is done so that elements like "Condition.extension" can be selected
            - if no slices are defined => return empty {}
        2. Slices of extensions(type 1).
            - get extension profile generate lookup and then recontextualize the generated lookup
    :param element_id: element id of extension
    :param profile: profile the element is in
    :param kwargs: kwargs passing through things like the profile manager and the terminology client
    :return: flattened extension with flattened children
    """
    element = profile.get_element_by_id(element_id)

    # parent extension
    if element.slicing is not None:
        _logger.debug(
            f"Found children for {element_id}: {get_direct_children_ids(element.id, profile)}"
        )
        flat_ext = FlatteningLookupElement(
            parent=check_if_root(get_parent_element_id(element), profile),
            view_definition={
                "select": [],
            },
            children=get_direct_children_ids(element.id, profile),
        )

        lookup = {}
        if len(flat_ext.children) > 0:
            lookup.update({element_id: flat_ext})
        for child in flat_ext.children:
            lookup.update(flatten_element(child, profile, **kwargs))

        return lookup

    else:
        lookup = {}
        manager: FhirPackageManager = kwargs["manager"]

        if element.type[0].profile and (ext_profile_url := element.type[0].profile[0]):

            flat_ext_el = FlatteningLookupElement(
                parent=check_if_root(get_parent_element_id(element), profile),
                view_definition={
                    "forEachOrNull": f"extension.where(url = '{ext_profile_url}')",
                    "select": [],
                }
            )

            _logger.debug(f"Found profile for {element_id}: {ext_profile_url}")
            content_pattern = {
                "resourceType": "StructureDefinition",
                "url": ext_profile_url,
            }
            if ext_profile := manager.find(content_pattern):
                ext_profile: StructureDefinitionSnapshot
                _logger.debug(f"Found profile ->  following reference: {ext_profile_url}")
                ext_lookup = flatten_polymorphic(
                    "Extension.value[x]", ext_profile, **kwargs
                )
                lookup.update(
                    recontextualize_extension_lookup(ext_lookup, element_id, profile)
                )
                flat_ext_el.children = [f"{element_id}.value[x]"]

            lookup.update({element_id: flat_ext_el})

        return lookup


@register_flattener("CodeableConcept")
def flatten_codeable_concept(
    element_id: str, profile: StructureDefinitionSnapshot, **kwargs
) -> Dict[str, FlatteningLookupElement]:
    """
    This function flattens codeableConcepts.
        1. codeableConcept.coding is defined
            1. slices are defined => flatten slices too and return
            2. no slices defined => generic flattening (``el_system, el_code``)
        2. codeableConcept.coding => flatten generic (``el_system, el_code``)

    TODO: rewrite, 2 cases same outcome
    :param element_id: element id of codeableConcept
    :param profile: profile the element is in
    :param kwargs: kwargs passing through things like the profile manager and the terminology client
    :return: flattened extension with flattened children
    """
    element = profile.get_element_by_id(element_id)
    _logger.debug(f"Flattening codeableConcept {element_id}")

    flat_element = FlatteningLookupElement(
        parent=check_if_root(get_parent_element_id(element_id), profile)
    )
    flat_element.view_definition = {
        "forEachOrNull": element_id.split(".")[-1],
        "select": [],
    }

    # check if a conding is defined and the defined coding has any defined slices -> else col_el_sys + col_el_code
    # TODO: allow extensions too? if no coding does this mean that no other elements?
    child_coding_element = profile.get_element_by_id(f"{element_id}.coding")
    if child_coding_element is not None:
        list_of_children_slices = [
            slice.id
            for slice in get_available_slices(child_coding_element.id, profile)
            if len(slice.type) > 0 and "Coding" in slice.type[0].code
        ]
        if len(list_of_children_slices) > 0:
            _logger.debug(f"found slices: {list_of_children_slices}")
            flat_element.children = list_of_children_slices
        else:
            _logger.debug(
                f"creating two columns for {element_id} because no slice had been found \n"
                f"for coding: {child_coding_element.id if child_coding_element else ''}. "
                f"Make sure this is correct"
            )
            flat_element.view_definition = {
                "forEachOrNull": f"{element_id.split('.')[-1]}.coding",
                "column": [
                    {
                        "name": f"{id_to_column_name(element_id)}_system",
                        "path": "system",
                    },
                    {"name": f"{id_to_column_name(element_id)}_code", "path": "code"},
                ],
            }
            flat_element.children = []

        lookup = {element_id: flat_element}
        for child in flat_element.children:
            lookup.update(
                flatten_element(
                    child, profile, codeable_concept_parent=element_id, **kwargs
                )
            )

        return lookup
    else:
        _logger.debug(
            f"creating two columns for {element_id} because no slice had been found \n"
            f"for coding: {child_coding_element.id if child_coding_element else ''}. "
            f"Make sure this is correct"
        )
        flat_element.view_definition = {
            "forEachOrNull": f"{element_id.split('.')[-1]}.coding",
            "column": [
                {"name": f"{id_to_column_name(element_id)}_system", "path": "system"},
                {"name": f"{id_to_column_name(element_id)}_code", "path": "code"},
            ],
        }
        return {element_id: flat_element}


def generate_flattening_polymorphic_child(
    element_id: str, profile, polymorphic_parent: ElementDefinition, type=None, **kwargs
) -> Dict[str, FlatteningLookupElement] | None:
    """
    Helper function for flattening polymorphic children. This is done by flattening the child (coding, quantity)
     the correct way and then inserting the generated "columns"
     into the viewDefinition of the polymorphic child(valueCoding, valueQuantity).
     Note: the type is adjusted as some types like "uri" do not work in pathling as a type
    :param element_id: element of the polymorphic child
    :param profile: profile the element is in
    :param polymorphic_parent: parent which the child should point to
    :param type: element type for when dealing with 'pseudo' elements
    :param kwargs: passing through things like the profile manager and the terminology client
    :return: flattened polymorphic child and its children
    """
    element_type = type

    if profile.get_element_by_id(element_id):  # optional
        element_type = classify_element_type(profile.get_element_by_id(element_id))

    _logger.debug(f"Flattening polymorphic subtype {element_id} of type: {type}")
    polymorphic_element_name = polymorphic_parent.id.split(".")[-1].replace("[x]", "")
    fle = FlatteningLookupElement(parent=check_if_root(polymorphic_parent.id, profile))
    fle.view_definition = {
        "forEachOrNull": f"{polymorphic_element_name}.ofType({PATHLING_SUPPORTED_TYPE_CONVERTER.get(element_type, element_type)})",
        "select": [],
    }

    subtype_flat_element_lookup = flatten_element(
        element_id, profile, polymorphic_child=True, type=type, **kwargs
    )
    if subtype_flat_element := subtype_flat_element_lookup.get(element_id):
        lookup_list: Dict[str, FlatteningLookupElement] = subtype_flat_element_lookup
        lookup_list.pop(element_id)
        # if element is a primitive element => include the .column of the viewDefinition of the flattened result
        # else if element is a complex element => flatten children accordingly below
        col = subtype_flat_element.view_definition.get("column", "")
        if col:
            fle.view_definition["select"] = [
                {
                    "column": col
                }
            ]
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
    :param element_id: element id of the polymorphic element
    :param profile: profile of the element
    :param kwargs: passing through things like the profile manager and the terminology client
    :return: flattened element and flattened children
    """

    element = profile.get_element_by_id(element_id)

    _logger.debug(f"Flattening polymorphic {element_id}")

    flat_ext_parent = FlatteningLookupElement(
        parent=check_if_root(get_parent_element_id(element_id), profile)
    )
    flat_ext_parent.view_definition = {"select": []}

    possible_types = [t.code for t in element.type]
    slice_prefix = element_id.split(".")[-1].replace("[x]", "")

    # children that the profile does not define but which should be there based on the listed types
    undefined_children = [
        (f"{element_id}:{slice_prefix}{t[0].upper()}{t[1:]}", t) for t in possible_types
    ]

    # children that the profile defined
    # considering the children of this element is more bothering then useful
    # and for the flattening we only ever want the type slices anyway
    # Polymorphic elements which do not have the valueSlices defined as children, will then proceed
    # to add the children of the only type to the list they support. In case of Coding this means that
    # .code, .id, .system all get columns which, as discussed in the flatten_coding does not make sense
    # to add these in flattening
    # The only time when this should be considered is in the rare
    # case an extension is defined on the polymorphic element itself
    # defined_children_ids = [
    #     (child_id, get_element_type(profile.get_element_by_id(child_id)))
    #     for child_id in get_direct_children_ids(element_id, profile)
    # ]
    # theoretical

    # children_ids = set(undefined_children).union(defined_children_ids)

    flat_ext_parent.children = []
    lookup_list = {}
    for child, child_type in undefined_children:
        flat_ext_parent.children.append(child)
        lookup_list.update(
            generate_flattening_polymorphic_child(
                child, profile, element, type=child_type, **kwargs
            )
        )

    lookup_list.update({element_id: flat_ext_parent})
    return lookup_list


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
    :param element_id: primitive element
    :param profile: profile of element
    :param kwargs: passing through things like the profile manager and the terminology client
    :return: flattened element
    """
    element_type = (
        classify_element_type(profile.get_element_by_id(element_id))
        if profile.get_element_by_id(element_id)
        else (type if type else None)
    )
    _logger.debug(f"Flattening primitive {element_id} of type: {element_type}")

    flat_element = FlatteningLookupElement(
        parent=check_if_root(get_parent_element_id(element_id), profile)
    )
    flat_element.view_definition = {
        "column": [
            {
                "name": f"{id_to_column_name(element_id)}",
                "path": f"{element_id.split('.')[-1] if not polymorphic_child else '$this'}",
                "type": element_type,
            }
        ]
    }
    lookup = {element_id: flat_element}
    for child in get_direct_children_ids(element_id, profile):
        lookup.update(flatten_element(child, profile, **kwargs))
    return lookup


def flatten_element(
    element_id: str,
    profile: StructureDefinitionSnapshot,
    client: FhirTerminologyClient = None,
    type: str = None,
    **kwargs,
) -> Dict[str, FlatteningLookupElement]:
    """
    This function flattens all FHIR types, as long as there is a flattener defined for that type.
    To add a flattener for a new type, use this decorator: ``@register_flattener("Polymorphic")``
    :param element_id: element to be flattened
    :param profile: profile of the element
    :param client: terminology client
    :param type: explicit type for when dealing with 'pseudo' elements
    :param kwargs: passing through things like the profile manager and the terminology client
    :return: flattened element with flattened children
    """
    flat_lookup_els: Dict[str, FlatteningLookupElement] = {}
    element = profile.get_element_by_id(element_id)
    element_type = type if type else classify_element_type(element)
    f = FLATTEN_FUNCTIONS.get(element_type)
    if f:
        if res := f(element_id, profile, client=client, **kwargs):
            flat_lookup_els.update(res)

    else:
        _logger.error(f"No flattener defined for {element_type} for {element_id}")

    return flat_lookup_els


def generate_flattening_lookup_for_profile(
    profile, client, manager
) -> FlatteningLookup:
    """
    Function to generate flattening for an entire profile.
    :param profile: profile to be flattened
    :param client: terminology client
    :param manager: profile manager
    :return: lookup for the given profile
    """
    first_lvl_children = get_direct_children_ids(profile.type, profile)
    flat_lookup = FlatteningLookup(url=profile.url, resource_type=profile.type)

    for lvl1_el in first_lvl_children:
        flat_lookup.elements.update(
            flatten_element(lvl1_el, profile, client, manager=manager)
        )

    return flat_lookup


def generate_flattening_lookup(
    manager: FhirPackageManager, client: FhirTerminologyClient
) -> List[FlatteningLookup]:
    """
    Flatten all available profiles
    :param manager: package manager containing the profiles
    :param client: terminology client
    :return: list of lookups of found profiles
    """

    # read all profiles from DSE
    _logger.info("Generating flattening lookup files")
    content_pattern = {"resourceType": "StructureDefinition", "kind": "resource"}
    lookup_file: List[FlatteningLookup] = []

    for profile in manager.iterate_cache(
        MII_CDS_PACKAGE_PATTERN, content_pattern, skip_on_fail=True
    ):
        if profile.type in ["SearchParameter"]:
            continue
        if not isinstance(profile, StructureDefinition) and not profile.snapshot:
            _logger.warning(
                f"Profile '{profile.url}' is not in snapshot form => Skipping"
            )
            continue

        _logger.info(f"Generating flattening lookup for {profile.name}")

        profile: StructureDefinitionSnapshot
        lookup_all_children = generate_flattening_lookup_for_profile(
            profile, client, manager
        )
        # clean up empty children references which point to non-existing elements and remove empty children arrays
        lookup_existing_children = lookup_all_children.model_copy(deep=True)
        for key, el in lookup_all_children.elements.items():
            el: FlatteningLookupElement
            new_el = el.model_copy(deep=True)
            new_el.children = [
                child
                for child in (el.children or [])
                if child in lookup_all_children.elements
            ]
            if len(new_el.children) == 0:
                new_el.children = None

            lookup_existing_children.elements[key] = new_el

        lookup_file.append(lookup_existing_children)

    return lookup_file
