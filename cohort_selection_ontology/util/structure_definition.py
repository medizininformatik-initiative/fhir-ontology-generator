from __future__ import annotations

import json
import os
import re
from collections import namedtuple
from pathlib import Path
from typing import List, Tuple, Optional

from cohort_selection_ontology.core.terminology.client import CohortSelectionTerminologyClient as TerminologyClient
from common.util.fhir.structure_definition import get_element_from_snapshot, is_element_in_snapshot
from helper import flatten, get_display_from_element_definition
from cohort_selection_ontology.model.ui_profile import VALUE_TYPE_OPTIONS, ValueSet
from cohort_selection_ontology.model.ui_data import TermCode

from importlib import resources
from cohort_selection_ontology.resources import cql, fhir
from common.util.log.functions import get_logger

UCUM_SYSTEM = "http://unitsofmeasure.org"
FHIR_TYPES_TO_VALUE_TYPES = json.load(fp=(resources.files(fhir) / 'fhir-types-to-value-types.json')
                                      .open('r', encoding='utf-8'))
CQL_TYPES_TO_VALUE_TYPES = json.load(fp=(resources.files(cql) / 'cql-types-to-value-types.json')
                                      .open('r', encoding='utf-8'))


logger = get_logger(__file__)


class InvalidValueTypeException(Exception):
    pass


def get_profiles_with_base_definition(modules_dir_path: str | Path, base_definition: str) -> Tuple[dict, str]:
    """
    Returns the profiles that have the given base definition
    :param modules_dir_path: path to the modules directory
    :param base_definition: base definition
    :return: generator of profiles that have the given base definition
    """
    for module_dir in [folder for folder in os.scandir(modules_dir_path) if folder.is_dir()]:
        logger.debug(f"Searching in {module_dir.path}")
        files = list(Path(module_dir.path, "differential", "package").rglob("*snapshot.json"))
        logger.debug(f"Found {len(files)} snapshot file(s) in module @ '{module_dir.path}'")
        for file in files:
            with open(file, mode="r", encoding="utf8") as f:
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
    files = [file for file in os.scandir(os.path.join(module_dir, "differential", "package", "extension")) if file.is_file()
             and file.name.endswith("snapshot.json")]
    for file in files:
        with open(file.path, "r", encoding="utf8") as f:
            profile = json.load(f)
            if profile.get("url") == extension_profile_url:
                return profile
    else:
        raise FileNotFoundError(
            f"Could not find extension definition for extension profile url: {extension_profile_url}")


def parse(chained_fhir_element_id) -> List[str] | str:
    """
    Parses a chained fhir element id with the given Grammar:
    chained_fhir_element_id ::= "(" chained_fhir_element_id ")" ( "." fhir_element_id )* | fhir_element_id
    :param chained_fhir_element_id: the chained fhir element id
    :return: the parsed fhir element id
    """
    if '.where' in chained_fhir_element_id:
        main_part, condition_and_rest = chained_fhir_element_id.split('.where', 1)
        condition_part, rest_part = condition_and_rest.split(')', 1)
        condition_part = condition_part.strip('(')
        rest_part = rest_part.strip(':')
        return [parse(f"{main_part.strip()}:{rest_part.strip()}"), parse(condition_part.strip())]
    tokens = tokenize(chained_fhir_element_id)
    result = parse_tokens(tokens)
    return result


def parse_tokens(tokens: List[str]) -> List[str] | str:
    """
    returns the parsed syntax node of the tokens
    :param tokens: the syntax tokens
    :return: the parsed syntax node represented as a list of child nodes or a string
    """
    if not tokens:
        raise ValueError("Empty string")

    token = tokens.pop(0)

    if token == ".where":
        return parse_tokens(tokens)
    elif token == "(":
        sub_tree = []
        while tokens and tokens[0] != ")":
            sub_tree.append(parse_tokens(tokens))
        if not tokens:
            raise ValueError("Missing closing parenthesis")
        tokens.pop(0)  # Remove the closing parenthesis
        if tokens and tokens[0] != ")":
            sub_tree.append(parse_tokens(tokens))
        return sub_tree
    elif token == ")":
        raise ValueError("Unexpected )")
    else:
        if tokens and tokens[0] != ")":
            return [token, parse_tokens(tokens)]
        else:
            return token


