from __future__ import annotations

import copy
import errno
import json
import os
import re
from os import path
from typing import List, Set, Protocol

from typing_extensions import deprecated

from cohort_selection_ontology.model.query_metadata import ResourceQueryingMetaData
from cohort_selection_ontology.model.ui_data import TermCode, TranslationElementDisplay
from common.exceptions.translation import MissingTranslationException
from common.util.log.functions import get_logger

logger = get_logger(__file__)

translation_map_default = {'de-DE': {'language': "de-DE", 'value': ""}, 'en-US': {'language': "en-US", 'value': ""}}

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
            logger.warning(f"Could not decode {file}")
            return False
        if json_data.get("resourceType") == "StructureDefinition":
            return True
        return False


class JSONSerializable(Protocol):
    def to_json(self) -> str:
        ...


def write_object_as_json(serializable: JSONSerializable, file_name: str):
    """
    Writes a list of objects as json to a file
    :param serializable: object that can be serialized to json
    :param file_name: name of the file
    """
    os.makedirs(os.path.dirname(file_name), exist_ok=True)
    with open(file_name, mode="w", encoding="utf-8") as f:
        f.write(serializable.to_json())


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


def get_attribute_key(element_id: str) -> str:
    """
    Generates the attribute key from the given element id (`ElementDefinition.id`)

    :param element_id: element id the key will be based on
    :return: attribute key
    """
    if '(' and ')' in element_id:
        element_id = element_id[element_id.rfind('(') + 1:element_id.find(')')]

    if ':' in element_id:
        element_id = element_id.split(':')[-1]
        key = element_id.split('.')[0]
    else:
        key = element_id.split('.')[-1]

    if not key:
        raise ValueError(f"Could not find key for {element_id}")

    return key


def get_display_from_element_definition(snapshot_element: dict,
                                        default: str = None) -> TranslationElementDisplay:
    """
    Extracts the display and translations from the descriptive elements within the ElementDefinition instance. If the
    identified `ElementDefinition` instance in the provided snapshot features translations for the elements short
    description, they will be provided as translations of the display value. The `original` display value is determined
    as follows:

    If a snapshot element with the provided if exists:

    - Use the `short` element value of the snapshot element if it exists
    - Otherwise use the `sliceName` element value of the snapshot element if it exists

    Else use the attribute key code

    :param snapshot_element: the element to extract (display) translations from
    :param default: value used as display if there is no other valid source in the element definition
    :return: TranslationElementDisplay instance holding the display value and all language variants
    """
    translations_map = copy.deepcopy(translation_map_default)
    display = default
    try:
        if snapshot_element is None or len(snapshot_element.keys()) == 0:
            raise MissingTranslationException(f"No translations can be extracted since an empty element was passed")
        if snapshot_element.get("short"):
            display = snapshot_element.get('short')
        elif snapshot_element.get("sliceName"):
            logger.info(f"Falling back to value of 'sliceName' for original display value of element. A short "
                         f"description via 'short' element should be added")
            display = snapshot_element.get('sliceName')

        for lang_container in snapshot_element.get("_short", {}).get("extension", []):
            if lang_container.get("url") != "http://hl7.org/fhir/StructureDefinition/translation":
                continue
            language = next(filter(lambda x: x.get("url") == "lang", lang_container.get("extension"))).get("valueCode")
            language_value = next(filter(lambda x: x.get("url") == "content", lang_container.get("extension"))).get("valueString")
            translations_map[language] = {'language': language, 'value': language_value}

        if translations_map == translation_map_default:
            logger.warning(f"No translation could be identified for element '{snapshot_element.get('id')}' since no "
                           f"language extensions are present => Defaulting")

    except MissingTranslationException as exc:
        logger.warning(exc)
    except Exception as exc:
        logger.warning(f"Something went wrong when trying to extract translations from element '{snapshot_element.get('id')}'. "
                       f"Reason: {exc}", exc_info=exc)

    return TranslationElementDisplay(original=display, translations=list(translations_map.values()))


def process_element_definition(snapshot_element: dict, default: str = None) -> (TermCode, TranslationElementDisplay):
    """
    Uses the provided ElementDefinition instance to determine the attribute code as well as associated display values
    (primary value and - if present - language variants)

    :param snapshot_element: ElementDefinition instance to process
    :param default: value to use as fallback if there is no 'id' in the ElementDefinition
    :return: the attribute code and suitable display values
    """
    if 'id' not in snapshot_element:
        key = default
    else:
        key = get_attribute_key(snapshot_element.get('id'))

    display = get_display_from_element_definition(snapshot_element, default=key)

    return TermCode("http://hl7.org/fhir/StructureDefinition", key, display.original), display


@deprecated("Switch over to process_element_definition to obtain better display values")
def generate_attribute_key(element_id: str) -> TermCode:
    key = get_attribute_key(element_id)
    return TermCode("http://hl7.org/fhir/StructureDefinition", key, key)

