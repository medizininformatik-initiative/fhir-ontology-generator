import os

import requests

from TerminologService.valueSetToRoots import create_vs_tree
from model.UiDataModel import TermCode, TerminologyEntry

ONTOLOGY_SERVER_ADDRESS = os.environ.get('ONTOLOGY_SERVER_ADDRESS')
POSSIBLE_CODE_SYSTEMS = ["http://loinc.org", "http://snomed.info/sct"]


def get_termentries_from_onto_server(canonical_address_value_set):
    if canonical_address_value_set in ["https://www.medizininformatik-initiative.de/fhir/core/modul-diagnose/ValueSet"
                                       "/diagnoses-sct",
                                       "https://www.medizininformatik-initiative.de/fhir/core/modul-prozedur/ValueSet/"
                                       "procedures-sct"]:
        return []
    canonical_address_value_set = canonical_address_value_set.replace("|", "&version=")
    print(canonical_address_value_set)
    # In Gecco 1.04 all icd10 elements with children got removed this brings them back. Requires matching valuesets on
    # Ontoserver
    if canonical_address_value_set.endswith("icd"):
        canonical_address_value_set = canonical_address_value_set + "-with-parent"
    result = create_vs_tree(canonical_address_value_set)
    if len(result) < 1:
        print("ERROR", canonical_address_value_set)
    return result

    # TODO: We only want to use a single coding system. The different coding systems need to be prioritized


def get_termcodes_from_onto_server(canonical_address_value_set, onto_server=ONTOLOGY_SERVER_ADDRESS):
    canonical_address_value_set = canonical_address_value_set.replace("|", "&version=")
    print(canonical_address_value_set)
    icd10_result = []
    snomed_result = []
    result = []
    response = requests.get(
        f"{onto_server}ValueSet/$expand?url={canonical_address_value_set}&includeDesignations=true")
    if response.status_code == 200:
        value_set_data = response.json()
        if "contains" in value_set_data["expansion"]:
            for contains in value_set_data["expansion"]["contains"]:
                system = contains["system"]
                code = contains["code"]
                display = contains["display"]
                term_code = TermCode(system, code, display)
                if system == "http://fhir.de/CodeSystem/dimdi/icd-10-gm":
                    icd10_result.append(term_code)
                elif system == "http://snomed.info/sct":
                    if "designation" in contains:
                        for designation in contains["designation"]:
                            if "language" in designation and designation["language"] == "de-DE":
                                term_code.display = designation["value"]
                    snomed_result.append(term_code)
                else:
                    result.append(term_code)
        else:
            return []
    else:
        print(f"{canonical_address_value_set} is empty")
        return []
    # TODO: Workaround
    if result and result[0].display == "Hispanic or Latino":
        return sorted(result + snomed_result)
    if icd10_result:
        return icd10_result
    elif result:
        return sorted(result)
    else:
        return sorted(snomed_result)


def get_answer_list_code(response):
    if parameters := response.get("parameter"):
        for parameter in parameters:
            if parts := parameter.get("part"):
                next_is_answer_list = False
                for part in parts:
                    if next_is_answer_list and (valueCode := part.get("valueCode")):
                        return valueCode
                    if (valueCode := part.get("valueCode")) and (valueCode == "answer-list"):
                        next_is_answer_list = True


def get_answer_list_vs(loinc_code):
    response = requests.get(
        f"{ONTOLOGY_SERVER_ADDRESS}CodeSystem/$lookup?system=http://loinc.org&code={loinc_code.code}&property=answer-list")
    if answer_list_code := get_answer_list_code(response.json()):
        return "http://loinc.org/vs/" + answer_list_code


# TODO: Refactor should only need the 2nd function
def pattern_coding_to_termcode(element):
    code = element["patternCoding"]["code"]
    system = element["patternCoding"]["system"]
    display = get_term_code_display_from_onto_server(system, code)
    if display.isupper():
        display = display.title()
    term_code = TermCode(system, code, display)
    return term_code