def tokenize(chained_fhir_element_id):
    """
    Tokenizes a chained fhir element id with the given Grammar:
    chained_fhir_element_id ::= "(" chained_fhir_element_id ")" ( "." fhir_element_id )* | fhir_element_id
    :param chained_fhir_element_id: the chained fhir element id
    :return: the tokenized fhir element id
    """
    return chained_fhir_element_id.replace("(", " ( ").replace(")", " ) ").replace('.where', ' .where ').split()


def get_element_defining_elements(chained_element_id, profile_snapshot: dict, start_module_dir: str,
                                  data_set_dir: str | Path) -> List[dict] | None:
    return [element_with_source_snapshot.element for element_with_source_snapshot in
            get_element_defining_elements_with_source_snapshots(chained_element_id, profile_snapshot, start_module_dir,
                                                                data_set_dir)]


ProcessedElementResult = namedtuple("ProcessedElementResult", ["element", "profile_snapshot", "module_dir", "last_short_desc"])

ShortDesc = namedtuple("ShortDesc", ["origin", "desc"])


def get_element_defining_elements_with_source_snapshots(chained_element_id, profile_snapshot: dict,
                                                        start_module_dir: str | Path,
                                                        data_set_dir: str | Path) -> List[ProcessedElementResult]:
    parsed_list = list(flatten(parse(chained_element_id)))
    return process_element_id(parsed_list, profile_snapshot, start_module_dir, data_set_dir)


def get_parent_slice_id(element_id: str) -> str:
    """
    Extracts the ID of the slice on the highest level
    :param element_id: the element id
    :return: the ID of the slice on the highest level

    Example:
        get_parent_slice_id("Observation.component:Diastolic.code.coding:sct") \n
        => 'Observation.component:Diastolic'
    """
    parent_slice_name = element_id.split(":")[-1].split(".")[0]
    parent_slice_id = element_id.rsplit(":", 1)[0] + ":" + parent_slice_name
    return parent_slice_id


def get_parent_slice_element(profile_snapshot: dict, element_id: str) -> dict:
    """
    Returns the parent slice element for the provided ID
    :param profile_snapshot: snapshot of the profile the element is in
    :param element_id: the element id
    :return: the parent slice element for the provided ID
    """
    parent_slice_id = get_parent_slice_id(element_id)
    return get_element_from_snapshot(profile_snapshot, parent_slice_id)


def is_element_slice_base(element_id: str) -> bool:
    """
    Is the specified element id a slice base

    Example:
        is_element_slice_base("Observation.component:Diastolic")  => TRUE \n
        is_element_slice_base("Observation.component:Diastolic.code")  => FALSE \n

    :param element_id:
    :return: bool
    """
    return get_parent_slice_id(element_id) == element_id


def get_common_ancestor_id(element_id_1: str, element_id_2: str) -> str:
    """
    Extracts the nearest common ancestor from two element IDs
    :param element_id_1: the first element ID
    :param element_id_2: the second element ID
    :return: the common ancestor ID

    Example
        id1 = "Observation.component:Systolic.short" \n
        id2 = "Observation.component:Diastolic.code.short" \n
        get_common_ancestor_id(id1, id2) => "Observation.component" \n
    """
    last_common_ancestor = []
    parts_1 = re.split(r"([.:])", element_id_1)
    parts_2 = re.split(r"([.:])", element_id_2)

    for sec_el_1, sec_el_2 in zip(parts_1, parts_2):
        if sec_el_1 != sec_el_2:
            if last_common_ancestor[-1] == "." or last_common_ancestor[-1] == ":":
                last_common_ancestor.pop()
            break
        last_common_ancestor.append(sec_el_1)
    return "".join(last_common_ancestor)


def get_common_ancestor(profile_snapshot: dict, element_id_1: str, element_id_2: str) -> dict:
    """
    Return the element of the common ancestor of the provided ids
    :param profile_snapshot: snapshot of the profile the element is in
    :param element_id_1: first element ID
    :param element_id_2: second element ID
    :return: the element of the common ancestor of the provided ids
    """
    return get_element_from_snapshot(profile_snapshot, get_common_ancestor_id(element_id_1, element_id_2))


