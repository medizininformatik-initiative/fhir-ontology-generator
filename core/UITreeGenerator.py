import json
import os
from typing import List

from core import StrucutureDefinitionParser as FhirParser
from TerminologService.ValueSetResolver import get_term_entries_from_onto_server
from core.ResourceQueryingMetaDataResolver import ResourceQueryingMetaDataResolver
from helper import is_structure_definition
from model.ResourceQueryingMetaData import ResourceQueryingMetaData
from model.UiDataModel import TermEntry, TermCode, Module


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
        for module_dir in [folder for folder in os.scandir(differential_dir) if folder.is_dir()]:
            self.module_dir = module_dir.path
            files = [file.path for file in os.scandir(f"{module_dir.path}/package") if file.is_file()
                     and file.name.endswith("snapshot.json") and is_structure_definition(file.path)]
            print(files)
            result.append(self.generate_module_ui_tree(module_dir.name, files))
        return result

    def get_query_meta_data(self, fhir_profile_snapshot: dict, module_name: str) -> List[ResourceQueryingMetaData]:
        """
        Returns the query meta data for the given FHIR profile snapshot
        :param fhir_profile_snapshot: FHIR profile snapshot
        :param module_name: name of the module the profile belongs to
        :return: Query meta data
        """
        return self.query_meta_data_resolver.get_query_meta_data(fhir_profile_snapshot, module_name)

    def generate_ui_subtree(self, fhir_profile_snapshot: dict, module_name) -> List[TermEntry]:
        """
        Generates the ui subtree for the given FHIR profile snapshot
        :param fhir_profile_snapshot: FHIR profile snapshot
        :param module_name: name of the module the profile belongs to
        :return: root of the ui subtree
        """
        applicable_querying_meta_data = self.get_query_meta_data(fhir_profile_snapshot, module_name)
        if not applicable_querying_meta_data:
            print(f"No querying meta data found for {fhir_profile_snapshot['name']}")
        return self.translate(fhir_profile_snapshot, applicable_querying_meta_data)

    def translate(self, fhir_profile_snapshot: dict, applicable_querying_meta_data: List[ResourceQueryingMetaData]) \
            -> List[TermEntry]:
        """
        Translates the given FHIR profile snapshot into a ui tree
        :param fhir_profile_snapshot: FHIR profile snapshot json representation
        :param applicable_querying_meta_data: applicable querying meta data
        :return: root of the ui tree
        """
        result: List[TermEntry] = []
        for applicable_querying_meta_data in applicable_querying_meta_data:
            # TODO: add context information to the ui tree
            if applicable_querying_meta_data.term_code_defining_id:
                print(f"Term code defining id: {applicable_querying_meta_data.term_code_defining_id}")
                sub_tree = self.get_term_entries_by_id(fhir_profile_snapshot, applicable_querying_meta_data.
                                                       term_code_defining_id)
                module_definition = applicable_querying_meta_data.module
                module_instance = Module(module_definition.get('code'), module_definition.get('display'))
                self.set_context(sub_tree, applicable_querying_meta_data.context)
                self.set_module(sub_tree, module_instance)
                result += sub_tree
            elif applicable_querying_meta_data.term_codes:
                result += [
                    TermEntry(applicable_querying_meta_data.term_codes, context=applicable_querying_meta_data.context)]
        return result

    def set_context(self, entries: List[TermEntry], context: TermCode):
        for entry in entries:
            entry.context = context
            if entry.children:
                self.set_context(entry.children, context)

    def set_module(self, entries: List[TermEntry], module: Module):
        for entry in entries:
            entry.module = module
            if entry.children:
                self.set_module(entry.children, module)

    def generate_module_ui_tree(self, module_name, files: List[str]) -> TermEntry:
        """
        Generates the ui tree for the given module
        :param module_name:  name of the module the profiles belongs to
        :param files: FHIR profiles snapshot paths in the module
        :return:
        """
        root_term_code = TermCode("fdpg.mii.cds", module_name, module_name)
        root = TermEntry([root_term_code], "Category", selectable=False, leaf=False,
                         context=root_term_code)
        if len(files) == 1:
            with open(files[0], 'r', encoding="utf-8") as snapshot:
                snapshot_json = json.load(snapshot)
                root.children = self.generate_ui_subtree(snapshot_json, module_name)
        else:
            for snapshot_file in files:
                print(snapshot_file)
                with open(snapshot_file, encoding="utf8") as snapshot:
                    snapshot_json = json.load(snapshot)
                    sub_entry_term_code = TermCode("fdpg.mii.cds", snapshot_json.get("name"),
                                                   snapshot_json.get("name"))
                    sub_entry = TermEntry([sub_entry_term_code], "Category", selectable=False,
                                          leaf=False, context=None)
                    sub_entry.children += self.generate_ui_subtree(snapshot_json, module_name)
                    if sub_entry.children:
                        sub_entry.context = sub_entry.children[0].context
                        root.children.append(sub_entry)
            if len(root.children) == 1:
                root.children = root.children[0].children
        if root.children:
            root.context.system = root.children[0].context.system
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
            term_code = self.parser.try_get_term_code_from_sub_elements(fhir_profile_snapshot,
                                                                        term_code_defining_id, self.data_set_dir,
                                                                        self.module_dir)
            if term_code:
                return [TermEntry([term_code], "CodeableConcept", leaf=True, selectable=True)]
            raise Exception(
                f"Could not resolve term code defining element: {term_code_defining_element} in "
                f"{fhir_profile_snapshot.get('name')}")
