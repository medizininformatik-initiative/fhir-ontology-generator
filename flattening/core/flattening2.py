import copy
from typing import Optional, List, Dict, Tuple, Callable

from fhir.resources.R4B.elementdefinition import ElementDefinition
from fhir.resources.R4B.structuredefinition import StructureDefinition
from pydantic import BaseModel

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
REQUIRED_PRIMITIVE_PER_ELEMENT = {
    "Period": [("start", "dateTime"), ("end", "dateTime")],
    "Quantity": [("value", None), ("code", "code"), ("system", None)],
}
EXCLUDED_CHILDREN_CODINGS = ["userSelected", "id", "system", "display", "version"]


_logger = get_logger(__file__)


class FlatteningLookupElement(BaseModel):
    parent: Optional[str] = None
    view_definition: Optional[Dict] = None
    children: Optional[List[str]] = None


class FlatteningLookup(BaseModel):
    url: str
    resource_type: str
    elements: Dict[str, FlatteningLookupElement] = {}


FLATTEN_FUNCTIONS: dict[str, Callable[..., FlatteningLookupElement | None]] = {}


def register_flattener(*fhir_types: str):
    def wrapper(fn):
        for t in fhir_types:
            if t in FLATTEN_FUNCTIONS:
                raise RuntimeError(f"Flattener already registered for FHIR type '{t}'")
            FLATTEN_FUNCTIONS[t] = fn
        return fn

    return wrapper


def check_if_root(element_id: str, profile: StructureDefinitionSnapshot) -> str | None:
    return None if element_id == profile.type else element_id


def id_to_column_name(element_id: str) -> str:
    """
    Return the column name given an element.
        Column name is created by striping characters which are not allowed by pathling
    :param element_id: Element the column should refer to
    :return: column name for the given element
    """
    el_id: str = element_id
    # ':' and '.' and '-' and '[x]' are not allowed by pathling in column names, using '#' and '_' instead
    el_id = el_id.replace(":", "")
    el_id = el_id.replace(".", "_")
    el_id = el_id.replace("-", "")
    el_id = el_id.replace("[x]", "_X_")
    return el_id


def get_element_type(
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
        if element in el.id and get_parent_element_id(el) == element
    ]


def get_required_primitives_per_element(
    element: str,
    type: str,
) -> List[Tuple[str, str]]:
    # res = {}
    # child_elements = [f"{element}.{part_prim_id}" for part_prim_id in REQUIRED_PRIMITIVE_PER_ELEMENT.get(type)]
    # if f := FLATTEN_FUNCTIONS.get("primitive"):
    #     for child in child_elements:
    #         res.update(f(child, profile))

    return [
        (f"{element}.{part_prim_id}", part_prim_type)
        for (part_prim_id, part_prim_type) in (
            REQUIRED_PRIMITIVE_PER_ELEMENT.get(type)
            if REQUIRED_PRIMITIVE_PER_ELEMENT.get(type)
            else []
        )
    ]


def recontextualize_extension_lookup(
    ext_lookup: Dict[str, FlatteningLookupElement],
    element_id: str,
    profile: StructureDefinitionSnapshot,
) -> Dict[str, FlatteningLookupElement]:
    """
    "Extension.value[x]": {
      "parent": "Extension",
      "view_definition": {
        "forEachOrNull": "value[x].coding",
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
      },
      "children": []
      },
    """
    res_lookup = {}

    for key, lookup in ext_lookup.items():
        new_key = key.replace("Extension", element_id)
        new_lookup = copy.deepcopy(lookup)

        if new_lookup.view_definition.get("column"):
            for col in new_lookup.view_definition.get("column"):
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


