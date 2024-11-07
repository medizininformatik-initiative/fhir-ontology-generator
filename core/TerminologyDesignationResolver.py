import json
import os

class TerminologyDesignationResolver:
    def __init__(self):
        self.code_systems = {}
    # folder_path erstmal temporär, bis das mit dem
    def load_designations(self, folder_path="../example/CodeSystemsTranslations"):
        # load them from a folder for now
        codesystem_files = os.listdir(folder_path)
        for codesystem_file in codesystem_files:
            with open(f"{folder_path}/{codesystem_file}", encoding="UTF-8") as json_file:
                codesystem = json.load(json_file)
                url = codesystem.get('url')
                self.code_systems[url] = codesystem


    # codesystem_url müssen wir noch schauen wie wir darauf referieren
    def resolve_term(self, codesystem_url, term_code):
        display = {}

        codesystem_concepts = self.code_systems.get(codesystem_url).get('concept')
        for concept in codesystem_concepts:
            if concept.get('code') == term_code:
                for designation in concept.get('designation'):
                    if designation.get('language') == 'en':
                        display['en-US'] = designation.get('value')
                    elif designation.get('language') == 'de':
                        display['de-DE'] = designation.get('value')
                    # original ??? müssen wir wohl auch nochmal das original value-set laden oder so,
                    # wobei auch da nicht ersichtlich ist welche sprache es ursprünglich hatter
                break
        return display


if __name__ == "__main__":
    terminology_resolver = TerminologyDesignationResolver()
    terminology_resolver.load_designations()
    print (terminology_resolver.resolve_term("https://fdpg.de/fhir/CodeSystem/Vitalstatus/translations", "L"))
