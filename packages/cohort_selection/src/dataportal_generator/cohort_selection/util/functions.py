from typing import List, Optional

from fhir.resources.R4B.elementdefinition import ElementDefinition

from cohort_selection_ontology.model.ui_profile import ValueSet
from dataportal_generator.common.exceptions.typing import InvalidValueTypeException
from dataportal_generator.common.fhir.structure_definition import resolve_defining_id
from dataportal_generator.common.model.fhir.idx_structure_definition import IdxStructureDefinition
from dataportal_generator.common.model.terminology import TermCode

from cohort_selection_ontology.core.terminology.client import CohortSelectionTerminologyClient as TerminologyClient


UCUM_SYSTEM = "http://unitsofmeasure.org"


def get_selectable_concepts(
    concept_defining_element: ElementDefinition,
    profile_name: str = "",
    client: TerminologyClient = None,
) -> ValueSet:
    # TODO: still needs test
    """
    Returns the answer options for the given concept defining element
    :param concept_defining_element: ``ElementDefinition`` that defines the concept
    :param profile_name: name of the FHIR profile for debugging purposes. Can be omitted
    :param client: Client to perform terminology server operations with
    :return: answer options as term codes
    :raises InvalidValueTypeException: if no valueSet is defined for the concept defining element
    """
    if binding := concept_defining_element.binding:
        if value_set_url := binding.valueSet:
            if "|" in value_set_url:
                value_set_url = value_set_url.split("|")[0]
            return ValueSet(
                url=value_set_url,
                valueSet=client.get_value_set_expansion(value_set_url),
            )
        else:
            raise InvalidValueTypeException(
                f"No value set defined in element: {str(binding)}"
                f" in profile: {profile_name}"
            )
    else:
        raise InvalidValueTypeException(
            f"No binding defined in element: {str(concept_defining_element.id)}"
            f" in profile: {profile_name}"
        )


def get_units(
    unit_defining_element: ElementDefinition,
    profile_name: str = "",
    client: TerminologyClient = None,
) -> List[TermCode]:
    """

    :param profile_name: Name of the FHIR profile for debugging purposes. Can be omitted
    :param unit_defining_element: ``ElementDefinition`` that defines the unit
    :param client: Client to perform terminology server operations with
    :return: a list of term codes

    Returns:

    """
    # TODO: still needs test
    if unit_code := unit_defining_element.fixedCode:
        return [TermCode(system=UCUM_SYSTEM, code=unit_code, display=unit_code)]
    elif unit_code := unit_defining_element.patternCode:
        return [TermCode(system=UCUM_SYSTEM, code=unit_code, display=unit_code)]
    elif binding := unit_defining_element.binding:
        if value_set_url := binding.valueSet:
            return client.get_termcodes_for_value_set(value_set_url)
        else:
            raise InvalidValueTypeException(
                f"No value set defined in element: {str(binding)}"
                f" in profile: {profile_name}"
            )
    else:
        raise InvalidValueTypeException(
            f"No unit defined in element: {str(unit_defining_element.id)}"
            f" in profile: {profile_name}"
        )


def pattern_coding_to_term_code(element: ElementDefinition, client: TerminologyClient):
    # TODO: write .tests
    """
    Converts a patternCoding to a term code
    :param element: Element node from the snapshot with a patternCoding
    :param client: Client instance to perform terminology server operations
    :return: Term code
    """
    code = element.patternCoding.code
    system = element.patternCoding.system
    display = client.get_term_code_display(system, code)
    version = str(element.patternCoding.version)

    if display.isupper():
        display = display.title()
    term_code = TermCode(system=system, code=code, display=display, version=version)
    return term_code


def fixed_coding_to_term_code(
    element: ElementDefinition,
    client: TerminologyClient,
):
    # TODO: unit .tests
    """
    Converts a fixedCoding to a term code
    :param element: Element node from the snapshot with a patternCoding
    :param client: Client instance to perform terminology server operations
    :return: Term code
    """
    code = element.fixedCoding.code
    system = element.fixedCoding.system
    display = client.get_term_code_display(system, code)
    if display.isupper():
        display = display.title()
    term_code = TermCode(system=system, code=code, display=display)
    return term_code


def pattern_codeable_concept_to_term_code(
    element: ElementDefinition, client: TerminologyClient
):
    # TODO: unit .tests

    """
    Converts a patternCodeableConcept to a term code
    :param element: Element node from the snapshot with a patternCoding
    :param client: Client instance to perform terminology server operations
    :return: Term code
    """
    code: str = element.patternCodeableConcept.coding[0].code
    system: str = element.patternCodeableConcept.coding[0].system
    display: str = client.get_term_code_display(system, code)
    version = element.patternCodeableConcept.coding[0].version
    if display.isupper():
        display = display.title()
    term_code = TermCode(system=system, code=code, display=display, version=version)
    return term_code


def fixed_codeable_concept_to_term_code(
    element: ElementDefinition, client: TerminologyClient
):
    # TODO: unit .tests
    """
    Converts a fixedCodeableConcept to a term code
    :param element: Element node from the snapshot with a patternCoding:
    :param client: Client instance to perform terminology server operations
    :return: Term code
    """
    code = element.patternCodeableConcept.coding[0].code
    system = element.patternCodeableConcept.coding[0].system
    display = client.get_term_code_display(system, code)
    version = element.fixedCodeableConcept.coding[0].version
    if display.isupper():
        display = display.title()
    term_code = TermCode(system=system, code=code, display=display, version=version)
    return term_code


