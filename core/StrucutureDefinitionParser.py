from __future__ import annotations

import json
import os
import re
from collections import namedtuple
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

    if not profile_snapshot.get("snapshot"):
        raise KeyError(f"KeyError the snapshot has no snapshot elements. The snapshot: {profile_snapshot.get('name')}")
    try:
        for element in profile_snapshot["snapshot"]["element"]:
            if "id" in element and element["id"] == element_id:
                return element
        else:
            raise KeyError(
                f"Could not find element with id: {element_id} in the snapshot: {profile_snapshot.get('name')}")
    except KeyError:
        raise KeyError(
            f"KeyError the element id: {element_id} is not in the snapshot or the snapshot has no snapshot "
            f"elements. The snapshot: {profile_snapshot.get('name')}")
    except TypeError:
        raise TypeError(f"TypeError the snapshot is not a dict {profile_snapshot}")


def is_element_in_snapshot(profile_snapshot, element_id) -> bool:
    """
    Returns true if the given element id is in the given FHIR profile snapshot
    :param profile_snapshot: FHIR profile snapshot
    :param element_id: element id
    :return: true if the given element id is in the given FHIR profile snapshot
    """
    try:
        for element in profile_snapshot["snapshot"]["element"]:
            if "id" in element and element["id"] == element_id:
                return True
        else:
            return False
    except KeyError:
        return False


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
                elif profile.get("url") == base_definition:
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
        print(file.path)
        with open(file.path, "r", encoding="utf8") as f:
            profile = json.load(f)
            if profile.get("url") == extension_profile_url:
                return profile
    else:
        raise FileNotFoundError(
            f"Could not find extension definition for extension profile url: {extension_profile_url}")


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


def get_element_defining_elements(chained_element_id, profile_snapshot: dict, start_module_dir: str,
                                  data_set_dir: str) -> List[dict] | None:
    return [element_with_source_snapshot.element for element_with_source_snapshot in
            get_element_defining_elements_with_source_snapshots(chained_element_id, profile_snapshot, start_module_dir,
                                                                data_set_dir)]


ProcessedElementResult = namedtuple("ProcessedElementResult", ["element", "profile_snapshot", "module_dir"])


def get_element_defining_elements_with_source_snapshots(chained_element_id, profile_snapshot: dict,
                                                        start_module_dir: str,
                                                        data_set_dir: str) -> List[ProcessedElementResult]:
    parsed_list = list(flatten(parse(chained_element_id)))
    return process_element_id(parsed_list, profile_snapshot, start_module_dir, data_set_dir)


def process_element_id(element_ids, profile_snapshot: dict, module_dir: str, data_set_dir: str) \
        -> List[ProcessedElementResult] | None:
    element_id = element_ids.pop(0)
    if element_id.startswith("."):
        raise ValueError("Element id must start with a resource type")
    element = get_element_from_snapshot(profile_snapshot, element_id)
    result = [ProcessedElementResult(element=element, profile_snapshot=profile_snapshot, module_dir=module_dir)]
    for element in element.get("type"):
        if element.get("code") == "Extension":
            profile_urls = element.get("profile")
            if len(profile_urls) > 1:
                raise Exception("Extension with multiple types not supported")
            print(profile_urls)
            extension = get_extension_definition(module_dir, profile_urls[0])
            element_ids[0] = f"Extension" + element_ids[0]
            result.extend(process_element_id(element_ids, extension, module_dir, data_set_dir))
            return result
        elif element.get("code") == "Reference":
            target_profiles = element.get("targetProfile")
            # if len(target_profiles) > 1:
            #     raise Exception("Reference with multiple types not supported")
            target_resource_type = element.get("targetProfile")[0]
            print(target_resource_type, data_set_dir)
            referenced_profile, module_dir = get_profiles_with_base_definition(data_set_dir, target_resource_type)
            element_ids[0] = f"{referenced_profile.get('type') + element_ids[0]}"
            result.extend(process_element_id(element_ids, referenced_profile, module_dir, data_set_dir))
            return result
        elif element.get("code") == "Coding":
            return result
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
    return fhir_value_types[0].get("code")


def extract_reference_type(value_defining_element: dict, data_set_dir: str, profile_name: str = "") -> str:
    """
    Extracts the reference type from the given value defining element
    :param value_defining_element: element that defines the value
    :param data_set_dir: path to the FHIR dataset directory
    :param profile_name: name of the FHIR profile for debugging purposes can be omitted
    :return: reference type
    """
    if not value_defining_element:
        print(f"Could not find value defining element for {profile_name}")
    # if len(target_profiles) > 1:
    #     raise Exception("Reference with multiple types not supported")
    if not value_defining_element.get("targetProfile"):
        print(f"Could not find target profile for {profile_name}")
    target_resource_type = value_defining_element.get("targetProfile")[0]
    print(target_resource_type, data_set_dir)
    referenced_profile, module_dir = get_profiles_with_base_definition(data_set_dir, target_resource_type)
    return referenced_profile.get("type")


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
    elif unit_code := unit_defining_element.get("patternCode"):
        return [TermCode(UCUM_SYSTEM, unit_code, unit_code)]
    elif binding := unit_defining_element.get("binding"):
        if value_set_url := binding.get("valueSet"):
            return get_termcodes_from_onto_server(value_set_url)
        else:
            raise InvalidValueTypeException(f"No value set defined in element: {str(binding)}"
                                            f" in profile: {profile_name}")
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


