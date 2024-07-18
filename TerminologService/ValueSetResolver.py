from __future__ import annotations

from typing import List

import requests

from TerminologService.TermServerConstants import TERMINOLOGY_SERVER_ADDRESS, SERVER_CERTIFICATE, PRIVATE_KEY, MAPPING_ONTO_VERSION
from TerminologService.valueSetToRoots import create_vs_tree, expand_value_set
from model.UiDataModel import TermCode

POSSIBLE_CODE_SYSTEMS = ["http://loinc.org", "http://snomed.info/sct"]


# Some valueSets are to big to execute the closure operation on the Ontoserver. We need to filter them out.


def get_term_entries_from_onto_server(value_set_canonical_url: str):
    """
    Get the term entries roots from the Ontoserver based on the given value set canonical url.
    :param value_set_canonical_url: The canonical url of the valueSet
    :return: Sorted term_entry roots of the value set hierarchy
    """
    value_set_canonical_url = value_set_canonical_url.replace("|", "&version=")
    print(value_set_canonical_url)
    # In Gecco 1.04 all icd10 elements with children got removed this brings them back. Requires matching valuesSets on
    # Ontoserver
    # if value_set_canonical_url.endswith("icd"):
    #     value_set_canonical_url = value_set_canonical_url + "-with-parent"
    result = create_vs_tree(value_set_canonical_url)
    if len(result) < 1:
        raise Exception("ERROR", value_set_canonical_url)
    return result


def get_termcodes_from_onto_server(value_set_canonical_url: str, onto_server: str = TERMINOLOGY_SERVER_ADDRESS) -> \
        List[TermCode]:
    """
    Get the term codes from the Ontoserver based on the given value set canonical url.
    :param value_set_canonical_url: The canonical url of the valueSet
    :param onto_server: url of the terminology server
    :return: returns the sorted list of term codes of the value set prioritized by the coding system:
    icd10 > snomed
    """
    return list(expand_value_set(value_set_canonical_url, onto_server))


def get_term_code_from_contains(contains):
    """
    Extracts the term code from the contains element of the value set expansion
    :param contains: contains element of the value set expansion
    :return: term code
    """
    system = contains["system"]
    code = contains["code"]
    display = contains["display"]
    term_code = TermCode(system, code, display)
    if system == "http://snomed.info/sct":
        if "designation" in contains:
            for designation in contains["designation"]:
                if "language" in designation and designation["language"] == "de-DE":
                    term_code.display = designation["value"]
    return term_code


def get_answer_list_code(response: dict) -> str | None:
    """
    Get the loinc answer list code from the Ontoserver based on the lookup response information.
    :param response: lookup response of ta loinc code
    :return: the answer list code of the loinc code or None if no answer list is available
    """
    if parameters := response.get("parameter"):
        for parameter in parameters:
            if parts := parameter.get("part"):
                next_is_answer_list = False
                for part in parts:
                    if next_is_answer_list and (valueCode := part.get("valueCode")):
                        return valueCode
                    if (valueCode := part.get("valueCode")) and (valueCode == "answer-list"):
                        next_is_answer_list = True
    return None


def get_answer_list_vs(loinc_code: TermCode) -> str | None:
    """
    Get the answer list value set url from the Ontoserver based on the loinc code.
    :param loinc_code: loinc code
    :return: url of the answer list value set or None if no answer list is available
    """
    response = requests.get(
        f"{TERMINOLOGY_SERVER_ADDRESS}CodeSystem/$lookup?system=http://loinc.org&code={loinc_code.code}&property"
        f"=answer-list", cert=(SERVER_CERTIFICATE, PRIVATE_KEY))
    if answer_list_code := get_answer_list_code(response.json()):
        return "http://loinc.org/vs/" + answer_list_code
    return None


# TODO: Refactor should only need the 2nd function
def pattern_coding_to_termcode(element):
    """
    Converts a patternCoding to a term code
    :param element: element node from the snapshot with a patternCoding
    :return: term code
    """
    code = element["patternCoding"]["code"]
    system = element["patternCoding"]["system"]
    display = get_term_code_display_from_onto_server(system, code)
    if display.isupper():
        display = display.title()
    term_code = TermCode(system, code, display)
    return term_code


def pattern_codeable_concept_to_termcode(element):
    """
    Converts a patternCodeableConcept to a term code
    :param element: element node from the snapshot that is a patternCoding
    :return: term code
    """
    code = element["code"]
    system = element["system"]
    display = get_term_code_display_from_onto_server(system, code)
    if display.isupper():
        display = display.title()
    term_code = TermCode(system, code, display)
    return term_code


def get_value_sets_by_path(element_path: str, profile_data: dict) -> List[str] | []:
    """
    Get the value sets from the profile data based on the given path element.
    :param element_path: the value of path element of the profile
    :param profile_data: snapshot of the profile
    :return: list of value set urls or empty list if no value set is available
    """
    value_set = []
    for element in profile_data["snapshot"]["element"]:
        if "id" in element and element["path"] == element_path and "binding" in element:
            vs_url = element["binding"]["valueSet"]
            if vs_url in ['http://hl7.org/fhir/ValueSet/observation-codes']:
                continue
            value_set.append(vs_url)
    return value_set


