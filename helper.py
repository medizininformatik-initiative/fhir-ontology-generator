from __future__ import annotations

import errno
import json
import os
import re
from os import path
from typing import List, Set, Protocol, Dict

from model.ResourceQueryingMetaData import ResourceQueryingMetaData
from model.UiDataModel import TermCode, TranslationElementDisplay


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
            os.makedirs(directory)
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

        if os.path.exists("package.json"):
            os.remove("package.json")

        os.system("fhir install hl7.fhir.r4.core")

        for package in prerequisite_packages:

            if os.path.exists("package.json"):
                os.remove("package.json")

            os.system(f"fhir install {package} --here")

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
    if reinstall or not (os.path.exists("fhirpkg.lock.json") and os.path.exists("package.json")):
        install_prerequisites()
    # module folders
    for folder in [f.path for f in os.scandir(package_dir) if f.is_dir()]:
        if folder.endswith("dependencies"):
            continue
        os.chdir(f"{folder}")
        # generates snapshots for all differential in the package if they do not exist
        for file in [f for f in os.listdir('.') if
                     os.path.isfile(f) and is_structure_definition(f) and "-snapshot" not in f
                     and f[:-5] + "-snapshot.json" not in os.listdir('.')]:
            generate_snapshot()
        if not os.path.exists("extension"):
            os.chdir(saved_path)
            continue
        os.chdir(f"extension")
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


def load_english_to_german_attribute_names() -> Dict[str, str]:
    with open("../../resources/english_to_german_attribute_names.json", "r", encoding="utf-8") as f:
        attribute_names = json.load(f)
    return attribute_names


def extract_translations_from_snapshot_element(element: dict) -> dict:
    """
    extracts the translations from _short of element
    :param element: the element to extract
    :return: {"de-DE":"germanTranslation","en-US":"englishTranslation"}
    """
    translation = {}
    if element.get("_short").get("extension"):
        for lang_container in element.get("_short").get("extension"):
            language = next(filter(lambda x: x.get("url") == "lang", lang_container.get("extension"))).get("valueCode")
            language_value = next(filter(lambda x: x.get("url") == "content", lang_container.get("extension"))).get("valueString")
            translation[language] = language_value

    return translation


def generate_attribute_key(element_id: str, snapshot_element=None) -> TermCode:
    """
    Generates the attribute key for the given element id
    :param element_id: element id
    :param snapshot_element: dict that contains the content of the element
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
    if snapshot_element is not None:
        if snapshot_element.get("_short"):
            display = TranslationElementDisplay(display,[])
            for lang_code,lang_content in extract_translations_from_snapshot_element(snapshot_element).items():
                display.add_as_language(lang_code, lang_content)
        else:
            print("-----------------------------------------> no _short was foud, therefore no translations were found")

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
    mkdir_if_not_exists("ui-trees")
    mkdir_if_not_exists("csv")
    mkdir_if_not_exists("ui-profiles")
    mkdir_if_not_exists("ui-profiles-old")
    mkdir_if_not_exists("mapping-old")
    mkdir_if_not_exists("mapping-old/fhir")
    mkdir_if_not_exists("mapping-old/cql")
    mkdir_if_not_exists("value-sets")
    mkdir_if_not_exists("criteria-sets")
