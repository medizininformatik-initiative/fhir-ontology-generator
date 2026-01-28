from typing import Dict, List, Optional

from fhir.resources.R4B.elementdefinition import ElementDefinition
from fhir.resources.R4B.structuredefinition import StructureDefinition
from pydantic import BaseModel, Field

from availability.constants.fhir import MII_CDS_PACKAGE_PATTERN
from common.model.structure_definition import (
    StructureDefinitionSnapshot,
)
from common.util.fhir.package.manager import FhirPackageManager
from common.util.http.terminology.client import FhirTerminologyClient
from common.util.log.functions import get_logger
from common.util.structure_definition.functions import (
    get_parent_element_id,
    get_available_slices,
    get_parent_element,
)

_logger = get_logger(__file__)
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


class FlatteningLookupElement(BaseModel):
    parent: str
    viewDefinition: Optional[Dict] = None
    children: Optional[List[str]] = None


class FlatteningLookup(BaseModel):
    url: str
    resource_type: str
    elements: Dict[str, FlatteningLookupElement] = Field(default={})


def id_to_column_name(element) -> str:
    """
    Return the column name given an element.
        Column name is created by striping characters which are not allowed by pathling
    :param element: Element the column should refer to
    :return: column name for the given element
    """
    el_id: str = element.id
    # ':' and '.' and '-' and '[x]' are not allowed by pathling in column names, using '#' and '_' instead
    el_id = el_id.replace(":", "")
    el_id = el_id.replace(".", "_")
    el_id = el_id.replace("-", "")
    el_id = el_id.replace("[x]", "_X_")
    return el_id


def get_direct_children_ids(element, profile) -> List[str]:
    """
    Returns the list of ids of direct children . All elements 1 level below.
    Example::

        get_direct_children_ids(ElementDefinition("Condition.code.coding"), profile)
        ->  ["code", "system", "version", "display", "userSelected"]

    :param element: element from which to get the children from
    :param profile: snapshot of the profile of the element in question
    :return: list of children ids
    """
    return [
        el.id
        for el in profile.snapshot.element
        if element.id in el.id and get_parent_element(profile, el).id == element.id
    ]


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
        return element.type[0].code

    if element.id == element.path:
        return None
    else:
        _logger.warning(f"No type found for element {element.id} => Skipping")

    return None


# def get_child_coding_slices(
#     element: ElementDefinition, profile: StructureDefinitionSnapshot
# ) -> List[ElementDefinition]:
#
#     found_codings_slices: Set[ElementDefinition] = set()
#
#     for el in profile.snapshot.element:
#         if ":" in el.id and element.id in get_parent_slice_id(el.id):
#             found_codings_slices.add(el)
#
#     return list(found_codings_slices)