def get_value_set_defining_url(
    value_set_defining_element: ElementDefinition, profile_name: str = ""
) -> str:
    # TODO: decide to keep and test? no usage in project found.
    #  Everywhere where i could be used its skipping this function using binding.valueSet directly
    """
    Returns the value set defining url for the given value set defining element
    :param value_set_defining_element: ``ElementDefinition`` that defines the value set
    :param profile_name: Name of the FHIR profile for debugging purposes. Can be omitted
    :raises InvalidValueTypeException: if no valueSet or binding is defined
    :return: Canonical URL of the value set
    """
    if binding := value_set_defining_element.binding:
        if value_set_url := binding.valueSet:
            return value_set_url
        raise InvalidValueTypeException(
            f"No value set defined in element: {str(binding)}"
            f" in profile: {profile_name}"
        )
    else:
        raise InvalidValueTypeException(
            f"No binding defined in element: {str(value_set_defining_element)}"
            f" in profile: {profile_name}"
        )


def try_get_term_code_from_sub_elements(
    profile_snapshot: IdxStructureDefinition,
    parent_coding_id,
    data_set_dir,
    module_dir,
    client: TerminologyClient,
) -> Optional[TermCode]:
    """"""
    if profile_snapshot.get_element_by_id(parent_coding_id + ".code") is not None:
        return None
    code_element = resolve_defining_id(
        profile_snapshot, parent_coding_id + ".code", data_set_dir, module_dir
    )
    system_element = resolve_defining_id(
        profile_snapshot,
        parent_coding_id + ".system",
        data_set_dir,
        module_dir,
    )
    if code_element and system_element:
        if "patternCode" in code_element and "patternUri" in system_element:
            return TermCode(
                system=system_element["patternUri"],
                code=code_element["patternCode"],
                display=client.get_term_code_display(
                    system_element["patternUri"], code_element["patternCode"]
                ),
            )
        if "fixedCode" in code_element and "fixedUri" in system_element:
            return TermCode(
                system=system_element["fixedUri"],
                code=code_element["fixedCode"],
                display=client.get_term_code_display(
                    system_element["fixedUri"], code_element["fixedCode"]
                ),
            )

    return None


def get_fixed_term_codes(
    profile_snapshot: IdxStructureDefinition,
    element: ElementDefinition,
    module_dir,
    data_set_dir,
    client: TerminologyClient,
) -> List[TermCode]:
    """
    Returns the fixed term codes of the given element
    """
    if element.fixedCodeableConcept is not None:
        return [fixed_codeable_concept_to_term_code(element, client)]
    elif element.patternCodeableConcept is not None:
        return [pattern_codeable_concept_to_term_code(element, client)]
    elif element.fixedCoding is not None and element.fixedCoding.code is not None:
        return [fixed_coding_to_term_code(element, client)]
    elif element.patternCoding is not None and element.patternCoding.code is not None:
        return [pattern_coding_to_term_code(element, client)]
    else:
        if tc := try_get_term_code_from_sub_elements(
            profile_snapshot, element.id, module_dir, data_set_dir, client
        ):
            return [tc]
    return []


def get_term_code_by_id(
    profile_snapshot: IdxStructureDefinition,
    term_code_defining_id: str,
    data_set_dir,
    module_dir,
    client: TerminologyClient,
) -> List[TermCode]:
    """
    Returns the term entries for the given term code defining id
    :param profile_snapshot: IdxStructureDefinition which the term_code_defining_id belong to
    :param term_code_defining_id: ID of the element that defines the term code
    :param data_set_dir: Data set directory of the FHIR profile
    :param module_dir: Module directory of the FHIR profile
    :param client: Client instance to perform terminology server operations
    :return: Term entries
    """
    if not term_code_defining_id:
        raise Exception(
            f"No term code defining id given print for {profile_snapshot.name}"
        )

    term_code_defining_element = resolve_defining_id(
        profile_snapshot, term_code_defining_id, data_set_dir, module_dir
    )
    if not term_code_defining_element:
        raise Exception(
            f"Could not resolve term code defining id {term_code_defining_id} "
            f"in {profile_snapshot.name}"
        )
    if term_code_defining_element.patternCoding is not None:
        if term_code_defining_element.patternCoding.code is not None:
            term_code = pattern_coding_to_term_code(term_code_defining_element, client)
            return [term_code]
    if term_code_defining_element.patternCodeableConcept is not None:
        if term_code_defining_element.patternCodeableConcept.coding is not None:
            term_code = pattern_codeable_concept_to_term_code(
                term_code_defining_element, client
            )
            return [term_code]
    if term_code_defining_element.binding:
        value_set = term_code_defining_element.binding.valueSet
        return client.get_termcodes_for_value_set(value_set)
    else:
        tc = try_get_term_code_from_sub_elements(
            profile_snapshot,
            term_code_defining_id,
            data_set_dir,
            module_dir,
            client,
        )
        if tc:
            return [tc]
        raise Exception(
            f"Could not resolve term code defining element: {term_code_defining_id}"
        )