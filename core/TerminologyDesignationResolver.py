import json
import copy
import logging
import os
from itertools import groupby
from util.LoggingUtil import init_logger, log_to_stdout
from typing import List
from TerminologService.TermServerConstants import TERMINOLOGY_SERVER_ADDRESS, SERVER_CERTIFICATE, PRIVATE_KEY, REQUESTS_SESSION
from util.FhirUtil import create_bundle, BundleType

logger = init_logger("TerminologyDesignationResolver", logging.DEBUG)
log_to_stdout("TerminologyDesignationResolver", logging.DEBUG)


class TerminologyDesignationResolver:
    def __init__(self, base_translations_conf: str = None, server_address: str = TERMINOLOGY_SERVER_ADDRESS):
        self.code_systems = {}
        self.server_address = server_address
        self.base_translation_mapping = {}
        if base_translations_conf is not None:
            self.__load_base_translations(base_translations_conf)

    def __optimize_code_system_concepts(self, code_system_content):
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

    def __load_base_translations(self, base_translation_conf: str):
        """
        Loads base translations mapping to later be able to retrieve authoritative designations, i.e. translations, from
        a terminology server. The file should contain a mapping form code system URL to a `Parameters` resource
        specifying common parameters passed for each coding to look up in a request
        """
        logger.debug(f"Loading base translation config located @ {base_translation_conf}")
        if self.base_translation_mapping is None:
            self.base_translation_mapping = dict()
        try:
            with open(base_translation_conf, mode='r', encoding='UTF-8') as conf_file:
                self.base_translation_mapping.update(json.load(conf_file).get("code_system_translations", {}))
        except OSError as exc:
            logger.warning(f"Failed to load base translation config @ {base_translation_conf}", exc_info=exc,
                           stack_info=True)

    def __bulk_lookup(self, bundle: dict) -> dict:
        """
        Performs `CodeSystem-lookup` operation in bulk against a terminology server and returns the
        response if successful
        :param bundle: Bundle resource containing individual entries for lookup requests
        :return: Response Bundle resource if successful
        """
        media_type = "application/fhir+json"
        response = REQUESTS_SESSION.post(
            url = self.server_address.rstrip('/'),
            json=bundle,
            headers={"Content-Type": media_type, "Accept": media_type},
            cert=(SERVER_CERTIFICATE, PRIVATE_KEY)
        )
        if response.status_code != 200:
            raise Exception(f"Unexpected status code [actual={response.status_code}, expected=200]. "
                            f"Content: {response.text}")
        else:
            return response.json()

    def __extract_designation(self, parameters: dict, language: str) -> str | None:
        for designation in filter(lambda p: p.get("name") == "designation", parameters.get("parameters", [])):
            part = designation.get("part")
            if part:
                designation_language = list(filter(lambda p: p.get("name") == "language", part))[0].get("valueCode")
                designation_use = list(filter(lambda p: p.get("name") == "use", part))[0].get("valueCoding").get("code")
                if designation_language == language and designation_use == "display":
                    return list(filter(lambda p: p.get("name") == "value", part))[0].get("valueString")
        return None

    def __save_bundle_content(self, bundle: dict, system_url: str, languages: List[str]):
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
                logger.warning(msg)
            else:
                match resource["type"]:
                    case "Parameters":
                        for language in languages:
                            code = list(filter(lambda p: p.get("name") == "code", resource.get("parameter", [])))[0]\
                                .get("valueCode")
                            designation = self.__extract_designation(resource, language)
                            if designation:
                                if code in code_system_concepts:
                                    code_system_concepts[code] = {}
                                designations = code_system_concepts[code]
                                if language not in designations:
                                    designations[language] = designation
                    case "OperationOutcome":
                        logger.warning(f"Operation failed. Details:\n{resource}")
                    case _:
                        logger.warning(f"Unexpected resource type '{resource['type']}'. Skipping")

    def __load_base_designations_for_ui_tree(self, ui_tree: dict):
        logger.debug("Loading base designations for UI tree")
        request_part = {
            "method": "POST",
            "url": "CodeSystem/$lookup"
        }
        # Process contained trees for each system
        for system_tree in ui_tree:
            system = system_tree.get("system")
            if system is None:
                logger.warning("Tree has no system URL and thus no look up can be performed. Skipping")
                continue
            version = system_tree.get("version")
            parameters_template = self.base_translation_mapping.get(system)
            if parameters_template is None:
                logger.debug(f"No parameters template defined for system [url={system}]. Skipping")
                continue
            logger.debug(f"Processing system tree [url={system}, "
                         f"version={version}]")
            bundle = create_bundle(BundleType.batch)
            for entry in system_tree.get("entries", []):
                if "key" not in entry:
                    logger.warning("No key in system tree. Skipping")
                    continue
                parameters = copy.deepcopy(parameters_template)
                parameters.get("parameters").append(
                    {
                        "name": "code",
                        "valueCode": entry["key"]
                    }
                )
                bundle["entry"].append(
                    {
                        "resource": parameters,
                        "request": request_part
                    }
                )
            # Perform bulk lookup request
            lookup_bundle = self.__bulk_lookup(bundle)
            self.__save_bundle_content(lookup_bundle, system, languages=["de", "en"])


    def __load_base_designations_for_value_set(self, value_set: dict):
        logger.debug("Loading base designations for value set")
        request_part = {
            "method": "POST",
            "url": "CodeSystem/$lookup"
        }
        # Process concepts in expansion
        expansion_content = value_set.get("expansion", {}).get("contains", [])
        # Since concepts contained within a ValueSet resource can cover multiple code systems we group them by their
        # code system url

    def load_base_designations(self, ui_trees: List[dict], value_sets: List[dict]):
        logger.debug("Loading base translations")
        if not self.base_translation_mapping:
            logger.warning("No mapping seems to exist and thus no designations can be loaded")
        else:
            for ui_tree in ui_trees:
                self.__load_base_designations_for_ui_tree(ui_tree)
            for value_set in value_sets:
                self.load_base_designations_for_value_set(value_set)


    def load_designations(self, folder_path: str = os.path.join("..", "example", "code_systems_translations")):
        """
        Loads the code_system files from specified folder into memory
        :param folder_path: folder containing translated code_systems
        """
        codesystem_files = os.listdir(folder_path)
        for codesystem_file in sorted(codesystem_files):
            if codesystem_file.endswith(".json"):
                with open(f"{folder_path}/{codesystem_file}", encoding="UTF-8") as json_file:
                    codesystem = json.load(json_file)
                    url = codesystem.get('supplements').split("|")[0]

                    codesystem['concept'] = self.optimize_code_system_concepts(codesystem)

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


    def resolve_term(self, term_code):
        """
        Generates the 'display' property of a term_code
        providing the ability of multilingual search.
        Supported languages: 'en-US', 'de-DE'

        :param term_code: term_code object used throughout ElasticSearchBulkGenerator.py
        :return:
            A dictionary in the following format:
            {
                "original": "<original>",
                "en-US": "<language-display>",
                "de-DE": "<language-display>"
            }
        """
        display = {'original': term_code['display'], 'en-US': "", 'de-DE': ""}
        if self.code_systems.get(term_code['system']):
            concept = self.code_systems.get(term_code['system']).get('concept').get(term_code['code'])
            if concept:
                if 'en' in concept:
                    display['en-US'] = concept.get('en')
                if 'de' in concept:
                    display['de-DE'] = concept.get('de')
        else:
            logger.info("Did not find codesystem: "+term_code['system'])
        return display