def flatten_Coding(
    element: ElementDefinition,
    profile: StructureDefinitionSnapshot,
    client: FhirTerminologyClient,
    el_to_flatten: Dict[str, Dict],
) -> FlatteningLookupElement | None:
    """
    This function creates the lookup for coding elements. There are two types of codings:
        1. **codings without a sliceName** : These act like a "parent" coding and
            define the structure of the slices, thus are not present in instance data which
                1. parent is of type "CodeableConcept" this coding can be **ignored**
                as it does not hold any information and
                is not even present in the instance data, thus it is not relevant for flattening.
                Also because of this direct children  like .code .display etc. are **removed** form el_to_flatten
                Child slices will be processed separately

                2. If coding parent is **not** of type "CodeableConcept":
                    - and has no slices defined ``el_code`` and ``el_system`` columns are created
                    - and has slices defined: to be implemented, probably same like codeable concept
                        TODO: IS THIS EVEN POSSIBLE?

        2. **codings with a sliceName** : These are children of the codings of type 1 and define the slices.
            fle.parent will point to the CodeableConcept, skipping the .coding (type 1) level
            => Use the ``codeableConcept`` these codings are a children of in::
                Example: parent for (Condition.code.coding:sct) is "Condition.code" (codeableConcept)
            fle.viewDefinition. ``ForEachOrNull`` should include the parent ``coding`` (See example below)

    Example lookup for coding-children (type 2)::

      "Condition.code.coding:sct": {
        "parent": "Condition.code",
        "viewDefinition": {
          "forEachOrNull": "coding.where(system = 'http://snomed.info/sct')",
          "select": []
        },
        "children": [
          "Condition.code.coding:sct.id",
          "Condition.code.coding:sct.extension",
          "Condition.code.coding:sct.system",
          "Condition.code.coding:sct.version",
          "Condition.code.coding:sct.code",
          "Condition.code.coding:sct.display",
          "Condition.code.coding:sct.userSelected"
        ]
      },

    :param element: coding element to be flattened
    :param profile: profile of the element
    :param client: terminology client used to expand valuesets in bindings
    :param el_to_flatten: list of elements to be flattened
    :return: flattened element
    """
    code_system_url: str
    # value_set_url: str

    # Handling of parent codings | not a slice
    if element.sliceName is None:
        parent = get_parent_element(profile, element)

        # delete all lvl1 children which do not contain any information
        # Optional: these can never be selected in dse
        # coding:   .code .system .version .display .userSelected
        for el_id in get_direct_children_ids(element, profile):
            if el_id in el_to_flatten:
                el_to_flatten.pop(el_id)

        # Case 1: Coding inside CodeableConcept.coding → ignore
        if parent and get_element_type(parent) == "CodeableConcept":
            _logger.debug("Is CodeableConcept.coding parent => Ignoring")
            return None

        # Case 2: Standalone Coding (e.g. meta.security) → flatten normally
        # if element.binding is None:
        # TODO: Where are the children?
        _logger.debug("Standalone Coding => creating columns")
        fle = FlatteningLookupElement(parent=get_parent_element_id(element))
        fle.viewDefinition = {
            "forEachOrNull": element.id.split(".")[-1],
            "column": [
                {"name": f"{id_to_column_name(element)}_system", "path": "system"},
                {"name": f"{id_to_column_name(element)}_code", "path": "code"},
            ],
        }
        return fle
        # else: TODO: diskus if this is even necessary, or smart (extract codesystems from valueSet)
        #     systems = set()
        #     valueSet = client.expand_value_set(element.binding.valueSet)
        #     if valueSet:
        #         for entry in valueSet.get("expansion").get("parameter"):
        #             if entry.get("name") == "used-codesystem":
        #                 uri = entry.get("valueUri")
        #                 if uri:
        #                     system = uri.split("|", 1)[0]
        #                     systems.add(system)
        #     _logger.info(f"found following codesystems for binding of {element.id}: \n "
        #                  f"{systems.__str__()}")

        # for generate all codesystem posibilities

    # parent CodeableConcept is used as parent for slices. Its two levels above
    # example: Condition.code.coding:sct -> Condition.code
    parent_codeableConcept: ElementDefinition = get_parent_element(
        profile, get_parent_element(profile, element)
    )
    if get_element_type(parent_codeableConcept) != "CodeableConcept":
        _logger.debug(
            "Undefined behaviour: Slice.parent reference does not point to a codeableConcept"
        )
        return None

    fle = FlatteningLookupElement(parent=parent_codeableConcept.id)
    # check pattern
    code_system_el = profile.get_element_by_id(f"{element.id}.system")
    if element.patternCoding or (code_system_el and code_system_el.patternUri):

        code_system_url = (
            code_system_el.patternUri
            if code_system_el and code_system_el.patternUri
            else element.patternCoding.system
        )
        fle.viewDefinition = {
            "forEachOrNull": f"{element.path.split('.')[-1]}.where(system = '{code_system_url}')",
            # "column": [{"name": id_to_column_name(element), "path": "code"}],
            "select": [],
        }
        fle.children = [
            el.id
            for el in profile.snapshot.element
            if element.id in el.id and get_parent_element(profile, el).id == element.id
        ]

    # TODO: check binding
    # if "binding" in element.__dict__.keys():
    #     value_set_url = element.binding.valueSet
    # else: TODO: AGAIN diskus if this is even necessary, or smart (extract codesystems from valueSet)

    # TODO: check fixed

    return fle


