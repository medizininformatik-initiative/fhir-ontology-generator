import json
import copy
import os
import re
from itertools import groupby
from pathlib import Path

from typing import List, TypeVar, Any, Mapping

from common.util.fhir.bundle import create_bundle, BundleType
from common.util.http.terminology.client import FhirTerminologyClient
from common.util.log.functions import get_class_logger, get_logger
from common.util.project import Project


logger = get_logger(__file__)


def extract_designation(parameters: dict, language: str, fuzzy = True) -> str | None:
    """
    Helper function for extracting language code specific designation display value from `Parameters` resource
    :param parameters: `Parameters` resource to extract display value from
    :param language: Language code identifying display value to extract
    :param fuzzy:
    :return: Either `str` display value or `None` if no designation for language codes exists
    """
    for designation in filter(lambda p: p.get("name") == "designation", parameters.get("parameter", [])):
        part = designation.get("part")
        if part:
            try:
                designation_language = list(filter(lambda p: p.get("name") == "language", part))[0].get("valueCode")
                if len(list(filter(lambda p: p.get("name") == "use", part))) == 0: continue
                designation_use = list(filter(lambda p: p.get("name") == "use", part))[0].get("valueCoding").get("code")
                matches = re.match(rf'^{language}(-\S+)?$', designation_language) if fuzzy else (
                        language == designation_language)
                if matches and (designation_use == "display" or designation_use == "preferredForLanguage"):
                    return list(filter(lambda p: p.get("name") == "value", part))[0].get("valueString")
            except IndexError:
                logger.warning(f"Designation could not be extracted. Code is probably not present on server."
                               f" Code:{designation}")
    return None


T = TypeVar("T")


def chunks(coll: List[T], chunk_size: int = 10) -> List[List[T]]:
    for i in range(0, len(coll), chunk_size):
        yield coll[i:i + chunk_size]


def split_bundle(bundle: dict, chunk_size: int = 10) -> List[dict]:
    if not bundle.get("entry", []):
        return [bundle]
    else:
        bundles = []
        for chunk in chunks(bundle.get("entry"), chunk_size):
            # Perform shallow copy as the `entry` element will be replaced with its chunk
            bundle_chunk = copy.copy(bundle)
            bundle_chunk["entry"] = chunk
            bundles.append(bundle_chunk)
        return bundles