@register_flattener("Coding")
def flatten_coding(
    element_id: str,
    profile: StructureDefinitionSnapshot,
    polymorphic_subtype: bool = False,
    codeable_concept_parent: str = None,
    **kwargs,
) -> Dict[str, FlatteningLookupElement] | None:

    element = profile.get_element_by_id(element_id)
    lookup = {}

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

    # parent coding
    if not codeable_concept_parent:
        if polymorphic_subtype:
            _logger.debug("Undefined behaviour: codeableConcept as polymorphic subtype")
            return None

        # # TODO: when no slices are found
        # flat_element = FlatteningLookupElement(
        #     parent=check_if_root(get_parent_element_id(element), profile)
        # )
        # flat_element.view_definition = {
        #     "forEachOrNull": element.id.split(".")[-1],
        #     "column": [
        #         {"name": f"{id_to_column_name(element.id)}_system", "path": "system"},
        #         {"name": f"{id_to_column_name(element.id)}_code", "path": "code"},
        #     ],
        # }
        # return {element.id:flat_element}
        return {}

    else:

        flat_element = FlatteningLookupElement(
            parent=check_if_root(codeable_concept_parent, profile)
        )
        # check pattern
        code_system_el = profile.get_element_by_id(f"{element.id}.system")
        if element.patternCoding or (code_system_el and code_system_el.patternUri):

            code_system_url = (
                code_system_el.patternUri
                if code_system_el and code_system_el.patternUri
                else element.patternCoding.system
            )
            flat_element.view_definition = {
                "forEachOrNull": f"{element.path.split('.')[-1]}.where(system = '{code_system_url}')",
                "select": [],
            }
            # it was decided to not include the following elements
            # for excluded in EXCLUDED_CHILDREN_CODINGS:
            #     full_el = f"{element.id}.{excluded}"
            #     if profile.get_element_by_id(full_el) is not None:
            #         el_to_flatten.pop(full_el)

            flat_element.children = [
                el.id
                for el in profile.snapshot.element
                if element.id in el.id
                and get_parent_element(profile, el).id == element.id
                # exclude from children too
                and el.id.split(".")[-1] not in EXCLUDED_CHILDREN_CODINGS
            ]

            lookup = {element.id: flat_element}
            for child in flat_element.children:
                lookup.update(flatten_element(child, profile, **kwargs))
            return lookup

        return None