def flatten_CodeableConcept(
    element: ElementDefinition, profile: StructureDefinitionSnapshot
) -> FlatteningLookupElement | None:
    """
    This function flattens an element of type CodeableConcept.
        If the child coding has any slices defined, the slice ids are saved as children.
            The children slices will be processed in the flatten_Coding function.
        Else this function creates two columns: el_system, el_code.
        When evaluating the viewDefinition all coding instances will be listed as rows with slices as columns
    :param element: codeableConcept to be flattened
    :param profile: profile of element codeableConcept
    :return: flattened element
    """

    # part of polymorphic element
    if element.sliceName is not None or "[x]" in element.path.split(".")[-1]:
        _logger.debug("Child of polymorphic element. Not yet implemented => Skipping")
        # TODO: implement later with ofType....
        return None

    fle = FlatteningLookupElement(parent=get_parent_element_id(element))
    fle.viewDefinition = {"forEachOrNull": element.id.split(".")[-1], "select": []}

    # check if a conding is defined and the defined coding has any defined slices -> else col_el_sys + col_el_code
    child_coding_element = profile.get_element_by_id(f"{element.id}.coding")
    if child_coding_element is not None:
        list_of_children_slices = [
            slice.id
            for slice in get_available_slices(child_coding_element.id, profile)
            if len(slice.type) > 0 and "Coding" in slice.type[0].code
        ]
        if len(list_of_children_slices) > 0:
            _logger.debug(f"found slices: {list_of_children_slices.__str__()}")
            fle.children = list_of_children_slices
            return fle

    _logger.debug(
        f"creating two columns for {element.id} because no slice had been found \n"
        f"for coding: {child_coding_element.id if child_coding_element else ''}. "
        f"Make sure this is correct"
    )
    fle.viewDefinition = {
        "forEachOrNull": f"{element.id.split('.')[-1]}.coding",
        "column": [
            {"name": f"{id_to_column_name(element)}_system", "path": "system"},
            {"name": f"{id_to_column_name(element)}_code", "path": "code"},
        ],
    }
    return fle


def flatten_Quantity(
    element: ElementDefinition, profile: StructureDefinitionSnapshot
) -> FlatteningLookupElement | None:
    """
    This function flattens an element of type "Quantity".
    - Quantity child of polymorphic element flattened using the ".ofType" fhir syntax
    - Quantity not child of polymorphic element: TODO: is this even possible?
    :param element: quantity element to be flattened
    :param profile: profile of element
    :return: flattened element
    """

    if element.sliceName is not None and "[x]" in element.path.split(".")[-1]:
        fle = FlatteningLookupElement(parent=get_parent_element_id(element))
        fle.viewDefinition = {
            "forEachOrNull": f"{element.sliceName.replace('Quantity','')}.ofType(Quantity)",
            "select": [],
        }
        fle.children = [
            el.id
            for el in profile.snapshot.element
            if element.id in el.id and get_parent_element(profile, el).id == element.id
        ]
        _logger.debug(f"Found quantity children: {fle.children}")
        return fle

    _logger.debug(
        "Quantity not child of polymorphic element. Not yet implemented => Skiping"
    )
    return None