def process_element_id(element_ids, profile_snapshot: dict, module_dir_name: str, modules_dir_path: str | Path,
                       last_desc: ShortDesc = None) -> List[ProcessedElementResult] | None:
    results = []

    while element_ids:
        element_id = element_ids.pop(0)
        if element_id.startswith("."):
            raise ValueError("Element id must start with a resource type")
        element = get_element_from_snapshot(profile_snapshot, element_id)
        short_desc = (element_id, get_display_from_element_definition(element)) \
            if last_desc is None else None
        result = [ProcessedElementResult(element=element, profile_snapshot=profile_snapshot, module_dir=module_dir_name,
                                         last_short_desc=short_desc)]

        for elem in element.get("type"):
            if elem.get("code") == "Extension":
                profile_urls = elem.get("profile")
                if len(profile_urls) > 1:
                    raise Exception("Extension with multiple types not supported")
                extension = get_extension_definition(os.path.join(modules_dir_path, module_dir_name), profile_urls[0])
                element_ids.insert(0, f"Extension" + element_ids.pop(0))
                result.extend(process_element_id(element_ids, extension, module_dir_name, modules_dir_path))
            elif elem.get("code") == "Reference":
                target_resource_type = elem.get("targetProfile")[0]
                referenced_profile, module_dir_name = get_profiles_with_base_definition(modules_dir_path, target_resource_type)
                element_ids.insert(0, f"{referenced_profile.get('type') + element_ids.pop(0)}")
                result.extend(process_element_id(element_ids, referenced_profile, module_dir_name, modules_dir_path))
        results.extend(result)
    return results


def resolve_defining_id(profile_snapshot: dict, defining_id: str, modules_dir_path: str | Path, module_dir_name: str) \
        -> dict | str:
    """
    :param profile_snapshot: FHIR profile snapshot
    :param defining_id: defining id
    :param module_dir_name: name of the module directory
    :param modules_dir_path: path to the FHIR dataset directory
    :return: resolved defining id
    """
    return get_element_defining_elements(defining_id, profile_snapshot, module_dir_name, modules_dir_path)[-1]


def extract_value_type(value_defining_element: dict, profile_name: str = "") -> VALUE_TYPE_OPTIONS:
    """
    Extracts the value type for the given FHIR profile snapshot at the value defining element id
    :param value_defining_element: element that defines the value
    :param profile_name: name of the FHIR profile for debugging purposes can be omitted
    :return: value type
    """
    if not value_defining_element:
        logger.warning(f"Could not find value defining element for {profile_name}")
    fhir_value_types = value_defining_element.get("type")
    if not fhir_value_types:
        raise InvalidValueTypeException(f"No value type defined in element: {str(value_defining_element)}"
                                        f" in profile: {profile_name}")
    if len(fhir_value_types) > 1:
        raise InvalidValueTypeException(f"More than one value type defined in element: "
                                        f"{str(value_defining_element)} refine the profile: " + profile_name)
    return fhir_value_types[0].get("code")


def extract_reference_type(value_defining_element: dict, modules_dir: str | Path, profile_name: str = "") -> str:
    """
    Extracts the reference type from the given value defining element
    :param value_defining_element: element that defines the value
    :param modules_dir: Path to the directory containing all module data
    :param profile_name: name of the FHIR profile for debugging purposes can be omitted
    :return: reference type
    """
    if not value_defining_element:
        logger.warning(f"Could not find value defining element for {profile_name}")
    # if len(target_profiles) > 1:
    #     raise Exception("Reference with multiple types not supported")
    if not value_defining_element.get("targetProfile"):
        logger.warning(f"Could not find target profile for {profile_name}")
    target_resource_type = value_defining_element.get("targetProfile")[0]
    # FIXME This should not be hardcoded to CDS_Module
    referenced_profile, module_dir = get_profiles_with_base_definition(modules_dir, target_resource_type)
    return referenced_profile.get("type")


def get_selectable_concepts(concept_defining_element, profile_name: str = "",
                            client: TerminologyClient = None) -> ValueSet:
    """
    Returns the answer options for the given concept defining element
    :param concept_defining_element:
    :param profile_name: name of the FHIR profile for debugging purposes can be omitted
    :param client: Client to perform terminology server operations with
    :return: answer options as term codes
    :raises InvalidValueTypeException: if no valueSet is defined for the concept defining element
    """
    if binding := concept_defining_element.get("binding"):
        if value_set_url := binding.get("valueSet"):
            if '|' in value_set_url:
                value_set_url = value_set_url.split('|')[0]
            return ValueSet(value_set_url, client.get_value_set_expansion(value_set_url))
        else:
            raise InvalidValueTypeException(f"No value set defined in element: {str(binding)}"
                                            f" in profile: {profile_name}")
    else:
        raise InvalidValueTypeException(f"No binding defined in element: {str(concept_defining_element)}"
                                        f" in profile: {profile_name}")