@register_flattener(*["Reference"])
def flatten_reference(
    element_id: str, profile: StructureDefinitionSnapshot, **kwargs
) -> Dict[str, FlatteningLookupElement]:
    _logger.info(f"Flattening Reference: {element_id}")

    flat_reference_main = FlatteningLookupElement(
        parent=check_if_root(get_parent_element_id(element_id), profile)
    )
    flat_reference_main.view_definition = {
        "forEachOrNull": f"{element_id.split('.')[-1]}",
        "select":[]
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
        "forEachOrNull": f"reference",
        "column": [
            {
                "name": f"{id_to_column_name(ref_element_id)}",
                "path": f"$this",
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

    _logger.info(
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

    element_type = type
    if element := profile.get_element_by_id(element_id):
        element_type = get_element_type(element)
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
    #     => could cause duplicates
    required_primitives = get_required_primitives_per_element(element_id, element_type)
    for prim_id, prim_type in required_primitives:
        # filter for duplicates with .children
        if prim_id not in flat_generic_complex.children:
            flat_generic_complex.children.append(prim_id)
            lookup.update(flatten_primitive(prim_id, profile, type=prim_type))

    _logger.info(
        f"Flatten {element_id} of type {element_type} with children: {flat_generic_complex.children}"
    )
    return lookup


@register_flattener("Extension")
def flatten_extension(
    element_id: str,
    profile: StructureDefinitionSnapshot,
    **kwargs,
) -> Dict[str, FlatteningLookupElement]:

    element = profile.get_element_by_id(element_id)
    # flat_ext = FlatteningLookupElement(
    #     parent=check_if_root(get_parent_element_id(element), profile)
    # )
    # flat_ext.view_definition = {"forEachOrNull": element.id.split(".")[-1], "select": []}
    # parent extension
    if element.slicing is not None:
        # flat_ext.children = get_direct_children_ids(element.id, profile)
        print(
            f"Found children for {element_id}: {get_direct_children_ids(element.id, profile)}"
        )
        # flat_ext.view_definition = {
        #     "forEachOrNull": element.id.split(".")[-1],
        #     "select": [],
        # }
        #
        # if not flat_ext.children or len(flat_ext.children) < 0:
        #     return {}

        lookup = {}
        for child in get_direct_children_ids(element.id, profile):
            lookup.update(flatten_element(child, profile, **kwargs))

        return lookup

    else:
        lookup = {}
        manager: FhirPackageManager = kwargs["manager"]

        if element.type[0].profile is not None:
            ext_profile_url = element.type[0].profile[0]

            flat_ext_el = FlatteningLookupElement(
                parent=check_if_root(get_parent_element_id(element), profile)
            )
            flat_ext_el.view_definition = {
                "forEachOrNull": f"extension.where(url = '{ext_profile_url}')",
                "select": [],
            }

            print(f"Found profile for {element_id}: {ext_profile_url}")
            content_pattern = {
                "resourceType": "StructureDefinition",
                "url": ext_profile_url,
            }
            if ext_profile := manager.find(content_pattern):
                ext_profile: StructureDefinitionSnapshot
                print(f"Found profile ->  going deeper: {ext_profile_url}")
                ext_lookup = flatten_polymorphic(
                    f"Extension.value[x]", ext_profile, **kwargs
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
    element = profile.get_element_by_id(element_id)
    _logger.info(f"Flattening codeableConcept {element_id}")

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

    # Condition.onset[x]:onsetDateTime -> dateTime
    element_type = type

    if profile.get_element_by_id(element_id):  # optional
        element_type = get_element_type(profile.get_element_by_id(element_id))

    _logger.info(f"Flattening polymorphic subtype {element_id} of type: {type}")
    polymorphic_element_name = polymorphic_parent.id.split(".")[-1].replace("[x]", "")
    fle = FlatteningLookupElement(
        parent=check_if_root(polymorphic_parent.id, profile)
    )
    fle.view_definition = {
        "forEachOrNull": f"{polymorphic_element_name}.ofType({element_type})",
        "select": [],
    }

    subtype_flat_element_lookup = flatten_element(
        element_id, profile, polymorphic_child=True, type=type, **kwargs
    )
    if (subtype_flat_element := subtype_flat_element_lookup.get(element_id)) and subtype_flat_element is not None:
        lookup_list: Dict[str, FlatteningLookupElement] = subtype_flat_element_lookup
        lookup_list.pop(element_id)
        # if element is a primitive element => include the .column of the viewDefinition of the flattened result
        # else if element is a complex element => flatten children accordingly below
        col = subtype_flat_element.view_definition.get("column", "")
        if col:
            fle.view_definition["column"] = col
        fle.children = (
            subtype_flat_element.children
            if subtype_flat_element.children
            else get_direct_children_ids(element_id, profile)
        )
        lookup_list.update({element_id: fle})
        return lookup_list

    return {}

    # fle.children = get_direct_children_ids(element_id, profile)

    # flatten children if complex type, no need for if, because primitives do not have any other children
    # for child in fle.children:
    #     lookup_list.update(flatten_element(child, profile, **kwargs))
    #
    # # add if missing, required primitives. This applies only if these are not defined in the profile
    # required_primitives = get_required_primitives_per_element(element_id, element_type)
    # for prim_id, prim_type in required_primitives:
    #     if prim_id not in fle.children:
    #         fle.children.append(prim_id)
    #         lookup_list.update(flatten_primitive(prim_id, profile, type=prim_type))

    # lookup_list.update({element_id: fle})


@register_flattener("Polymorphic")
def flatten_polymorphic(
    element_id: str, profile: StructureDefinitionSnapshot, **kwargs
) -> Dict[str, FlatteningLookupElement]:

    element = profile.get_element_by_id(element_id)

    _logger.info(f"Flattening polymorphic {element_id}")

    # if element.slicing is not None:
    # polymorphic_element_name = element.id.split(".")[-1].replace("[x]", "")
    flat_ext_parent = FlatteningLookupElement(parent=check_if_root(get_parent_element_id(element_id), profile))
    flat_ext_parent.view_definition = {
        # "forEachOrNull": polymorphic_element_name,
        "select":[]
    }
    # flat_ext_parent.children = get_direct_children_ids(element_id, profile)

    # if element.slicing is not None:
    #     # slice_prefix = element_id.split(".")[-1].replace("[x]","")
    #     # flat_ext_parent.children = [f"{element_id}:{slice_prefix}{t}" for t in possible_types]
    #     # flat_ext_parent.children = get_direct_children_ids(element_id, profile)
    #
    #     lookup_list = {}
    #     # for child in flat_ext_parent.children:
    #     for child in get_direct_children_ids(element_id, profile):
    #         lookup_list.update(
    #             generate_flattening_polymorphic_child(child, profile, element, **kwargs)
    #         )
    #     return lookup_list
    # else:
    possible_types = [t.code for t in element.type]
    slice_prefix = element_id.split(".")[-1].replace("[x]", "")
    undefined_children = [
        (f"{element_id}:{slice_prefix}{t[0].upper()}{t[1:]}", t)
        for t in possible_types
    ]
    defined_children_ids = [
        (child_id, get_element_type(profile.get_element_by_id(child_id)))
        for child_id in get_direct_children_ids(element_id, profile)
    ]

    children_ids = set(undefined_children).union(defined_children_ids)

    flat_ext_parent.children = []
    lookup_list = {}
    for child, child_type in children_ids:
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
    :param type: type of element when element can't be found in profile
    :param polymorphic_child: if true => element is child of polymorphic element like Condition.onsetDateTime
    :param element_id: primitive element
    :param profile: profile of element
    :return: flattened element
    """
    element_type = (
        get_element_type(profile.get_element_by_id(element_id))
        if profile.get_element_by_id(element_id)
        else (type if type else None)
    )
    _logger.info(f"Flattening primitive {element_id} of type: {element_type}")

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
    flat_lookup_els: Dict[str, FlatteningLookupElement] = {}
    element = profile.get_element_by_id(element_id)
    element_type = type if type else get_element_type(element)
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
    first_lvl_children = get_direct_children_ids(profile.type, profile)
    flat_lookup = FlatteningLookup(url=profile.url, resource_type=profile.type)

    print(first_lvl_children)
    # print(FLATTEN_FUNCTIONS.keys())

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
    :return:
    """

    # read all profiles from DSE
    _logger.info("Generating flattening lookup files")
    content_pattern = {"resourceType": "StructureDefinition", "kind": "resource"}
    lookup_file: List[FlatteningLookup] = []
    # tqdm only ads a progress bar to output
    for profile in manager.iterate_cache(
        MII_CDS_PACKAGE_PATTERN, content_pattern, skip_on_fail=True
    ):
        if profile.type in ["SearchParameter"]:
            continue
        if not isinstance(profile, StructureDefinition) and not profile.snapshot:
            _logger.debug(
                f"Profile '{profile.url}' is not in snapshot form => Skipping"
            )
            continue

        # ONLY FOR TESTING
        if not profile.id in [
            "mii-pr-diagnose-condition",
            "mii-pr-person-patient",
            "mii-pr-person-patient-pseudonymisiert",
            "mii-pr-prozedur-procedure",
            "mii-pr-labor-laboruntersuchung",
        ]:
            continue

        _logger.info(f"Generating flattening lookup for {profile.name}")

        profile: StructureDefinitionSnapshot
        lookup = generate_flattening_lookup_for_profile(profile, client, manager)
        lookup_file.append(lookup)
    return lookup_file