def pattern_codeable_concept_to_term_code(element):
    """
    Converts a patternCodeableConcept to a term code
    :param element: element node from the snapshot with a patternCoding
    :return: term code
    """
    code = element["patternCodeableConcept"]["coding"][0]["code"]
    system = element["patternCodeableConcept"]["coding"][0]["system"]
    display = get_term_code_display_from_onto_server(system, code)
    if display.isupper():
        display = display.title()
    term_code = TermCode(system, code, display)
    return term_code


def fixed_codeable_concept_to_term_code(element):
    """
    Converts a fixedCodeableConcept to a term code
    :param element: element node from the snapshot with a patternCoding
    :return: term code
    """
    code = element["fixedCodeableConcept"]["coding"][0]["code"]
    system = element["fixedCodeableConcept"]["coding"][0]["system"]
    display = get_term_code_display_from_onto_server(system, code)
    if display.isupper():
        display = display.title()
    term_code = TermCode(system, code, display)
    return term_code


def translate_element_to_fhir_path_expression(elements: List[dict], profile_snapshot) -> List[str]:
    """
    Translates an element to a fhir search parameter. Be aware not every element is translated alone to a
    fhir path expression. I.E. Extensions elements are translated together with the prior element.
    :param elements: elements for which the fhir path expressions should be obtained
    :param profile_snapshot: snapshot of the profile
    :return: fhir path expressions
    """
    element = elements.pop(0)
    element_path = element.get("path")
    element_type = get_element_type(element)
    if element_type == "Extension":
        if elements[0].get("id") == "Extension.value[x]":
            element_type = get_element_type(elements[0])
            element_path = f"{element_path}.where(url='{get_extension_url(element)}').value[x]"
            element_path = replace_x_with_cast_expression(element_path, element_type)
        # FIXME: Currently hard coded should be generalized
        elif elements[0].get("id") == "Extension.extension:age.value[x]":
            element_path = f"{element_path}.where(url='{get_extension_url(element)}').extension.where(url='age').value[x]"
            element_path = replace_x_with_cast_expression(element_path, element_type)
    if '[x]' in element_path and "Extension" not in element_path:
        element_type = get_parent_element_type(element.get("id"), profile_snapshot)
        element_path = replace_x_with_cast_expression(element_path, element_type)
    result = [element_path]
    if elements:
        result.extend(translate_element_to_fhir_path_expression(elements, profile_snapshot))
    return result


def replace_x_with_cast_expression(element_path, element_type):
    # Regular expression to capture [x] and [x]:arbitrary_slicing
    match = re.search(r'(\[x\](?::[\w]+)?)', element_path)
    if match:
        pre_match = element_path[:match.start()]
        post_match = element_path[match.end():]
        # If there's a following attribute expression, add parentheses
        if '.' in post_match:
            replacement = f'({pre_match} as {element_type}){post_match}'
        else:
            replacement = f'{pre_match} as {element_type}'
        return replacement
    return element_path


def get_parent_element_type(element_id, profile_snapshot):
    """
    If the path indicates an arbitrary type [x] the parent element can give insight on its type. This function
    returns the type of the parent element. By searching the element at [x] or at its slicing.
    """
    if '[x]:' not in element_id:
        # remove everything after the [x]
        element_id = re.sub(r'(\[x\]).*', r'\1', element_id)
    else:
        # remove everything after the [x] and the slicing -> everything until the next . after [x]:
        element_id = re.sub(r'(\[x\]).*?(?=\.)', r'\1', element_id)
    try:
        parent_element = get_element_from_snapshot(profile_snapshot, element_id)
    except Exception as e:
        element_id = re.sub(r'(\[x\]).*', r'\1', element_id)
        parent_element = get_element_from_snapshot(profile_snapshot, element_id)
    return get_element_type(parent_element)


def get_extension_url(element):
    print(element.get("type"))
    extension_profiles = element.get('type')[0].get('profile')
    if len(extension_profiles) > 1:
        raise Exception("More than one extension found")
    if not extension_profiles:
        raise Exception("No extension profile url found in element: \n" + element)
    return extension_profiles[0]


