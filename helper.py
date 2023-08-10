from __future__ import annotations

import errno
import functools
import json
import math
import os
import re
from collections import OrderedDict as orderedDict
from os import path
from typing import List, Set, Protocol, Dict, Tuple, OrderedDict

from model.ResourceQueryingMetaData import ResourceQueryingMetaData
from model.UiDataModel import TermCode


def traverse_tree(result: List[TermCode], node: dict):
    """
    Traverse the tree and collect all selectable nodes
    :param result: roots of the tree that are selectable
    :param node: the current tree node
    """
    if children := node.get("children"):
        for child in children:
            if child.get("selectable"):
                result += [TermCode(**termCode) for termCode in child.get("termCodes")]
            traverse_tree(result, child)


def get_term_selectable_codes_from_ui_profile(profile: dict) -> Set[TermCode]:
    """
    Get all selectable nodes from the ui profile
    :param profile: ui profile
    :return: set of selectable leaf nodes
    """
    result = []
    if profile.get("selectable"):
        result += [TermCode(**termCode) for termCode in profile.get("termCodes")]
    traverse_tree(result, profile)
    return set(result)


def to_upper_camel_case(string: str) -> str:
    """
    Convert a string to upper camel case
    :param string: input string
    :return: the string in upper camel case
    """
    result = ""
    if re.match("([A-Z][a-z0-9]+)+", string) and " " not in string:
        return string
    for substring in string.split(" "):
        result += substring.capitalize()
    return result


def download_simplifier_packages(package_names: List[str]):
    """
    Downloads the core data set from the MII and saves the profiles in the resources/core_data_sets folder
    """

    mkdir_if_not_exists("resources/core_data_sets")
    for dataset in package_names:
        saved_path = os.getcwd()
        os.chdir("resources/core_data_sets")
        os.system(f"fhir install {dataset} --here")
        os.chdir(saved_path)


def mkdir_if_not_exists(directory: str):
    """
    Creates a directory if it does not exist
    :param directory: name of the directory
    :raises OSError: if the directory could not be created
    """
    if not path.isdir(f"./{directory}"):
        try:
            os.mkdir(directory)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise


def generate_snapshots(package_dir: str, prerequisite_packages: List[str] = None, reinstall: bool = False):
    """
    Generates the snapshots for all the profiles in the package_dir folder and its sub folders
    :param prerequisite_packages: list of prerequisite packages
    :param package_dir: directory of the package
    :param reinstall: if true the required packages will be reinstalled
    :raises FileNotFoundError: if the package directory could not be found
    :raises NotADirectoryError: if the package directory is not a directory
    """

    def install_prerequisites():
        os.system("fhir install hl7.fhir.r4.core")
        for package in prerequisite_packages:
            os.system(f"fhir install {package}")

    def generate_snapshot():
        os.system(f"fhir push {file}")
        os.system(f"fhir snapshot")
        os.system(f"fhir save {file[:-5]}-snapshot.json")

    prerequisite_packages = prerequisite_packages if prerequisite_packages else []
    if not os.path.exists(package_dir):
        raise FileNotFoundError(f"Package directory does not exist: {package_dir}")
    if not os.path.isdir(package_dir):
        raise NotADirectoryError("package_dir must be a directory")
    saved_path = os.getcwd()
    # module folders
    for folder in [f.path for f in os.scandir(package_dir) if f.is_dir()]:
        os.chdir(f"{folder}\\package")
        if reinstall or not (os.path.exists("fhirpkg.lock.json") and os.path.exists("package.json")):
            install_prerequisites()
        # generates snapshots for all differential in the package if they do not exist
        for file in [f for f in os.listdir('.') if
                     os.path.isfile(f) and is_structure_definition(f) and "-snapshot" not in f
                     and f[:-5] + "-snapshot.json" not in os.listdir('.')]:
            generate_snapshot()
        os.chdir(f"extension")
        if reinstall or not (os.path.exists("fhirpkg.lock.json") and os.path.exists("package.json")):
            install_prerequisites()
        for file in [f for f in os.listdir('.') if
                     os.path.isfile(f) and is_structure_definition(f) and "-snapshot" not in f
                     and f[:-5] + "-snapshot.json" not in os.listdir('.')]:
            generate_snapshot()
        os.chdir(saved_path)


def load_querying_meta_data(resource_querying_meta_data_dir: str) -> List[ResourceQueryingMetaData]:
    """
    Loads the querying meta data from the querying meta data file
    :return: the querying meta data
    :raises FileNotFoundError: if the querying meta data directory could not be found
    :raises NotADirectoryError: if the querying meta data directory is not a directory
    """
    if not os.path.exists(resource_querying_meta_data_dir):
        raise FileNotFoundError(f"Resource querying meta data file does not exist: {resource_querying_meta_data_dir}")
    if not os.path.isdir(resource_querying_meta_data_dir):
        raise NotADirectoryError("resource_querying_meta_data_dir must be a directory")
    query_meta_data: List[ResourceQueryingMetaData] = []
    for file in [f for f in os.scandir(resource_querying_meta_data_dir)
                 if os.path.isfile(f.path) and f.name.endswith(".json")]:
        with open(file.path, encoding="utf-8") as f:
            query_meta_data.append(ResourceQueryingMetaData.from_json(f))
    return query_meta_data