def get_term_codes_by_id_from_term_server(element_id: str, profile_data: dict) -> List[TermCode] | []:
    """
    Get the term codes from the profile data based on the given id element.
    :param element_id: the value of the id element of the profile
    :param profile_data: snapshot of the profile
    :return: list of term codes or empty list if no term codes are available
    """
    value_set = ""
    for element in profile_data["snapshot"]["element"]:
        if "id" in element and element["id"] == element_id and "patternCoding" in element:
            if "code" in element["patternCoding"]:
                term_code = pattern_coding_to_termcode(element)
                return [term_code]
        if "id" in element and element["id"] == element_id and "binding" in element:
            value_set = element["binding"]["valueSet"]
    if value_set:
        return get_termcodes_from_onto_server(value_set)
    return []


def try_get_fixed_code(element_path: str, profile_data: dict) -> TermCode | None:
    """
    Get the fixed code from the profile data based on the given path element if available.
    :param element_path: the value of the path element of the profile
    :param profile_data: the snapshot of the profile
    :return: term code or None if no fixed code is available
    """
    system = ""
    code = ""
    for element in profile_data["snapshot"]["element"]:
        if "path" in element and element["path"] == element_path + ".system":
            if "fixedUri" in element:
                system = element["fixedUri"]
        if "path" in element and element["path"] == element_path + ".code":
            if "fixedCode" in element:
                code = element["fixedCode"]
        if system and code:
            display = get_term_code_display_from_onto_server(system, code)
            term_code = TermCode(system, code, display)
            return term_code
    return None


def get_term_codes_by_path(element_path: str, profile_data: dict) -> List[TermCode] | []:
    """
    Get the term codes from the profile data based on the given path element.
    :param element_path: the value of the path element of the profile
    :param profile_data: the snapshot of the profile
    :return:
    """
    # ToDo: handle multiple term_codes in patternCoding also consider allowing to resolve multiple valuesets here
    value_set = ""

    # This is another case of inconsistent profiling:
    if result := try_get_fixed_code(element_path, profile_data):
        return [result]
    for element in profile_data["snapshot"]["element"]:
        if "path" in element and element["path"] == element_path:
            if "patternCoding" in element:
                if "code" in element["patternCoding"]:
                    term_code = pattern_coding_to_termcode(element)
                    return [term_code]
            elif "patternCodeableConcept" in element:
                for coding in element["patternCodeableConcept"]["coding"]:
                    if "code" in coding:
                        term_code = pattern_codeable_concept_to_termcode(coding)
                        return [term_code]
        if "path" in element and element["path"] == element_path and "binding" in element:
            value_set = element["binding"]["valueSet"]
    if value_set:
        result = get_termcodes_from_onto_server(value_set)
        return result
    return []


# TODO duplicated code in valueSetToRoots
def get_term_code_display_from_onto_server(system: str, code: str,
                                           onto_server: str = TERMINOLOGY_SERVER_ADDRESS) -> str:
    """
    Get the display of a term code from the terminology server.
    :param system: code system of the term code
    :param code: code of the term code
    :param onto_server: address of the terminology server
    :return: The display of the term code or "" if no display is available
    """
    response = requests.get(f"{onto_server}CodeSystem/$lookup?system={system}&code={code}", cert=(SERVER_CERTIFICATE, PRIVATE_KEY))
    if response.status_code == 200:
        response_data = response.json()
        for parameter in response_data["parameter"]:
            if name := parameter.get("name"):
                if name == "display":
                    return parameter.get("valueString") if parameter.get("valueString") else ""
    return ""


def get_system_from_code(code: str, onto_server: str = TERMINOLOGY_SERVER_ADDRESS):
    """
    Get the system of a term code from the terminology server based on the code.
    :param code: code we want to get the system for
    :param onto_server: address of the terminology server
    :return: the the list of PossibleSystems that contain the code or an empty list if no system contains the code
    """
    result = []
    for system in POSSIBLE_CODE_SYSTEMS:
        if get_term_code_display_from_onto_server(system, code, onto_server):
            result.append(system)
    return result


def get_value_set_definition(canonical_address: str, onto_server: str = TERMINOLOGY_SERVER_ADDRESS) -> dict:
    """
    Get the value set definition from the terminology server based on the canonical address.
    :param canonical_address: canonical address of the value set
    :param onto_server: address of the terminology server
    :return: value set definition or an empty dict if no value set definition is available
    """
    version = MAPPING_ONTO_VERSION.get(canonical_address)  # Ensure we get the correct value for the address

    if version:
        canonical_address = f'{canonical_address}&system-version={version}'
    else:
        logging.debug(f"No version found for canonical address: {canonical_address}")

    try:
        response = requests.get(f"{onto_server}ValueSet/?url={canonical_address}", cert=(SERVER_CERTIFICATE, PRIVATE_KEY))
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logging.error(f"Request failed: {e}")
        return {}

    if response.status_code == 200:
        response_data = response.json()
        for entry in response_data.get("entry", []):
            resource = entry.get("resource")
            if resource and "id" in resource:
                return get_value_set_definition_by_id(resource["id"], onto_server)
    else:
        logging.warning(f"Failed to retrieve value set definition. Status code: {response.status_code}")

    logging.info(f"Canonical address processed: {canonical_address}")
    return {}

# TODO: Check if we can use that for any resource type
def get_value_set_definition_by_id(value_set_id: str, onto_server: str = TERMINOLOGY_SERVER_ADDRESS) -> dict:
    """
    Get the value set definition from the terminology server based on the id.
    :param value_set_id: the id of the value set
    :param onto_server: address of the terminology server
    :return: value set definition or None if no value set definition is available
    """
    response = requests.get(f"{onto_server}ValueSet/{value_set_id}", cert=(SERVER_CERTIFICATE, PRIVATE_KEY))
    if response.status_code == 200:
        return response.json()
    return {}
