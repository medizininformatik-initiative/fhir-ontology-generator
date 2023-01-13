from __future__ import annotations

import json
import os
from typing import List, Tuple

from TerminologService.ValueSetResolver import get_termcodes_from_onto_server, get_term_code_display_from_onto_server
from helper import flatten
from model.UIProfileModel import VALUE_TYPE_OPTIONS
from model.UiDataModel import TermCode

UCUM_SYSTEM = "http://unitsofmeasure.org"
FHIR_TYPES_TO_VALUE_TYPES = {
    "code": "concept",
    "Quantity": "quantity",
    "Reference": "reference",
    "CodeableConcept": "concept",
    "Coding": "concept"
}


class InvalidValueTypeException(Exception):
    pass


def get_element_from_snapshot(profile_snapshot, element_id) -> dict:
    """
    Returns the element from the given FHIR profile snapshot at the given element id
    :param profile_snapshot: FHIR profile snapshot
    :param element_id: element id
    :return: element
    """
    try:
        for element in profile_snapshot["snapshot"]["element"]:
            if "id" in element and element["id"] == element_id:
                return element
        else:
            raise KeyError(
                f"Could not find element with id: {element_id} in the snapshot: {profile_snapshot.get('name')}")
    except KeyError:
        print(
            f"KeyError the element id: {element_id} is not in the snapshot or the snapshot has no snapshot "
            f"elements")


def get_profiles_with_base_definition(fhir_dataset_dir: str, base_definition: str) -> Tuple[dict, str]:
    """
    Returns the profiles that have the given base definition
    :param fhir_dataset_dir: path to the FHIR dataset directory
    :param base_definition: base definition
    :return: generator of profiles that have the given base definition
    """
    for module_dir in [folder for folder in os.scandir(fhir_dataset_dir) if folder.is_dir()]:
        files = [file for file in os.scandir(f"{module_dir.path}/package") if file.is_file()
                 and file.name.endswith("snapshot.json")]
        for file in files:
            with open(file.path, "r", encoding="utf8") as f:
                profile = json.load(f)
                if profile.get("baseDefinition") == base_definition:
                    return profile, module_dir.path
                elif profile.get("type") == base_definition.split("/")[-1]:
                    return profile, module_dir.path


def get_extension_definition(module_dir: str, extension_profile_url: str) -> dict:
    """
    Returns the FHIR extension definition for the given extension profile url, the extension has to be located in
    {module_dir}/package/extension
    :param module_dir: path to the module directory
    :param extension_profile_url:  extension profile url
    :return: extension definition
    """
    files = [file for file in os.scandir(f"{module_dir}/package/extension") if file.is_file()
             and file.name.endswith("snapshot.json")]
    for file in files:
        with open(file.path, "r", encoding="utf8") as f:
            profile = json.load(f)
            if profile.get("url") == extension_profile_url:
                return profile


def parse(chained_fhir_element_id):
    """
    Parses a chained fhir element id with the given Grammar:
    chained_fhir_element_id ::= "(" chained_fhir_element_id ")" ( "." fhir_element_id )* | fhir_element_id
    :param chained_fhir_element_id: the chained fhir element id
    :return: the parsed fhir element id
    """
    tokens = tokenize(chained_fhir_element_id)
    return parse_tokens(tokens)


def parse_tokens(tokens: List[str]) -> List[str] | str:
    """
    returns the parsed syntax node of the tokens
    :param tokens: the syntax tokens
    :return: the parsed syntax node represented as a list of child nodes or a string
    """
    if len(tokens) == 0:
        raise ValueError("Empty string")
    token = tokens.pop(0)
    if token == "(":
        sub_tree = []
        while tokens[0] != ")":
            sub_tree.append(parse_tokens(tokens))
        tokens.pop(0)
        if len(tokens) == 1:
            return [sub_tree, tokens.pop(0)]
        else:
            return sub_tree
    elif token == ")":
        raise ValueError("Unexpected )")
    else:
        return token


def tokenize(chained_fhir_element_id):
    """
    Tokenizes a chained fhir element id with the given Grammar:
    chained_fhir_element_id ::= "(" chained_fhir_element_id ")" ( "." fhir_element_id )* | fhir_element_id
    :param chained_fhir_element_id: the chained fhir element id
    :return: the tokenized fhir element id
    """
    return chained_fhir_element_id.replace("(", " ( ").replace(")", " ) ").split()


def get_element_defining_elements(chained_element_id, profile_snapshot: dict, start_module_dir: str, data_set_dir: str) \
        -> List[dict]:
    parsed_list = list(flatten(parse(chained_element_id)))
    print(parsed_list)
    return process_element_id(parsed_list, profile_snapshot, start_module_dir, data_set_dir)


