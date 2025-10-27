from typing import List, Tuple, Literal, Set

from fhir.resources.R4B.elementdefinition import ElementDefinition
from fhir.resources.R4B.structuredefinition import StructureDefinitionSnapshot

from cohort_selection_ontology.model.mapping import SimpleCardinality
from common.util.functions import foldl
from common.util.structure_definition.functions import get_parent_element


def select_element_compatible_with_cql_operations(
    element: ElementDefinition, snapshot: StructureDefinitionSnapshot
) -> (ElementDefinition, Set[str]):
    """
    Uses the given element to determine - if necessary - an element which is more suitable for generating the CQL
    mapping
    :param element: ElementDefinition instance to possibly replace
    :param snapshot: StructureDefinition instance in snapshot form to which the element belongs
    :return: Alternative element and targeted type if a more compatible element could be identified or the given
             element and its type if not
    """
    ### Select element were the slicing is defined
    if element.sliceName is not None:
        return select_element_compatible_with_cql_operations(
            get_parent_element(snapshot, element), snapshot
        )

    element_types = element.type if element.type else []
    element_type_codes = {t.code for t in element_types}
    compatible_element = element
    targeted_types = element_type_codes
    ### Coding -> CodeableConcept
    if len(element_types) == 1 and "Coding" in element_type_codes:
        # If the given element has type Coding which is part of the CodeableConcept type, the parent element is
        # returned to allow the CQL generation to use this information for query optimization
        # element_base_path = element.base.path
        if element.base and (element_base_path := element.base.path):
            targeted_type = element_base_path.split(".")[0]
            if targeted_type in {"CodeableConcept", "Reference"}:
                parent_element = get_parent_element(snapshot, element)
                if parent_element:
                    # Recurse until the actual ancestor element is reached. Slicing element definitions do not have
                    # such an element as their parent (direct ancestor)
                    compatible_element, _ = (
                        select_element_compatible_with_cql_operations(
                            parent_element, snapshot
                        )
                    )
                    targeted_types = {targeted_type}
        else:
            raise KeyError(
                f"Element [id='{element.id}'] is missing required 'ElementDefinition.base.path' "
                f"element which is required in snapshots"
            )
    return compatible_element if compatible_element else element, targeted_types


def aggregate_cardinality_using_element(
    element: ElementDefinition,
    snapshot: StructureDefinitionSnapshot,
    card_type: Literal["min", "max"] = "max",
) -> SimpleCardinality:
    """
    Aggregates the cardinality of an element along its path by collecting the cardinalities of itself and the parent
    elements and combining them to obtain the aggregated value as viewed from the root of the FHIR Resource
    :param element: Element to calculate the aggregated cardinality for
    :param snapshot: Snapshot of profile defining the element
    :param card_type: Type of cardinality to aggregate (either 'mix' or 'max')
    :return: Aggregated cardinality stating whether an element can occur multiple times or not
    """
    opt_element, _ = select_element_compatible_with_cql_operations(element, snapshot)
    card = SimpleCardinality.from_fhir_cardinality(getattr(opt_element, card_type))
    opt_element_path = opt_element.path
    is_root = opt_element_path.count(".") == 0
    match card:
        case SimpleCardinality.MANY:
            # End recursion since with the current enum members reaching this state leads to no further changes. An
            # exception will be made if the element is a root element since at that level we always assume singleton
            # occurrence (e.g. for paths like '<resource-type>')
            return SimpleCardinality.SINGLE if is_root else card
        case _:
            parent_element = get_parent_element(snapshot, opt_element)
            if opt_element_path == parent_element.id:
                opt_parent_el, _ = select_element_compatible_with_cql_operations(
                    parent_element, snapshot
                )
                grand_parent_el = get_parent_element(snapshot, opt_parent_el)
                if grand_parent_el is None and opt_element_path.count(".") == 0:
                    return SimpleCardinality.SINGLE
                # skip one parent
                return (
                    aggregate_cardinality_using_element(
                        grand_parent_el, snapshot, card_type
                    )
                    * card
                )

            match parent_element:
                case None:
                    if not is_root:
                        raise Exception(
                            f"No parent could be identified for element '{opt_element.id}' with "
                            f"non-root path '{opt_element_path}'"
                        )
                    else:
                        # The root element is always assumed to have `SINGLE` cardinality
                        return SimpleCardinality.SINGLE
                case parent_element:
                    return (
                        aggregate_cardinality_using_element(
                            parent_element, snapshot, card_type
                        )
                        * card
                    )


def aggregate_cardinality_of_element_chain(
    chain: List[Tuple[StructureDefinitionSnapshot, ElementDefinition]],
    card_type: Literal["min", "max"] = "max",
) -> SimpleCardinality:
    """
    Aggregates the cardinality of the element at the end of the provided element chain. It is assumed that the provided
    chains members represent subpaths in different scopes. For example, when considering the path::

    Resource1.element1.extension.valueReference.element2.element3

    the provided chain should have the following pattern::

    [(snapshot1, element[id=Resource1.element.extension]), (extSnapshot, element[id=Extension.valueReference]), (snapshot2, element[id=Resource2.element2.element3])]

    The aggregates cardinalities for each element will be combined to obtain the final result.

    :param chain: List of tuples of containing profile snapshot and element
    :param card_type: Type of cardinality to aggregate (either 'mix' or 'max')
    :return: Aggregated cardinality along the element chain
    """
    if len(chain) == 0:
        return SimpleCardinality.SINGLE
    return foldl(
        chain,
        SimpleCardinality.SINGLE,
        lambda acc, t: (
            acc
            if acc == SimpleCardinality.MANY
            else acc * aggregate_cardinality_using_element(t[1], t[0], card_type)
        ),
    )