def get_units(unit_defining_element, profile_name: str = "", client: TerminologyClient = None) -> List[TermCode]:
    if unit_code := unit_defining_element.get("fixedCode"):
        return [TermCode(UCUM_SYSTEM, unit_code, unit_code)]
    elif unit_code := unit_defining_element.get("patternCode"):
        return [TermCode(UCUM_SYSTEM, unit_code, unit_code)]
    elif binding := unit_defining_element.get("binding"):
        if value_set_url := binding.get("valueSet"):
            return client.get_termcodes_for_value_set(value_set_url)
        else:
            raise InvalidValueTypeException(f"No value set defined in element: {str(binding)}"
                                            f" in profile: {profile_name}")
    else:
        raise InvalidValueTypeException(f"No unit defined in element: {str(unit_defining_element)}"
                                        f" in profile: {profile_name}")


def get_value_set_defining_url(value_set_defining_element: dict, profile_name: str = "") -> str:
    """
    Returns the value set defining url for the given value set defining element
    :param value_set_defining_element: Element that defines the value set
    :param profile_name: Name of the FHIR profile for debugging purposes can be omitted
    :return: Canonical URL of the value set
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


def pattern_coding_to_term_code(element, client: TerminologyClient):
    """
    Converts a patternCoding to a term code
    :param element: Element node from the snapshot with a patternCoding
    :param client: Client instance to perform terminology server operations
    :return: Term code
    """
    code = element["patternCoding"]["code"]
    system = element["patternCoding"]["system"]
    display = client.get_term_code_display(system, code)
    version = element["patternCoding"].get("version")

    if display.isupper():
        display = display.title()
    term_code = TermCode(system, code, display, version)
    return term_code


def fixed_coding_to_term_code(element, client: TerminologyClient):
    """
    Converts a fixedCoding to a term code
    :param element: Element node from the snapshot with a patternCoding
    :param client: Client instance to perform terminology server operations
    :return: Term code
    """
    code = element["fixedCoding"]["code"]
    system = element["fixedCoding"]["system"]
    display = client.get_term_code_display(system, code)
    if display.isupper():
        display = display.title()
    term_code = TermCode(system, code, display)
    return term_code


def pattern_codeable_concept_to_term_code(element, client: TerminologyClient):
    """
    Converts a patternCodeableConcept to a term code
    :param element: Element node from the snapshot with a patternCoding
    :param client: Client instance to perform terminology server operations
    :return: Term code
    """
    code = element["patternCodeableConcept"]["coding"][0]["code"]
    system = element["patternCodeableConcept"]["coding"][0]["system"]
    display = client.get_term_code_display(system, code)
    version = element["patternCodeableConcept"]["coding"][0].get("version")
    if display.isupper():
        display = display.title()
    term_code = TermCode(system, code, display, version)
    return term_code


def fixed_codeable_concept_to_term_code(element, client: TerminologyClient):
    """
    Converts a fixedCodeableConcept to a term code
    :param element: Element node from the snapshot with a patternCoding:
    :param client: Client instance to perform terminology server operations
    :return: Term code
    """
    code = element["fixedCodeableConcept"]["coding"][0]["code"]
    system = element["fixedCodeableConcept"]["coding"][0]["system"]
    display = client.get_term_code_display(system, code)
    version = element["fixedCodeableConcept"]["coding"][0].get("version")
    if display.isupper():
        display = display.title()
    term_code = TermCode(system, code, display, version)
    return term_code


def translate_element_to_fhir_path_expression(elements: List[dict], profile_snapshot, is_composite: bool = False) -> List[str]:
    """
    Translates an element to a fhir search parameter. Be aware not every element is translated alone to a
    fhir path expression. I.E. Extensions elements are translated together with the prior element.
    :param elements: Elements for which the fhir path expressions should be obtained
    :param profile_snapshot: Snapshot of the profile
    :is_composite: special case for when its composite attribute.  .value.ofType(<valueType>)
    :return: FHIR path expressions
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
        if is_composite:
            element_path = f"value.ofType({element_type})"
    result = [element_path]
    if elements:
        result.extend(translate_element_to_fhir_path_expression(elements, profile_snapshot))
    return result