def is_structure_definition(file: str) -> bool:
    """
    Checks if a file is a structured definition
    :param file: potential structured definition
    :return: true if the file is a structured definition else false
    """
    with open(file, encoding="UTF-8") as json_file:
        try:
            json_data = json.load(json_file)
        except json.decoder.JSONDecodeError:
            print(f"Could not decode {file}")
            return False
        if json_data.get("resourceType") == "StructureDefinition":
            return True
        return False


class JsonSerializable(Protocol):
    def to_json(self) -> str:
        ...


def write_object_as_json(serializable: JsonSerializable, file_name: str):
    """
    Writes a list of objects as json to a file
    :param serializable: object that can be serialized to json
    :param file_name: name of the file
    """
    with open(file_name, "w") as f:
        f.write(serializable.to_json())


VALUE_TYPE_TO_FHIR_SEARCH_TYPE = {
    "concept": "token",
    "quantity": "quantity",
    "reference": "reference",
    "date": "date"
}


def get_fhir_search_parameters() -> List[dict]:
    pass


def flatten(lst) -> List:
    """
    Flattens a list of lists with arbitrary depth
    :param lst: the list to flatten
    :return: the flattened list
    """
    if not isinstance(lst, list):
        yield lst
    else:
        for element in lst:
            if isinstance(element, list) and not isinstance(element, (str, bytes)):
                yield from flatten(element)
            else:
                yield element


def get_cleaned_expressions(search_parameter: dict) -> List[str]:
    """
    Gets the cleaned expressions of a search parameter
    :param search_parameter: the search parameter
    :return: the cleaned expressions
    """
    expressions = search_parameter.get("expression")
    if not expressions:
        return []
    expressions = [translate_as_function_to_operand(expression) if not re.match(r"\((.*?)\)", expression) else
                   translate_as_function_to_operand(expression[1:-1]) for expression in
                   expressions.split(" | ")]
    expressions = [convert_of_type_to_as_operand(expression) for expression in expressions]
    return expressions


def convert_of_type_to_as_operand(expression: str) -> str:
    """
    Converts an of-type expression to an as expression
    :param expression: the expression
    :return: the converted expression
    """
    while ".ofType(" in expression:
        expression = re.sub(r"\.ofType\((.*?)\)", r" as \1", expression)
    return expression


def translate_as_function_to_operand(expression) -> str:
    """
    fhirPath expressions like Observation.value.as(CodeableConcept) are deprecated and should be replaced with
    Observation.value as CodeableConcept
    :param expression: the expression to update
    :return: the updated expression
    """
    while "as(" in expression:
        as_start = expression.find(".as(")
        as_end = expression.find(")", as_start)

        expression = (expression[:as_start] + " as " + expression[as_start + 4:as_end] + expression[as_end + 1:])
        if len(expression) > as_end + 1 and expression[as_end + 1] == ".":
            Exception("Not implemented: Todo: Put operation in round brackets. "
                      "I.e. Observation.(value as CodeableConcept).text")
    return expression


def find_search_parameter(fhir_path_expressions: List[str]) -> OrderedDict[str, dict]:
    """
    Finds the search parameter for a fhir path expression. Only the shortest expression is considered
    :param fhir_path_expressions: fhir path expressions to be mapped to search parameters
    :return: the search parameter
    :raises ValueError: if the search parameter could not be found
    """
    # int parameter is used to find the shortest expression and not returned in the result

    fhir_path_expressions = [expression for expression in fhir_path_expressions if
                             not expression.startswith("Extension")]
    print(f"Finding search parameter for {fhir_path_expressions}")
    fhir_path_expressions_to_search_parameter: OrderedDict[str, Tuple[dict, int]] = orderedDict(
        [(expression, (None, math.inf)) for expression in fhir_path_expressions]
    )
    for search_parameter in get_all_search_parameters():
        expressions = get_cleaned_expressions(search_parameter)
        for path_expression in fhir_path_expressions:
            if path_expression in expressions:
                resource_type = path_expression.split('.')[0]
                number_of_relevant_expressions = len(list(filter(lambda x: x.startswith(resource_type), expressions)))
                if not fhir_path_expressions_to_search_parameter.get(path_expression) or \
                        number_of_relevant_expressions \
                        < fhir_path_expressions_to_search_parameter.get(path_expression)[1]:
                    fhir_path_expressions_to_search_parameter[path_expression] = (search_parameter,
                                                                                  number_of_relevant_expressions)
    result = orderedDict([(key, value[0]) for key, value in fhir_path_expressions_to_search_parameter.items()])
    if missing_search_parameters := [key for key, value in result.items() if not value]:
        if any([" as " in fhir_path_expressions and '.' not in fhir_path_expressions.split("as")[1] for
                fhir_path_expressions in missing_search_parameters]):
            result_without_as_cast = find_search_parameter([fhir_path_expressions.split(" as ")[0] for
                                                            fhir_path_expressions in missing_search_parameters])
            result = orderedDict([(key if key.split(" as ")[0] not in result_without_as_cast else
                                   key.split(" as ")[0],
                                   value if key.split(" as ")[0] not in result_without_as_cast else
                                   result_without_as_cast[key.split(" as ")[0]]) for key, value in result.items()])
        else:
            result_without_last_path_element = find_search_parameter([fhir_path_expressions.rsplit(".", 1)[0] for
                                                                      fhir_path_expressions in
                                                                      missing_search_parameters])
            result = orderedDict([(key if key.rsplit(".", 1)[0] not in result_without_last_path_element else
                                   key.rsplit(".", 1)[0], value if key.rsplit(".", 1)[0] not in
                                                                   result_without_last_path_element else
                                   result_without_last_path_element[key.rsplit(".", 1)[0]]) for key, value in
                                  result.items()])
        if missing_search_parameters := [key for key, value in result.items() if not value]:
            raise ValueError(f"Could not find search parameter for {missing_search_parameters} \n"
                             f"You may need to add an custom search parameter")
    return result


