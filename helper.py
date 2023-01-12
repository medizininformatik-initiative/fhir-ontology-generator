from __future__ import annotations

import errno
import json
import os
import re
from os import path
from typing import List, Set, Protocol, Dict

from model.ResourceQueryingMetaData import ResourceQueryingMetaData
from model.UIProfileModel import VALUE_TYPE_OPTIONS
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
                     os.path.isfile(f) and is_structured_definition(f) and "-snapshot" not in f
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
        with open(file.path) as f:
            query_meta_data.append(ResourceQueryingMetaData.from_json(f))
    return query_meta_data


def is_structured_definition(file: str) -> bool:
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


def find_search_parameter(full_expression: str, resource_type: str, attribute_type: VALUE_TYPE_OPTIONS = None) -> str:
    """
    Finds the search parameter for a given expression. The search parameter with the shortest expression limited to the
    resource_type is returned. I.e expression: Observation.code results in code and not combo-code. As the expression:
    (Observation.code) | (Medication.code) | (Condition.code) | (Procedure.code) | (DiagnosticReport.code) | ...
    filtered by resource type results in (Observation.code) which is shorter than the combo-code expression:
    (Observation.code) | (Observation.component.code)
    :param full_expression: the expression
    :param resource_type: FHIR resource type
    :param attribute_type: the attribute type
    :return: the search parameter
    :raises ValueError: if the search parameter could not be found
    """
    expression = full_expression
    replaced_expression = None
    current_expression_match = None
    result = None
    attribute_type = VALUE_TYPE_TO_FHIR_SEARCH_TYPE.get(attribute_type, attribute_type)
    # ToDo: Consider replacing this with code logic
    with open(f"../../resources/fhir_resource_id_path_mapping.json") as f:
        resource_id_path_mapping = json.load(f)
        for expression_key in resource_id_path_mapping.keys():
            if expression_key in expression:
                replaced_expression = expression_key
                expression = resource_id_path_mapping.get(expression_key, expression)
    expression = expression.replace('[x]', '')
    if expression.endswith(":"):
        expression = expression[:-1]
    print(f"expression: {expression}, resource_type: {resource_type}, attribute_type: {attribute_type}")
    if "." not in expression:
        raise ValueError(f"Search parameter could not be found for expression: {expression}")

    for search_parameter in get_all_search_parameters():
        if search_parameter_expression := get_expression_if_resource_and_type_match(search_parameter, resource_type,
                                                                                    attribute_type):
            search_parameter_expression = expression_to_resource_relevant_expression(search_parameter_expression,
                                                                                     resource_type)
            if current_expression_match:
                if len(current_expression_match) > len(search_parameter_expression):
                    current_expression_match = search_parameter_expression
                    result = search_parameter
            else:
                current_expression_match = search_parameter_expression
                result = search_parameter
    if result:
        if result.get("type") == "reference":
            targets = result.get("target")
            if len(targets) != 1:
                raise ValueError(f"Chained search parameters with no or multiple targets are not supported: {result}")
            if replaced_expression:
                expression = full_expression.replace(replaced_expression, f"{targets[0]}").rstrip()
                print(expression, targets[0], attribute_type)
                return result.get("code") + "." + find_search_parameter(expression, targets[0], attribute_type)
        else:
            return result.get("code")
    else:
        try:
            return find_search_parameter(expression[:expression.rfind('.')], resource_type, attribute_type)
        except ValueError:
            raise ValueError(f"Search parameter could not be found for expression {expression} . Consider adding a "
                             f"custom search parameter")


def get_all_search_parameters() -> List[Dict]:
    with open("../../resources/fhir_search_parameter_definition.json") as f:
        search_parameter_definition = json.load(f)
    with open(
            "../../resources/core_data_sets/de.medizininformatikinitiative.kerndatensatz.biobank#1.0.3"
            "/package/SearchParameter-SearchParamDiagnosis.json") as f:
        search_parameter_definition.get("entry").append({"resource": json.load(f)})
        return [entry.get("resource") for entry in search_parameter_definition.get("entry") if entry.get("resource")]


def get_expression_if_resource_and_type_match(search_parameter: Dict, resource_type: str, attribute_type: str) -> str:
    if resource_type in search_parameter.get("base") and attribute_type \
            in search_parameter.get("type") or search_parameter.get("type") == "reference":
        return search_parameter.get("expression")


def expression_to_resource_relevant_expression(expression: str, resource_type: str) -> str:
    resource_relevant_sub_expressions = [subexpression for subexpression in
                                         expression.split("|") if
                                         resource_type in subexpression]
    filtered_expression = "|".join(resource_relevant_sub_expressions)
    return filtered_expression