def pattern_codeable_concept_to_termcode(element):
    code = element["code"]
    system = element["system"]
    display = get_term_code_display_from_onto_server(system, code)
    if display.isupper():
        display = display.title()
    term_code = TermCode(system, code, display)
    return term_code


# Ideally we would want to use [path] not the id, but using the id gives us control on which valueSet we want to use.
def get_term_entries_by_id(element_id, profile_data):
    for element in profile_data["snapshot"]["element"]:
        if "id" in element and element["id"] == element_id and "patternCoding" in element:
            if "code" in element["patternCoding"]:
                term_code = pattern_coding_to_termcode(element)
                return [TerminologyEntry([term_code], "CodeableConcept", leaf=True, selectable=True)]
        if "id" in element and element["id"] == element_id and "binding" in element:
            value_set = element["binding"]["valueSet"]
            return get_termentries_from_onto_server(value_set)
    return []


def get_term_entries_by_path(element_path, profile_data):
    for element in profile_data["snapshot"]["element"]:
        if "path" in element and element["path"] == element_path and "patternCoding" in element:
            if "code" in element["patternCoding"]:
                term_code = pattern_coding_to_termcode(element)
                return [TerminologyEntry([term_code], "CodeableConcept", leaf=True, selectable=True)]
        if "path" in element and element["path"] == element_path and "binding" in element:
            value_set = element["binding"]["valueSet"]
            return get_termentries_from_onto_server(value_set)
    return []


def get_value_sets_by_path(element_path, profile_data):
    value_set = []
    for element in profile_data["snapshot"]["element"]:
        if "id" in element and element["path"] == element_path and "binding" in element:
            vs_url = element["binding"]["valueSet"]
            if vs_url in ['http://hl7.org/fhir/ValueSet/observation-codes']:
                continue
            value_set.append(vs_url)
    return value_set


def get_term_codes_by_id(element_id, profile_data):
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


def get_value_set_by_id(element_id, profile_data):
    value_set = []
    for element in profile_data["snapshot"]["element"]:
        if "id" in element and element["id"] == element_id and "binding" in element:
            value_set.append(element["binding"]["valueSet"])
    return value_set


def get_term_code_by_id(element_id, profile_data):
    term_code = None
    for element in profile_data["snapshot"]["element"]:
        if "id" in element and element["id"] == element_id and "patternCoding" in element:
            if "code" in element["patternCoding"]:
                term_code = pattern_coding_to_termcode(element)
                return [term_code]


def try_get_fixed_code(element_path, profile_data):
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


def get_term_codes_by_path(element_path, profile_data):
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
def get_term_code_display_from_onto_server(system, code, onto_server=ONTOLOGY_SERVER_ADDRESS):
    response = requests.get(f"{onto_server}CodeSystem/$lookup?system={system}&code={code}")
    if response.status_code == 200:
        response_data = response.json()
        for parameter in response_data["parameter"]:
            if name := parameter.get("name"):
                if name == "display":
                    return parameter.get("valueString") if parameter.get("valueString") else ""
    return ""


def get_system_from_code(code, onto_server=ONTOLOGY_SERVER_ADDRESS):
    result = []
    for system in POSSIBLE_CODE_SYSTEMS:
        if get_term_code_display_from_onto_server(system, code, onto_server):
            result.append(system)
    return result


def get_value_set_definition(canonical_address, onto_server=ONTOLOGY_SERVER_ADDRESS):
    response = requests.get(f"{onto_server}ValueSet/?url={canonical_address}")
    if response.status_code == 200:
        response_data = response.json()
        for entry in response_data.get("entry", []):
            if resource := entry.get("resource"):
                if "id" in resource:
                    return get_value_set_definition_by_id(resource["id"], onto_server)
    print(canonical_address)
    return None


# TODO: Check if we can use that for any resource type
def get_value_set_definition_by_id(value_set_id, onto_server=ONTOLOGY_SERVER_ADDRESS):
    response = requests.get(f"{onto_server}ValueSet/{value_set_id}")
    if response.status_code == 200:
        return response.json()
    return None
