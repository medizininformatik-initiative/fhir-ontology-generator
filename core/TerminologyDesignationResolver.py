import json
import logging
import os
from util.LoggingUtil import init_logger, log_to_stdout

logger = init_logger("TerminologyDesignationResolver", logging.DEBUG)
log_to_stdout("TerminologyDesignationResolver", logging.DEBUG)


class TerminologyDesignationResolver:
    def __init__(self):
        self.code_systems = {}
    def optimize_code_system_concepts(self, code_system_content):
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

    def load_designations(self, folder_path: str = "../example/code_systems_translations"):
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

                    # optimize/reformat input
                    codesystem['concept'] = self.optimize_code_system_concepts(codesystem)

                    if self.code_systems.get(url):
                        for new_concept_code, new_concept_designations in codesystem.get('concept').items(): #cycle through all concepts
                            existing_concept = self.code_systems[url]['concept'][new_concept_code]

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
            logger.info("Did not find codesystem:{term_code['system']}")
        return display