class TerminologyDesignationResolver:
    __logger = get_class_logger("TerminologyDesignationResolver")
    
    def __init__(self, project: Project, base_translations_conf: str | Path = None, max_bundle_size: int = 10_000):
        self.code_systems = {}
        self.__project = project
        self.__client = FhirTerminologyClient.from_project(project)
        self.base_translation_mapping = {}
        if base_translations_conf is not None:
            self.__load_base_translations(base_translations_conf)
        self.max_bundle_size = max_bundle_size

    @staticmethod
    def __optimize_code_system_concepts(code_system_content):
        """
        Reduces the complexity of the code system concepts, making the
        single concepts accessible with .get(code), optimizing speed.
        Transforms:
        "concept": [
            {
                  "code": "L",
                  "designation": [
                        {
                            "value": "Patient lebt",
                            "language": "de"
                        },
                        {
                            "value": "Patient lives",
                            "language": "en"
                        }
                  ]
            }, ...
        To:
        "concept": [
            "L": {
                    'de':"Patient lebt",
                    'en'": "Patient lives"
                {
            }, ...
        """
        temp = {}
        for concept in code_system_content.get('concept'):
            temp[concept.get('code')] = {}
            for designation in concept.get('designation'):
                temp[concept.get('code')][designation.get('language')] = designation.get('value')
        return temp

    def __load_base_translations(self, base_translation_conf: str | Path):
        """
        Loads base translations mapping to later be able to retrieve authoritative designations, i.e. translations, from
        a terminology server. The file should contain a mapping form code system URL to a `Parameters` resource
        specifying common parameters passed for each coding to look up in a request
        """
        self.__logger.debug(f"Loading base translation config located @ {base_translation_conf}")
        if self.base_translation_mapping is None:
            self.base_translation_mapping = dict()
        try:
            with open(base_translation_conf, mode='r', encoding='UTF-8') as conf_file:
                self.base_translation_mapping.update(json.load(conf_file).get("code_system_translations", {}))
        except OSError as exc:
            self.__logger.warning(f"Failed to load base translation config @ {base_translation_conf}", exc_info=exc,
                             stack_info=True)

    def __batch_lookup(self, bundle: dict) -> dict:
        """
        Performs `CodeSystem-lookup` operation in batch against a terminology server and returns the
        response if successful. The passed `Bundle` resource will be split into smaller chunks according to the
        `max_bundle_size` field fo the class instance
        :param bundle: Bundle resource containing individual entries for lookup requests
        :return: Response Bundle resource if successful
        """
        response_bundle = {"resourceType": "Bundle", "type": BundleType.BATCH_RESPONSE.value, "entry": []}
        for bundle_chunk in split_bundle(bundle, self.max_bundle_size):
            response = self.__client.post("", body=json.dumps(bundle_chunk),
                                          headers={'Content-Type': "application/fhir+json",
                                                   'Accept': "application/fhir+json"})
            if response.status_code != 200:
                raise Exception(f"Unexpected status code [actual={response.status_code}, expected=200]. "
                                f"Content: {response.text}")
            else:
                response_bundle["entry"].extend(response.json().get("entry", []))
        return response_bundle

    def __save_bundle_content(self, bundle: dict, system_url: str, languages: List[str]):
        """
        Saves content of batch `CodeSystem/$lookup` bundle to internal designation mapping
        :param bundle: Response bundle of batch `CodeSystem/$lookup` request
        :param system_url: URL of code system to which the codes belong
        :param languages: Language codes to extract from the responses
        """
        if system_url not in self.code_systems:
            self.code_systems[system_url] = {
                "resourceType": "CodeSystem",
                "url": system_url,
                "concept": {}
            }
        code_system_concepts = self.code_systems[system_url]["concept"]
        for entry in bundle.get("entry", []):
            resource = entry.get("resource", {})
            response = entry.get("response", {})
            if not resource:
                msg = "No resource present in bundle entry"
                if "status_code" in response or "outcome" in response:
                    msg += f" [status_code={response['status_code']}]. Details:\n{response['outcome']}"
                self.__logger.warning(msg)
            else:
                match resource["resourceType"]:
                    case "Parameters":
                        for language in languages:
                            code = list(filter(lambda p: p.get("name") == "code", resource.get("parameter", [])))[0] \
                                .get("valueCode")
                            designation = extract_designation(resource, language)
                            if designation:
                                if code not in code_system_concepts:
                                    code_system_concepts[code] = {}
                                designations = code_system_concepts[code]
                                if language not in designations:
                                    designations[language] = designation
                    case "OperationOutcome":
                        self.__logger.warning(f"Operation failed. Details:\n{resource}")
                    case _:
                        self.__logger.warning(f"Unexpected resource type '{resource['type']}'. Skipping")

    def __load_base_designations_for_ui_tree(self, ui_tree: dict):
        """
        Load authoritative designations for concepts in a UI tree using terminology server
        :param ui_tree: UI tree code system entry
        """
        self.__logger.debug("Loading base designations for UI tree")
        request_part = {
            "method": "POST",
            "url": "CodeSystem/$lookup"
        }
        # Process contained trees for each system
        for system_tree in ui_tree:
            system = system_tree.get("system")
            if system is None:
                self.__logger.warning("Tree has no system URL and thus no look up can be performed. Skipping")
                continue
            version = system_tree.get("version")
            parameters_template = self.base_translation_mapping.get(system)
            if parameters_template is None:
                self.__logger.debug(f"No parameters template defined for system [url={system}]. Skipping")
                continue
            self.__logger.debug(f"Processing system tree [url={system}, "f"version={version}]")
            bundle = create_bundle(BundleType.BATCH)
            for entry in system_tree.get("entries", []):
                if "key" not in entry:
                    self.__logger.warning("No key in system tree. Skipping")
                    continue
                parameters = copy.deepcopy(parameters_template)
                parameters.get("parameter").extend([
                    {
                        "name": "code",
                        "valueCode": entry["key"]
                    },
                    {
                        "name": "system",
                        "valueUri": system
                    }
                ])
                bundle["entry"].append(
                    {
                        "resource": parameters,
                        "request": request_part
                    }
                )
            # Perform batch lookup request
            lookup_bundle = self.__batch_lookup(bundle)
            self.__save_bundle_content(lookup_bundle, system, languages=["de", "en"])

    def __load_base_designations_for_value_set(self, value_set: dict):
        """
        Load authoritative designations for concepts in an expanded `ValueSet` resource using terminology server
        :param value_set: Expanded `ValueSet` resource
        """
        self.__logger.debug(f"Loading base designations for value set [url={value_set.get('url')}]")
        request_part = {
            "method": "POST",
            "url": "CodeSystem/$lookup"
        }
        # Process concepts in expansion
        expansion_content = value_set.get("expansion", {}).get("contains", [])
        # Since concepts contained within a ValueSet resource can cover multiple code systems we group them by their
        # code system url
        for system, concepts in groupby(expansion_content, lambda c: c.get("system")):
            parameters_template = self.base_translation_mapping.get(system)
            if parameters_template is None:
                self.__logger.debug(f"No parameters template defined for system [url={system}]. Skipping")
                continue
            self.__logger.debug(f"Processing system concepts [url={system}]")
            bundle = create_bundle(BundleType.BATCH)
            for concept in concepts:
                parameters = copy.deepcopy(parameters_template)
                parameters.get("parameter").extend([
                    {
                        "name": "code",
                        "valueCode": concept["code"]
                    },
                    {
                        "name": "system",
                        "valueUri": system
                    }
                ])
                bundle["entry"].append(
                    {
                        "resource": parameters,
                        "request": request_part
                    }
                )
            # Perform batch lookup request
            lookup_bundle = self.__batch_lookup(bundle)
            self.__save_bundle_content(lookup_bundle, system, languages=["de", "en"])

    def load_base_designations(self, ui_tree_dir: str | Path = None, value_set_dir: str | Path = None):
        """
        Loads authoritative designations for UI trees and expanded `ValueSet` resources using a terminology server.
        Since they are retrieved from the FHIR resources stored by the terminology server, their values are regarded as
        official values and thus override any existing code designation mappings already stored by the object
        :param ui_tree_dir: Path to directory containing UI tree JSON files
        :param value_set_dir: Path to directory containing expanded `ValueSet` resource FHIR JSON files
        """
        self.__logger.debug("Loading base translations")
        if ui_tree_dir is None:
            ui_trees = []
        else:
            ui_trees = [json.load(open(os.path.join(ui_tree_dir, file_name), mode='r', encoding='UTF-8'))
                        for file_name in os.listdir(ui_tree_dir) if file_name.endswith('.json')]
        if value_set_dir:
            value_sets = []
        else:
            value_sets = [json.load(open(os.path.join(value_set_dir, file_name), mode='r', encoding='UTF-8'))
                          for file_name in os.listdir(value_set_dir) if file_name.endswith('.json')]
        if not self.base_translation_mapping:
            self.__logger.warning("No mapping seems to exist and thus no designations can be loaded. Aborting")
        else:
            for ui_tree in ui_trees:
                self.__load_base_designations_for_ui_tree(ui_tree)
            for value_set in value_sets:
                self.__load_base_designations_for_value_set(value_set)

    def load_designations(self, folder_path: str | Path, update_translation_supplements=False):
        """
        Loads the code_system files from specified folder into memory
        :param folder_path: folder containing translated code_systems
        :param update_translation_supplements: specifies if supplements should be downloaded or updated from TERMINOLOGY_SERVER_ADDRESS
        """
        if update_translation_supplements:
            self.__logger.info("Updating the supplement registry")

            supplement_registry = self.__client.get_code_system("fdpg-plus-translation-supplement-registry")
            if supplement_registry is None:
                self.__logger.warning("Could not find supplement registry code system on the terminology server "
                                      "=> Skipping update")
            else:
                for code_system_concept in supplement_registry.concept:
                    for prop in code_system_concept.property:
                        if prop.code == "supplement-canonical":
                            code_system_url_split = prop.valueString.split('|')
                            code_system_url = code_system_url_split[0]
                            code_system_version = ""

                            if len(code_system_url_split) == 2:
                                code_system_version = prop.valueString.split('|')[-1]

                            supplement_code_system_bundle = self.__client.search_code_system(url=code_system_url,
                                                                                             version=code_system_version)
                            if not supplement_code_system_bundle.entry:
                                self.__logger.warning("No entry was found in this bundle => Skipping " +
                                                      code_system_url + "|" + code_system_version)
                                continue

                            supplement_code_system_full_url = supplement_code_system_bundle.entry[0].fullUrl
                            self.__logger.info("Downloading: " + supplement_code_system_full_url)
                            response_cs_content = self.__client.get(full_url=supplement_code_system_full_url,
                                                                    headers={'Accept': "application/fhir+json"})

                            if response_cs_content.status_code != 200:
                                self.__logger.warning("Something went wrong. Status code:" + response_cs_content.status_code + ". Expected 200")
                                self.__logger.debug("Content: " + response_cs_content.content)
                                continue

                            actual_code_system = response_cs_content.json()
                            actual_code_system_name = actual_code_system.get('name')
                            file_path_save_code_system=os.path.join(folder_path, actual_code_system_name + ".json")
                            with open(file_path_save_code_system, mode='w', encoding='UTF-8') as f:
                                f.write(json.dumps(actual_code_system, indent=4))

        codesystem_files = os.listdir(folder_path)
        for codesystem_file in sorted(codesystem_files):
            if codesystem_file.endswith(".json"):
                self.__logger.debug(f"Processing CodeSystem supplement file {codesystem_file}")
                with open(os.path.join(folder_path,codesystem_file), mode='r', encoding="UTF-8") as json_file:
                    codesystem = json.load(json_file)
                    url = codesystem.get('supplements').split("|")[0]

                    codesystem['concept'] = self.__optimize_code_system_concepts(codesystem)

                    if self.code_systems.get(url):
                        for new_concept_code, new_concept_designations in codesystem.get('concept').items():
                            existing_concept = self.code_systems[url]['concept'].get(new_concept_code)

                            if existing_concept:
                                if 'de' not in existing_concept and 'de' in new_concept_designations:
                                    existing_concept['de'] = new_concept_designations.get('de')
                                if 'en' not in existing_concept and 'en' in new_concept_designations:
                                    existing_concept['en'] = new_concept_designations.get('en')
                            else:
                                self.code_systems[url]['concept'][new_concept_code] = new_concept_designations
                    else:
                        self.code_systems[url] = codesystem

    def resolve_term(self, term_code) -> Mapping[str, Any]:
        """
        Generates the 'display' property of a term_code
        providing the ability of multilingual search.
        Supported languages: 'en-US', 'de-DE'

        :param term_code: term_code object used throughout ElasticSearchbatchGenerator.py
        :return:
            A dictionary in the following format:
            {
                "original": "<original>",
                "en": "<language-display>",
                "de": "<language-display>"
            }
        """
        display = {'original': term_code['display'], 'en': "", 'de': ""}
        if self.code_systems.get(term_code['system']):
            concept = self.code_systems.get(term_code['system']).get('concept').get(term_code['code'])
            if concept:
                if 'en' in concept:
                    display['en'] = concept.get('en')
                    if concept.get('en') is None:
                        self.__logger.warning("Did not find Englisch version of code: " + term_code['code'])
                if 'de' in concept:
                    display['de'] = concept.get('de')
                    if concept.get('de') is None:
                        self.__logger.warning("Did not find German version of code: " + term_code['code'])
        else:
            self.__logger.warning(f"Did not find codesystem '{term_code['system']}'. Requested Code: {term_code['code']}")
        return display

    def has_designations_for(self, canonical_url: str) -> bool:
        """
        Checks if there are designations loaded for the code system identified by this canonical URL
        :param canonical_url: Canonical URL of the code system
        :return: Boolean indicating whether this instance has designations for the code system
        """
        return canonical_url in self.code_systems
