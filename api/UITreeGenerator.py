import json
import os
from typing import List

from api import StrucutureDefinitionParser as FhirParser
from TerminologService.ValueSetResolver import get_term_entries_from_onto_server
from api.ResourceQueryingMetaDataResolver import ResourceQueryingMetaDataResolver
from helper import is_structure_definition
from model.ResourceQueryingMetaData import ResourceQueryingMetaData
from model.UiDataModel import TermEntry, TermCode


class UITreeGenerator(ResourceQueryingMetaDataResolver):
    """
    Generates the ui tree for the given FHIR profiles
    """

    def __init__(self, querying_meta_data_resolver: ResourceQueryingMetaDataResolver, parser=FhirParser):
        """
        :param querying_meta_data_resolver: resolves the for the query relevant meta data for a given FHIR profile
        :parser: parses the FHIR profiles
        snapshot
        """
        self.query_meta_data_resolver = querying_meta_data_resolver
        self.module_dir = ""
        self.data_set_dir = ""
        self.parser = parser

    def generate_ui_trees(self, differential_dir: str):
        """
        Generates the ui trees for all FHIR profiles in the differential directory
        :param differential_dir: path to the directory which contains the FHIR profiles
        :return: ui trees for all FHIR profiles in the differential directory
        """
        self.data_set_dir = differential_dir
        result: List[TermEntry] = []
        for folder in [folder for folder in os.scandir(differential_dir) if folder.is_dir()]:
            self.module_dir = folder.path
            files = [file.path for file in os.scandir(f"{folder.path}/package") if file.is_file()
                     and file.name.endswith("snapshot.json") and is_structure_definition(file.path)]
            result.append(self.generate_module_ui_tree(TermCode("fdpg.mii.cds", folder.name, folder.name), files))
        return result

    def get_query_meta_data(self, fhir_profile_snapshot: dict, context: TermCode) -> List[ResourceQueryingMetaData]:
        """
        Returns the query meta data for the given FHIR profile snapshot
        :param fhir_profile_snapshot: FHIR profile snapshot
        :param context: context of the FHIR profile snapshot
        :return: Query meta data
        """
        return self.query_meta_data_resolver.get_query_meta_data(fhir_profile_snapshot, context)

    def generate_ui_subtree(self, fhir_profile_snapshot: dict, context: TermCode = None) -> List[TermEntry]:
        """
        Generates the ui subtree for the given FHIR profile snapshot
        :param fhir_profile_snapshot: FHIR profile snapshot json representation
        :param context: of the parent node | None if this is the root node
        :return: root of the ui subtree
        """

        # If no context is provided the context code is derived from the profile name.
        # If the profile is based on mii cds profile, the name of that profile is used as context. Otherwise the name
        # of the profile is used as context code.
        # baseDefinition =
        # https://www.medizininformatik-initiative.de/fhir/core/modul-person/StructureDefinition/Diagnose
        # => context_code = Diagnose
        # baseDefinition = http://hl7.org/fhir/StructureDefinition/Condition and url =
        # https://www.medizininformatik-initiative.de/fhir/core/modul-person/StructureDefinition/Todesursache
        # => context_code = Todesursache
        context_code = fhir_profile_snapshot["baseDefinition"].split("/")[-1] \
            if fhir_profile_snapshot["baseDefinition"] in "https://www.medizininformatik-initiative.de/" \
            else fhir_profile_snapshot["url"].split("/")[-1]
        sub_tree_context = context if context else TermCode("mii.fdpg.cds", context_code, context_code)
        applicable_querying_meta_data = self.get_query_meta_data(fhir_profile_snapshot, sub_tree_context)
        if not applicable_querying_meta_data:
            print(f"No querying meta data found for {fhir_profile_snapshot['name']}")
        return self.translate(fhir_profile_snapshot, applicable_querying_meta_data, sub_tree_context)

    def translate(self, fhir_profile_snapshot: dict, applicable_querying_meta_data: List[ResourceQueryingMetaData],
                  _context: TermCode) \
            -> List[TermEntry]:
        """
        Translates the given FHIR profile snapshot into a ui tree
        :param fhir_profile_snapshot: FHIR profile snapshot json representation
        :param applicable_querying_meta_data: applicable querying meta data
        :param _context: context for the FHIR profile snapshot
        :return: root of the ui tree
        """
        result: List[TermEntry] = []
        for applicable_querying_meta_data in applicable_querying_meta_data:
            print(f"Translating {fhir_profile_snapshot['name']} with {applicable_querying_meta_data}")
            # TODO: add context information to the ui tree
            if applicable_querying_meta_data.term_code_defining_id:
                result += self.get_term_entries_by_id(fhir_profile_snapshot, applicable_querying_meta_data.
                                                      term_code_defining_id)
            elif applicable_querying_meta_data.term_codes:
                result += [TermEntry(applicable_querying_meta_data.term_codes)]
        return result

    def generate_module_ui_tree(self, module_context: TermCode, files: List[str]) -> TermEntry:
        """
        Generates the ui tree for the given module
        :param module_context: context of the module
        :param files: FHIR profiles snapshot paths in the module
        :return:
        """
        if len(files) == 1:
            with open(files[0], 'r') as snapshot:
                snapshot_json = json.load(snapshot)
                root = TermEntry([TermCode(module_context.system, snapshot_json.get("name"),
                                           snapshot_json.get("name"))], "Category", selectable=False, leaf=False)
                root.children = self.generate_ui_subtree(snapshot_json)
                return root
        else:
            root = TermEntry([module_context], "Category", selectable=False,
                             leaf=False)
            for snapshot_file in files:
                with open(snapshot_file, encoding="utf8") as snapshot:
                    root.children += self.generate_ui_subtree(json.load(snapshot), module_context)
            return root

    def get_term_entries_by_id(self, fhir_profile_snapshot, term_code_defining_id) -> List[TermEntry]:
        """
        Returns the term entries for the given term code defining id
        :param fhir_profile_snapshot: snapshot of the FHIR profile
        :param term_code_defining_id: id of the element that defines the term code
        :return: term entries
        """
        term_code_defining_element = self.parser.resolve_defining_id(fhir_profile_snapshot, term_code_defining_id,
                                                                     self.data_set_dir, self.module_dir)
        if not term_code_defining_element:
            raise Exception(f"Could not resolve term code defining id {term_code_defining_id} "
                            f"in {fhir_profile_snapshot.get('name')}")
        if "patternCoding" in term_code_defining_element:
            if "code" in term_code_defining_element["patternCoding"]:
                term_code = self.parser.pattern_coding_to_term_code(term_code_defining_element)
                return [TermEntry([term_code], "CodeableConcept", leaf=True, selectable=True)]
        if "patternCodeableConcept" in term_code_defining_element:
            if "coding" in term_code_defining_element["patternCodeableConcept"]:
                term_code = self.parser.pattern_codeable_concept_to_term_code(term_code_defining_element)
                return [TermEntry([term_code], "CodeableConcept", leaf=True, selectable=True)]
        if "binding" in term_code_defining_element:
            value_set = term_code_defining_element.get("binding").get("valueSet")
            return get_term_entries_from_onto_server(value_set)
        else:
            raise Exception(f"Could not resolve term code defining element: {term_code_defining_element}")