def flatten_primitive(
    element: ElementDefinition, profile: StructureDefinitionSnapshot, type: str
):
    """
    Flatten all primitives defined in FHIR_PRIMITIVES.
    All other flatten functions for complex types (apart from some exceptions)
     create the structures around these primitives
     for which a generic pattern like the one below, can be used
    :param element: primitive element
    :param profile: profile of element
    :param type: fhir type to be used in the viewDefinition
    :return: flattened element
    """
    fle = FlatteningLookupElement(parent=get_parent_element_id(element))
    fle.viewDefinition = {
        "column": [
            {
                "name": f"{id_to_column_name(element)}",
                "path": f"{element.id.split('.')[-1]}",
                "type": type,
            }
        ]
    }
    return fle


def flatten_BackboneElement(
    element: ElementDefinition, profile: StructureDefinitionSnapshot
) -> FlatteningLookupElement | None:
    """
    Flatten a "BackboneElement" element by listing all children elements.
     This structure does not contain any information itself.
    :param element: BackboneElement to be flattened
    :param profile: profile of element
    :return: flattened element
    """

    fle = FlatteningLookupElement(parent=get_parent_element_id(element))
    # determine children, base.path
    fle.children = get_direct_children_ids(element, profile)
    fle.viewDefinition = {"forEachOrNull": element.id.split(".")[-1], "select": []}

    _logger.debug(fle.children)
    return fle


def flatten_Reference(
    element: ElementDefinition, profile: StructureDefinitionSnapshot
) -> FlatteningLookupElement | None:
    """
    Flattens element of type "Reference". The element containing
     a references information in the instance data is in fact "...el.reference"
    :param element: element to be flattened
    :param profile: profile of the element
    :return: flattened element
    """

    fle = FlatteningLookupElement(parent=get_parent_element(profile, element).id)
    fle.viewDefinition = {
        "forEachOrNull": f"{element.id.split('.')[-1]}",
        "column": [
            {
                "name": f"{id_to_column_name(element)}",
                "path": f"reference",
            }
        ],
    }

    return fle


def flatten_dateTime(
    element: ElementDefinition, profile: StructureDefinitionSnapshot
) -> FlatteningLookupElement | None:
    """
    Flattens element of type "dateTime". Special case when a child of polymorphic element.
    :param element: element to be flattened
    :param profile: profile of the element
    :return: flattened element
    """

    # is it part of polymorphic element
    if element.sliceName is not None and "[x]" in element.path.split(".")[-1]:
        # Condition.onset[x]:onsetDateTime -> grandparent: Condition
        parent_element = get_parent_element(profile, element)
        grand_parent_element = get_parent_element(profile, parent_element)
        fle = FlatteningLookupElement(parent=grand_parent_element.id)
        fle.viewDefinition = {
            "forEachOrNull": f"{element.sliceName.replace('DateTime','')}.ofType(dateTime)",
            "column": [
                {
                    "name": f"{id_to_column_name(element)}",
                    "path": f"$this",
                }
            ],
        }
        return fle

    fle = FlatteningLookupElement(parent=get_parent_element(profile, element).id)
    fle.viewDefinition = {
        "column": [
            {
                "name": f"{id_to_column_name(element)}",
                "path": f"{element.id.split('.')[-1]}",
            }
        ]
    }

    return fle


def flatten_Period(
    element: ElementDefinition, profile: StructureDefinitionSnapshot
) -> FlatteningLookupElement | None:
    """
    Flattens element of type "Period". Special case when a child of polymorphic element.
    :param element: element to be flattened
    :param profile: profile of the element
    :return: flattened element
    """

    # is it part of polymorphic element
    if element.sliceName is not None and "[x]" in element.path.split(".")[-1]:
        # Condition.onset[x]:onsetPeriod -> grandparent: Condition
        parent_element = get_parent_element(profile, element)
        grand_parent_element = get_parent_element(profile, parent_element)
        fle = FlatteningLookupElement(parent=grand_parent_element.id)
        fle.viewDefinition = {
            "forEachOrNull": f"{element.sliceName.replace('Period','')}.ofType(Period)",
            "select": [],
        }
        fle.children = [
            el.id
            for el in profile.snapshot.element
            if element.id in el.id and get_parent_element(profile, el).id == element.id
        ]
        _logger.debug(f"found children for Period: {fle.children.__str__()}")
        # TODO: WHAT IF NO CHILDREN ARE FOUND: Procedure.performed[x]:performedPeriod
        # add .start .end anyway?
        return fle

    # TODO: handle simple case
    # fle = FlatteningLookupElement(parent=get_parent_element(profile, element).id)
    # fle.viewDefinition = {"forEachOrNull": element.id.split(".")[-1], "select": []}
    #
    # fle.children = [
    #     el.id for el in profile.snapshot.element if element.id in el.id and get_parent_element(profile,el).id == element.id
    # ]

    return None