def process_element_id(element_ids, profile_snapshot: dict, module_dir: str, data_set_dir: str) -> List[dict] | None:
    element_id = element_ids.pop(0)
    if element_id.startswith("."):
        raise ValueError("Element id must start with a resource type")
    element = get_element_from_snapshot(profile_snapshot, element_id)
    result = [element]
    if element_ids:
        for element in element.get("type"):
            if element.get("code") == "Extension":
                profile_urls = element.get("profile")
                if len(profile_urls) > 1:
                    raise Exception("Extension with multiple types not supported")
                extension = get_extension_definition(module_dir, profile_urls[0])
                element_ids[0] = f"Extension{element_ids[0]}"
                result.extend(process_element_id(element_ids, extension, module_dir, data_set_dir))
                return result
            elif element.get("code") == "Reference":
                target_profiles = element.get("targetProfile")
                if len(target_profiles) > 1:
                    raise Exception("Reference with multiple types not supported")
                target_resource_type = element.get("targetProfile")[0]
                referenced_profile, module_dir = get_profiles_with_base_definition(data_set_dir, target_resource_type)
                element_ids[0] = f"{referenced_profile.get('type')}{element_ids[0]}"
                result.extend(process_element_id(element_ids, referenced_profile, module_dir, data_set_dir))
                return result
            else:
                raise Exception(f"You can only chain extensions and references, but found: {element.get('code')}")
    return result


def resolve_defining_id(profile_snapshot: dict, defining_id: str, data_set_dir: str, module_dir: str) \
        -> dict | str:
    """
    :param profile_snapshot: FHIR profile snapshot
    :param defining_id: defining id
    :param module_dir: path to the module directory
    :param data_set_dir: path to the FHIR dataset directory
    :return: resolved defining id
    """
    return get_element_defining_elements(defining_id, profile_snapshot, module_dir, data_set_dir)[-1]


def extract_value_type(value_defining_element: dict, profile_name: str = "") -> VALUE_TYPE_OPTIONS:
    """
    Extracts the value type for the given FHIR profile snapshot at the value defining element id
    :param value_defining_element: element that defines the value
    :param profile_name: name of the FHIR profile for debugging purposes can be omitted
    :return: value type
    """
    if not value_defining_element:
        print(f"Could not find value defining element for {profile_name}")
    fhir_value_types = value_defining_element.get("type")
    if not fhir_value_types:
        raise InvalidValueTypeException(f"No value type defined in element: {str(value_defining_element)}"
                                        f" in profile: {profile_name}")
    if len(fhir_value_types) > 1:
        raise InvalidValueTypeException(f"More than one value type defined in element: "
                                        f"{str(value_defining_element)} refine the profile: " + profile_name)
    return FHIR_TYPES_TO_VALUE_TYPES.get(fhir_value_types[0].get("code")) \
        if fhir_value_types[0].get("code") in FHIR_TYPES_TO_VALUE_TYPES else fhir_value_types[0].get("code")


def get_selectable_concepts(concept_defining_element, profile_name: str = "") -> List[TermCode]:
    """
    Returns the answer options for the given concept defining element
    :param concept_defining_element:
    :param profile_name: name of the FHIR profile for debugging purposes can be omitted
    :return: answer options as term codes
    :raises InvalidValueTypeException: if no valueSet is defined for the concept defining element
    """
    if binding := concept_defining_element.get("binding"):
        if value_set_url := binding.get("valueSet"):
            return get_termcodes_from_onto_server(value_set_url)
        else:
            raise InvalidValueTypeException(f"No value set defined in element: {str(binding)}"
                                            f" in profile: {profile_name}")
    else:
        raise InvalidValueTypeException(f"No binding defined in element: {str(concept_defining_element)}"
                                        f" in profile: {profile_name}")


def get_units(unit_defining_element, profile_name: str = "") -> List[TermCode]:
    if unit_code := unit_defining_element.get("fixedCode"):
        return [TermCode(UCUM_SYSTEM, unit_code, unit_code)]
    else:
        raise InvalidValueTypeException(f"No unit defined in element: {str(unit_defining_element)}"
                                        f" in profile: {profile_name}")


def get_value_set_defining_url(value_set_defining_element: dict, profile_name: str = "") -> str:
    """
    Returns the value set defining url for the given value set defining element
    :param value_set_defining_element: element that defines the value set
    :param profile_name: name of the FHIR profile for debugging purposes can be omitted
    :return: canonical url of the value set
    """
    if binding := value_set_defining_element.get("binding"):
        if value_set_url := binding.get("valueSet"):
            return value_set_url
        else:
            raise InvalidValueTypeException(f"No value set defined in element: {str(binding)}"
                                            f" in profile: {profile_name}")
    else:
        raise InvalidValueTypeException(f"No binding defined in element: {str(value_set_defining_element)}"
                                        f" in profile: {profile_name}")


def pattern_coding_to_term_code(element):
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

#
# if __name__ == "__main__":
#     with open("example/mii_core_data_set/resources/core_data_sets/de.medizininformatikinitiative.kerndatensatz"
#               ".biobank#1.0.3/package/StructureDefinition-Specimen-snapshot.json", "r") as f:
#         profile = json.load(f)
#         print(resolve_defining_id(profile,
#                                   "((Specimen.extension:festgestellteDiagnose as Reference).value[x] "
#                                   "as Reference).code.coding:icd10-gm as ValueSetUrl",
#                                   "example/mii_core_data_set/resources/core_data_sets",
#                                   "example/mii_core_data_set/resources/fdpg_differential/"
#                                   "Bioprobe"))