def get_element_type(element):
    """
    Returns the type of the given element
    :param element: element
    :return: type of the element
    """
    element_types = element.get("type")
    if len(element_types) > 1:
        types = [element_type.get("code") for element_type in element_types]
        if "dateTime" in types and "Period" in types:
            return "dateTime"
        # FIXME: Currently hard coded should be generalized
        if "Reference" in types and "CodeableConcept" in types:
            return "CodeableConcept"
        else:
            raise Exception("Multiple types are currently not supported")
    elif not element_types:
        raise Exception("No type found for element " + element.get("id") + " in profile element \n" + element)
    return element_types[0].get("code")


def get_element_from_snapshot_by_path(profile_snapshot, element_path) -> List[dict]:
    """
    Returns the element from the given FHIR profile snapshot at the given element path
    :param profile_snapshot: FHIR profile snapshot
    :param element_path: element id
    :return: elements
    """
    result = []
    try:
        for element in profile_snapshot["snapshot"]["element"]:
            if "path" in element and element["path"] == element_path:
                result.append(element)
        if not result:
            raise KeyError(
                f"Could not find element with id: {element_path} in the snapshot: {profile_snapshot.get('name')}")
    except KeyError:
        raise KeyError(
            f"KeyError the element id: {element_path} is not in the snapshot or the snapshot has no snapshot "
            f"elements")
    return result


def get_term_code_by_id(fhir_profile_snapshot, term_code_defining_id, data_set_dir, module_dir) -> List[TermCode]:
    """
    Returns the term entries for the given term code defining id
    :param fhir_profile_snapshot: snapshot of the FHIR profile
    :param term_code_defining_id: id of the element that defines the term code
    :param data_set_dir: data set directory of the FHIR profile
    :param module_dir: module directory of the FHIR profile
    :return: term entries
    """
    if not term_code_defining_id:
        raise Exception(f"No term code defining id given print for {fhir_profile_snapshot.get('name')}")
    term_code_defining_element = resolve_defining_id(fhir_profile_snapshot, term_code_defining_id,
                                                     data_set_dir, module_dir)
    if not term_code_defining_element:
        raise Exception(f"Could not resolve term code defining id {term_code_defining_id} "
                        f"in {fhir_profile_snapshot.get('name')}")
    if "patternCoding" in term_code_defining_element:
        if "code" in term_code_defining_element["patternCoding"]:
            term_code = pattern_coding_to_term_code(term_code_defining_element)
            return [term_code]
    if "patternCodeableConcept" in term_code_defining_element:
        if "coding" in term_code_defining_element["patternCodeableConcept"]:
            term_code = pattern_codeable_concept_to_term_code(term_code_defining_element)
            return [term_code]
    if "binding" in term_code_defining_element:
        value_set = term_code_defining_element.get("binding").get("valueSet")
        return get_termcodes_from_onto_server(value_set)
    else:
        tc = try_get_term_code_from_sub_elements(fhir_profile_snapshot, term_code_defining_id, data_set_dir, module_dir)
        if tc:
            return [tc]
        raise Exception(f"Could not resolve term code defining element: {term_code_defining_element}")


def try_get_term_code_from_sub_elements(fhir_profile_snapshot, parent_coding_id, data_set_dir,
                                        module_dir) -> TermCode | None:
    if not is_element_in_snapshot(fhir_profile_snapshot, parent_coding_id + ".code"):
        return None
    code_element = resolve_defining_id(fhir_profile_snapshot, parent_coding_id + ".code", data_set_dir, module_dir)
    system_element = resolve_defining_id(fhir_profile_snapshot, parent_coding_id + ".system", data_set_dir,
                                         module_dir)
    if code_element and system_element:
        if "patternCode" in code_element and "patternUri" in system_element:
            return TermCode(system_element["patternUri"], code_element["patternCode"],
                            get_term_code_display_from_onto_server(system_element["patternUri"],
                                                                   code_element["patternCode"]))
        elif "fixedCode" in code_element and "fixedUri" in system_element:
            return TermCode(system_element["fixedUri"], code_element["fixedCode"],
                            get_term_code_display_from_onto_server(system_element["fixedUri"],
                                                                   code_element["fixedCode"]))

    return None


def get_binding_value_set_url(element: dict) -> str | None:
    """
    Returns the value set url of the given element
    :param element: element with binding
    :return: value set url
    """
    if "binding" in element:
        return element["binding"].get("valueSet")


def get_fixed_term_codes(element: dict, snapshot: dict, module_dir, data_set_dir) -> List[TermCode] | None:
    """
    Returns the fixed term codes of the given element
    """
    if "fixedCodeableConcept" in element:
        return [fixed_codeable_concept_to_term_code(element)]
    elif "patternCodeableConcept" in element:
        return [pattern_codeable_concept_to_term_code(element)]
    else:
        if tc := try_get_term_code_from_sub_elements(snapshot, element.get("id"), module_dir, data_set_dir):
            return [tc]
    return None
