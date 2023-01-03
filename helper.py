import errno
import json
import os
import re
from os import path
from typing import List, Set, Protocol

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


def generate_snapshots(package_dir: str, prerequisite_packages: List[str] = None):
    """
    Generates the snapshots for all the profiles in the package_dir folder and its sub folders
    :param prerequisite_packages: list of prerequisite packages
    :param package_dir: directory of the package
    :raises FileNotFoundError: if the package directory could not be found
    :raises NotADirectoryError: if the package directory is not a directory
    """
    prerequisite_packages = prerequisite_packages if prerequisite_packages else []
    if not os.path.exists(package_dir):
        raise FileNotFoundError(f"Package directory does not exist: {package_dir}")
    if not os.path.isdir(package_dir):
        raise NotADirectoryError("package_dir must be a directory")
    saved_path = os.getcwd()
    os.system("fhir install hl7.fhir.r4.core")
    for package in prerequisite_packages:
        os.system(f"fhir install {package}")
    # module folders
    for folder in [f.path for f in os.scandir(package_dir) if f.is_dir()]:
        os.chdir(f"{folder}\\package")
        for file in [f for f in os.listdir('.') if
                     os.path.isfile(f) and is_structured_definition(f) and "-snapshot" not in f]:
            os.system(f"fhir push {file}")
            os.system(f"fhir snapshot")
            os.system(f"fhir save {file[:-5]}-snapshot.json")
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
                 if os.path.isfile(f) and f.name.endswith(".json")]:
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
        json_data = json.load(json_file)
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
    with open(file_name, "a") as f:
        f.write(serializable.to_json())