def flatten_polymorphic_element(
    element: ElementDefinition, profile: StructureDefinitionSnapshot
) -> FlatteningLookupElement | None:
    # TODO: Maybe trying to generalize would be a good idea. As of now, all types special cases
    pass


def flatten_element(
    element: ElementDefinition,
    profile: StructureDefinitionSnapshot,
    client: FhirTerminologyClient,
    el_to_flatten: Dict[str, Dict],
) -> FlatteningLookupElement | None:
    """
    Flattens an element according to its type
    :param element: element to be flattened
    :param profile: profile of the element
    :param client: terminology client
    :param el_to_flatten: list of elements to flatten
    :return: flattened element
    """
    match get_element_type(element):
        case "Coding":
            _logger.debug("Found coding")
            return flatten_Coding(element, profile, client, el_to_flatten)
        case "CodeableConcept":
            _logger.debug("Found codeableConcept")
            return flatten_CodeableConcept(element, profile)
        case "BackboneElement" | "Meta":
            _logger.debug("Found backbone")
            return flatten_BackboneElement(element, profile)
        case "Quantity":
            _logger.debug("Found Quantity")
            return flatten_Quantity(element, profile)
        case "Reference":
            _logger.debug("Found reference")
            return flatten_Reference(element, profile)
        case "Period":
            _logger.debug("Found Period")
            return flatten_Period(element, profile)
        case "Polymorphic":
            _logger.debug("Found dateTime")
            return flatten_polymorphic_element(element, profile)
        case "dateTime":
            _logger.debug("Found dateTime")
            return flatten_dateTime(element, profile)
        case t if t in FHIR_PRIMITIVES:
            _logger.debug(f"Found primitive type: {t}")
            return flatten_primitive(element, profile, str(t))

    return None


def generate_flattening_lookup_for_profile(
    profile: StructureDefinitionSnapshot, client: FhirTerminologyClient
) -> FlatteningLookup:
    """
    Flattens an entire Profile.
    :param profile: element to be flattened
    :param client: terminology client
    :return: Lookup table for the given profile
    """
    fl = FlatteningLookup(url=profile.url, resource_type=profile.type)
    elements = {value.id: value for value in profile.snapshot.element}
    elements = dict(sorted(elements.items(), key=lambda item: len(item[0]), reverse=True))
    while elements:
        element: ElementDefinition
        key, element = elements.popitem()
        _logger.debug(f"{element.id}")
        if (
            fle := flatten_element(element, profile, client, el_to_flatten=elements)
        ) is not None:
            fl.elements[element.id] = fle

    return fl


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
    content_pattern = {
        "resourceType": "StructureDefinition",
        "kind": "resource",
    }
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
        # if not profile.id in [
        #     "mii-pr-diagnose-condition",
        #     "mii-pr-person-patient",
        #     "mii-pr-person-patient-pseudonymisiert",
        #     "mii-pr-prozedur-procedure",
        #     "mii-pr-labor-laboruntersuchung",
        # ]:
        #     continue

        _logger.info(f"Generating flattening lookup for {profile.name}")

        profile: StructureDefinitionSnapshot
        lookup = generate_flattening_lookup_for_profile(profile, client)
        lookup_file.append(lookup)
    return lookup_file
