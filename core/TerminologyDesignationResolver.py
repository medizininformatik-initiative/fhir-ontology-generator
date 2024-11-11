import json
import logging
import os
from util.LoggingUtil import init_logger, log_to_stdout

logger = init_logger("TerminologyDesignationResolver", logging.DEBUG)
log_to_stdout("TerminologyDesignationResolver", logging.DEBUG)

class TerminologyDesignationResolver:
    def __init__(self):
        self.code_systems = {}

    def load_designations(self, folder_path: str = "../example/code_systems_translations"):
        """
        Loads the code_system files from specified folder into memory
        :param folder_path: folder containing translated code_systems
        """
        codesystem_files = os.listdir(folder_path)
        for codesystem_file in codesystem_files:
            if codesystem_file.endswith(".json"):
                with open(f"{folder_path}/{codesystem_file}", encoding="UTF-8") as json_file:
                    codesystem = json.load(json_file)
                    url = codesystem.get('supplements').split("|")[0]
                    self.code_systems[url] = codesystem
        self.optimize_code_system_concepts()

    def optimize_code_system_concepts(self):
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
            "L": [
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
        """
        for code_system_key, code_system_content in self.code_systems.items():
            temp = {}
            for concept in code_system_content.get('concept'):
                temp[concept.get('code')] = concept.get('designation')

            self.code_systems[code_system_key] = temp

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

        if self.code_systems.get(term_code['system']) is not None:
            concept = self.code_systems.get(term_code['system']).get(term_code['code'])
            if concept is not None:
                for designation in concept:
                    if designation.get('language') == 'en':
                        display['en-US'] = designation.get('value')
                    elif designation.get('language') == 'de':
                        display['de-DE'] = designation.get('value')
        return display