def validate_chainable(chainable_search_parameter) -> bool:
    """
    Validates the chaining of search parameters
    :param chainable_search_parameter: the search parameter to be chained
    :return: true if the search parameter can be chained else false
    """
    if not chainable_search_parameter:
        raise ValueError("No search parameters to chain")
    elif len(chainable_search_parameter) == 1:
        return True
    return functools.reduce(
        lambda x, y: True if x and len(set(y.get("base", [])).intersection(x.get("target", []))) != 0 else False,
        chainable_search_parameter)


def get_all_search_parameters() -> List[Dict]:
    # TODO: This has to be configurable
    with open("../../resources/fhir_search_parameter_definition.json", 'r', encoding="utf-8") as f:
        search_parameter_definition = json.load(f)
    with open("../../resources/fhir-search-params/fhir-search-params.json", 'r', encoding="utf-8") as f:
        search_parameter_definition.get("entry").extend(json.load(f).get("entry"))
    with open(
            "../../resources/core_data_sets/de.medizininformatikinitiative.kerndatensatz.biobank#1.0.3"
            "/package/SearchParameter-SearchParamDiagnosis.json") as f:
        search_parameter_definition.get("entry").append({"resource": json.load(f)})
        return [entry.get("resource") for entry in search_parameter_definition.get("entry") if
                entry.get("resource")]


def get_expression_if_resource_and_type_match(search_parameter: Dict, resource_type: str,
                                              attribute_type: str) -> str:
    if resource_type in search_parameter.get("base") and attribute_type \
            in search_parameter.get("type") or search_parameter.get("type") == "reference":
        return search_parameter.get("expression")


def expression_to_resource_relevant_expression(expression: str, resource_type: str) -> str:
    resource_relevant_sub_expressions = [subexpression for subexpression in
                                         expression.split("|") if
                                         resource_type in subexpression]
    filtered_expression = "|".join(resource_relevant_sub_expressions)
    return filtered_expression


def load_english_to_german_attribute_names() -> Dict[str, str]:
    with open("../../resources/english_to_german_attribute_names.json", "r", encoding="utf-8") as f:
        attribute_names = json.load(f)
    return attribute_names


def generate_attribute_key(element_id: str) -> TermCode:
    """
    Generates the attribute key for the given element id
    :param element_id: element id
    :return: attribute key
    """
    if '(' and ')' in element_id:
        element_id = element_id[element_id.rfind('(') + 1:element_id.find(')')]
    if ':' in element_id:
        element_id = element_id.split(':')[-1]
        key = element_id.split('.')[0]
    else:
        key = element_id.split('.')[-1]
    display = get_german_display(key)
    if not key:
        raise ValueError(f"Could not find key for {element_id}")
    return TermCode("http://hl7.org/fhir/StructureDefinition", key, display)


def get_german_display(key: str) -> str:
    """
    Returns the german display for the given key if it exists else the key itself and creates an entry in the
    english_to_german_attribute_names.json
    :param key: attribute key
    :return: german display or original key
    """
    english_to_german_attribute_names = load_english_to_german_attribute_names()
    if key not in english_to_german_attribute_names:
        english_to_german_attribute_names[key] = key
        with open("../../resources/english_to_german_attribute_names.json", "w", encoding="utf-8") as f:
            json.dump(english_to_german_attribute_names, f, ensure_ascii=False, indent=4)
    return english_to_german_attribute_names.get(key)


def generate_result_folder():
    """
    Generates the mapping, csv and ui-profiles folder if they do not exist in the result folder
    :return:
    """
    mkdir_if_not_exists("mapping")
    mkdir_if_not_exists("mapping/fhir")
    mkdir_if_not_exists("mapping/cql")
    mkdir_if_not_exists("ui_trees")
    mkdir_if_not_exists("csv")
    mkdir_if_not_exists("ui-profiles")
    mkdir_if_not_exists("ui-profiles-old")
    mkdir_if_not_exists("mapping-old")
    mkdir_if_not_exists("mapping-old/fhir")
    mkdir_if_not_exists("mapping-old/cql")