def replace_x_with_cast_expression(element_path, element_type):
    # Regular expression to capture [x] and [x]:arbitrary_slicing
    match = re.search(r'(\[x](?::\w+)?)', element_path)
    if match:
        pre_match = element_path[:match.start()]
        post_match = element_path[match.end():]
        # TODO: Rework handling of FHIRPath-like expressions. We currently only use string manipulation when working
        #       with such expressions which leads to a lot of edge case handling and double checking. Instead strings
        #       should be tokenized somewhat so that information about the expression is readily available throughout
        #       the processing chain
        # Always add parenthesis for now to avoid functions agnostic to the actual structure of the expression to
        # generate invalid FHIRPath expressions accidentally
        replacement = f'({pre_match} as {element_type}){post_match}'
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
    except Exception:
        element_id = re.sub(r'(\[x\]).*', r'\1', element_id)
        parent_element = get_element_from_snapshot(profile_snapshot, element_id)
    return get_element_type(parent_element)


def get_extension_url(element):
    extension_profiles = element.get('type')[0].get('profile')
    if len(extension_profiles) > 1:
        raise Exception("More than one extension found")
    if not extension_profiles:
        raise Exception("No extension profile url found in element: \n" + element)
    return extension_profiles[0]


def get_element_type(element):
    """
    Returns the type of the given element
    :param element: Parent element
    :return: Type of the element
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


def get_term_code_by_id(fhir_profile_snapshot, term_code_defining_id, data_set_dir, module_dir,
                        client: TerminologyClient) -> List[TermCode]:
    """
    Returns the term entries for the given term code defining id
    :param fhir_profile_snapshot: Snapshot of the FHIR profile
    :param term_code_defining_id: ID of the element that defines the term code
    :param data_set_dir: Data set directory of the FHIR profile
    :param module_dir: Module directory of the FHIR profile
    :param client: Client instance to perform terminology server operations
    :return: Term entries
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
            term_code = pattern_coding_to_term_code(term_code_defining_element, client)
            return [term_code]
    if "patternCodeableConcept" in term_code_defining_element:
        if "coding" in term_code_defining_element["patternCodeableConcept"]:
            term_code = pattern_codeable_concept_to_term_code(term_code_defining_element, client)
            return [term_code]
    if "binding" in term_code_defining_element:
        value_set = term_code_defining_element.get("binding").get("valueSet")
        return client.get_termcodes_for_value_set(value_set)
    else:
        tc = try_get_term_code_from_sub_elements(fhir_profile_snapshot, term_code_defining_id, data_set_dir, module_dir,
                                                 client)
        if tc:
            return [tc]
        raise Exception(f"Could not resolve term code defining element: {term_code_defining_element}")


def try_get_term_code_from_sub_elements(fhir_profile_snapshot, parent_coding_id, data_set_dir,
                                        module_dir, client: TerminologyClient) -> Optional[TermCode]:
    if not is_element_in_snapshot(fhir_profile_snapshot, parent_coding_id + ".code"):
        return None
    code_element = resolve_defining_id(fhir_profile_snapshot, parent_coding_id + ".code", data_set_dir, module_dir)
    system_element = resolve_defining_id(fhir_profile_snapshot, parent_coding_id + ".system", data_set_dir,
                                         module_dir)
    if code_element and system_element:
        if "patternCode" in code_element and "patternUri" in system_element:
            return TermCode(system_element["patternUri"], code_element["patternCode"],
                            client.get_term_code_display(system_element["patternUri"],
                                                         code_element["patternCode"]))
        elif "fixedCode" in code_element and "fixedUri" in system_element:
            return TermCode(system_element["fixedUri"], code_element["fixedCode"],
                            client.get_term_code_display(system_element["fixedUri"],
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


def get_fixed_term_codes(element: dict, snapshot: dict, module_dir, data_set_dir,
                         client: TerminologyClient) -> List[TermCode]:
    """
    Returns the fixed term codes of the given element
    """
    if "fixedCodeableConcept" in element:
        return [fixed_codeable_concept_to_term_code(element, client)]
    elif "patternCodeableConcept" in element:
        return [pattern_codeable_concept_to_term_code(element, client)]
    elif "fixedCoding" in element and "code" in element["fixedCoding"]:
        return [fixed_coding_to_term_code(element, client)]
    elif "patternCoding" in element and "code" in element["patternCoding"]:
        return [pattern_coding_to_term_code(element, client)]
    else:
        if tc := try_get_term_code_from_sub_elements(snapshot, element.get("id"), module_dir, data_set_dir, client):
            return [tc]
    return []
