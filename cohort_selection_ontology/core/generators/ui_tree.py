import json
import os
from typing import List

from cohort_selection_ontology.util.fhir import structure_definition as sd
from cohort_selection_ontology.core.terminology.client import (
    CohortSelectionTerminologyClient,
)
from cohort_selection_ontology.core.resolvers.querying_metadata import (
    ResourceQueryingMetaDataResolver,
)
from common.util.fhir.structure_definition import is_structure_definition
from cohort_selection_ontology.model.query_metadata import ResourceQueryingMetaData
from cohort_selection_ontology.model.tree_map import (
    ContextualizedTermCodeInfo,
    ContextualizedTermCodeInfoList,
    TermEntryNode,
    TreeMapList,
    TreeMap,
)
from cohort_selection_ontology.model.ui_data import TermCode
from common.util.log.functions import get_class_logger
from common.util.project import Project


class UITreeGenerator:
    """
    Generates the ui tree for the given FHIR profiles
    """

    __logger = get_class_logger("UITreeGenerator")

    def __init__(
        self,
        project: Project,
        querying_meta_data_resolver: ResourceQueryingMetaDataResolver,
    ):
        """
        :param project: Project to operate on
        :param querying_meta_data_resolver: resolves the for the query relevant metadata for a given FHIR profile
        snapshot
        """
        self.__project = project
        self.__client = CohortSelectionTerminologyClient(self.__project)
        self.query_meta_data_resolver = querying_meta_data_resolver
        self.__modules_dir = self.__project.input.cso.mkdirs("modules")

    def generate_ui_subtree(
        self, fhir_profile_snapshot: dict, module_name
    ) -> List[TreeMap]:
        """
        Generates the ui subtree for the given FHIR profile snapshot
        :param fhir_profile_snapshot: FHIR profile snapshot
        :param module_name: name of the module the profile belongs to
        :return: root of the ui subtree
        """
        applicable_querying_meta_data = (
            self.query_meta_data_resolver.get_query_meta_data(
                fhir_profile_snapshot, module_name
            )
        )
        if not applicable_querying_meta_data:
            self.__logger.warning(
                f"No querying meta data found for {fhir_profile_snapshot['name']}"
            )
        return self.translate(
            fhir_profile_snapshot, applicable_querying_meta_data, module_name
        )

    def translate(
        self,
        fhir_profile_snapshot: dict,
        applicable_querying_meta_data: List[ResourceQueryingMetaData],
        module_dir_name: str,
    ) -> List[TreeMap]:
        """
        Translates the given FHIR profile snapshot into a UI tree
        :param fhir_profile_snapshot: FHIR profile snapshot json representation
        :param applicable_querying_meta_data: applicable querying metadata
        :param module_dir_name: Name of the module directory
        :return: root of the ui tree
        """
        result_map: dict[(TermCode, str), TreeMap] = dict()
        for qmd in applicable_querying_meta_data:
            tree_maps: List[TreeMap] = list()
            if qmd.term_code_defining_id:
                tree_maps = self.get_term_entries_by_id(
                    fhir_profile_snapshot, qmd.term_code_defining_id, module_dir_name
                )
            elif qmd.term_codes:
                tree_maps = [
                    TreeMap(
                        {term_code.code: TermEntryNode(term_code)},
                        context=qmd.context,
                        system=term_code.system,
                        version=term_code.version,
                    )
                    for term_code in qmd.term_codes
                ]
            for tree_map in tree_maps:
                context: TermCode = qmd.context
                tree_map.context = context
                if (context, tree_map.system) not in result_map:
                    result_map[(context, tree_map.system)] = tree_map
                else:
                    # Add entries of tree map to existing tree map with same context and system URL
                    result_map[(context, tree_map.system)].entries.update(
                        tree_map.entries
                    )
        return list(result_map.values())

    def generate_module_ui_tree(self, module_name) -> TreeMapList:
        """
        Generates the ui tree for the given module
        :param module_name:  name of the module the profiles belongs to
        :return:
        """
        files = [
            file.path
            for file in os.scandir(
                os.path.join(self.__modules_dir, module_name, "differential", "package")
            )
            if file.is_file()
            and file.name.endswith("snapshot.json")
            and is_structure_definition(file.path)
        ]

        result = TreeMapList()
        for snapshot_file in files:
            with open(snapshot_file, encoding="utf8") as snapshot:
                snapshot_json = json.load(snapshot)
                result.entries += self.generate_ui_subtree(snapshot_json, module_name)
                # Quick and dirty fix to get the module name
                applicable_querying_meta_data = (
                    self.query_meta_data_resolver.get_query_meta_data(
                        snapshot_json, module_name
                    )
                )
                if applicable_querying_meta_data:
                    result.module_name = applicable_querying_meta_data[0].module.display
        return result

    def get_term_entries_by_id(
        self, fhir_profile_snapshot, term_code_defining_id, module_dir_name: str
    ) -> List[TreeMap]:
        """
        Returns the tree map for the given term code defining id
        :param fhir_profile_snapshot: snapshot of the FHIR profile
        :param term_code_defining_id: id of the element that defines the term code
        :param module_dir_name: Name of the module directory
        :return: term entries
        """
        term_code_defining_element = sd.resolve_defining_id(
            fhir_profile_snapshot,
            term_code_defining_id,
            self.__modules_dir,
            module_dir_name,
        )
        if not term_code_defining_element:
            raise Exception(
                f"Could not resolve term code defining id {term_code_defining_id} "
                f"in {fhir_profile_snapshot.get('name')}"
            )
        if "patternCoding" in term_code_defining_element:
            pattern_coding = term_code_defining_element["patternCoding"]
            if "code" in pattern_coding:
                term_code = sd.pattern_coding_to_term_code(
                    term_code_defining_element, self.__client
                )
                return [
                    TreeMap(
                        {term_code.code: TermEntryNode(term_code)},
                        None,
                        term_code.system,
                        term_code.version,
                    )
                ]
        if "patternCodeableConcept" in term_code_defining_element:
            if "coding" in term_code_defining_element["patternCodeableConcept"]:
                term_code = sd.pattern_codeable_concept_to_term_code(
                    term_code_defining_element, self.__client
                )
                return [
                    TreeMap(
                        {term_code.code: TermEntryNode(term_code)},
                        None,
                        term_code.system,
                        term_code.version,
                    )
                ]
        if "binding" in term_code_defining_element:
            value_set = term_code_defining_element.get("binding").get("valueSet")
            return [self.__client.get_term_map(value_set)]
        else:
            term_code = sd.try_get_term_code_from_sub_elements(
                fhir_profile_snapshot,
                term_code_defining_id,
                self.__modules_dir,
                module_dir_name,
                self.__client,
            )
            if term_code:
                return [
                    TreeMap(
                        {term_code.code: TermEntryNode(term_code)},
                        None,
                        term_code.system,
                        term_code.version,
                    )
                ]
            raise Exception(
                f"Could not resolve term code for element '{term_code_defining_element.get('id')}' in profile "
                f"'{fhir_profile_snapshot.get('name')}'"
            )

    def generate_contextualized_term_code_info_list(
        self, module_name: str
    ) -> List[ContextualizedTermCodeInfoList]:
        """
        Generates ContextualizedTermCodeInfoList for all FHIR profiles in the differential directory
        :param module_name: Name of the module (directory)
        :return: ContextualizedTermCodeInfoList for all FHIR profiles in the differential directory
        """
        result: List[ContextualizedTermCodeInfoList] = []
        files = [
            file.path
            for file in os.scandir(
                os.path.join(self.__modules_dir, module_name, "differential", "package")
            )
            if file.is_file()
            and file.name.endswith("snapshot.json")
            and is_structure_definition(file.path)
        ]
        result.append(
            self.generate_module_contextualized_term_code_info(module_name, files)
        )
        return result

    def generate_module_contextualized_term_code_info(
        self, module_name, files: List[str]
    ) -> ContextualizedTermCodeInfoList:
        """
        Generates the ContextualizedTermCodeInfoList for the given module
        :param module_name: name of the module the profiles belongs to
        :param files: FHIR profiles snapshot paths in the module
        :return: List of ContextualizedTermCodeInfoList
        """
        result = ContextualizedTermCodeInfoList()
        for snapshot_file in files:
            with open(snapshot_file, encoding="utf8") as snapshot:
                snapshot_json = json.load(snapshot)
                result.entries += (
                    self.generate_contextualized_term_code_info_list_for_snapshot(
                        snapshot_json, module_name
                    )
                )
        return result

    def generate_contextualized_term_code_info_list_for_snapshot(
        self, fhir_profile_snapshot: dict, module_name: str
    ) -> ContextualizedTermCodeInfoList:
        """
        Generates a ContextualizedTermCodeInfoList for a single FHIR profile snapshot
        :param fhir_profile_snapshot: FHIR profile snapshot
        :param module_name: name of the module the profile belongs to
        :return: ContextualizedTermCodeInfoList
        """
        contextualized_term_code_infos = []
        applicable_querying_meta_data = (
            self.query_meta_data_resolver.get_query_meta_data(
                fhir_profile_snapshot, module_name
            )
        )

        for querying_meta_data in applicable_querying_meta_data:
            contextualized_term_code_info = self.create_contextualized_term_code_info(
                fhir_profile_snapshot, querying_meta_data, module_name
            )
            contextualized_term_code_infos += contextualized_term_code_info

        return contextualized_term_code_infos

    def create_contextualized_term_code_info(
        self,
        fhir_profile_snapshot: dict,
        querying_meta_data: ResourceQueryingMetaData,
        module_dir_name: str,
    ) -> List[ContextualizedTermCodeInfo]:
        """
        Creates a ContextualizedTermCodeInfo object for a given FHIR profile snapshot and querying metadata
        :param fhir_profile_snapshot: FHIR profile snapshot
        :param querying_meta_data: applicable querying metadata
        :param module_dir_name: Name of the module directory
        :return: ContextualizedTermCodeInfo
        """
        context = querying_meta_data.context
        module = querying_meta_data.module

        if not querying_meta_data.term_code_defining_id:
            contextualized_term_code_infos = []
            for term_code in querying_meta_data.term_codes:
                contextualized_term_code_infos.append(
                    ContextualizedTermCodeInfo(
                        term_code,
                        context,
                        module,
                        siblings=[
                            sibling
                            for sibling in querying_meta_data.term_codes
                            if sibling != term_code
                        ],
                    )
                )
            return contextualized_term_code_infos

        contextualized_term_code_infos = self.get_term_info_by_id(
            fhir_profile_snapshot,
            querying_meta_data.term_code_defining_id,
            module_dir_name,
        )
        for contextualized_term_code_info in contextualized_term_code_infos:
            contextualized_term_code_info.context = context
            contextualized_term_code_info.module = module
        return contextualized_term_code_infos

    def get_term_info_by_id(
        self, fhir_profile_snapshot, term_code_defining_id, module_dir_name: str
    ) -> List[ContextualizedTermCodeInfo]:
        term_code_defining_element = sd.resolve_defining_id(
            fhir_profile_snapshot,
            term_code_defining_id,
            self.__modules_dir,
            module_dir_name,
        )
        if not term_code_defining_element:
            raise Exception(
                f"Could not resolve term code defining id {term_code_defining_id} "
                f"in {fhir_profile_snapshot.get('name')}"
            )
        if "patternCoding" in term_code_defining_element:
            if "code" in term_code_defining_element["patternCoding"]:
                term_code = sd.pattern_coding_to_term_code(
                    term_code_defining_element, self.__client
                )
                return [ContextualizedTermCodeInfo(term_code)]
        if "patternCodeableConcept" in term_code_defining_element:
            if "coding" in term_code_defining_element["patternCodeableConcept"]:
                term_code = sd.pattern_codeable_concept_to_term_code(
                    term_code_defining_element, self.__client
                )
                return [ContextualizedTermCodeInfo(term_code)]
        if "binding" in term_code_defining_element:
            value_set = term_code_defining_element.get("binding").get("valueSet")
            return self.__client.get_term_info(value_set)
        else:
            term_code = sd.try_get_term_code_from_sub_elements(
                fhir_profile_snapshot,
                term_code_defining_id,
                self.__modules_dir,
                module_dir_name,
                self.__client,
            )
            if term_code:
                return [ContextualizedTermCodeInfo(term_code)]
            raise Exception(
                f"Could not resolve term code defining element: {term_code_defining_element} in "
                f"{fhir_profile_snapshot.get('name')}"
            )
