from __future__ import annotations

import json
import os
from typing import Tuple, List, Dict

from api import StrucutureDefinitionParser as FHIRParser
from api.ResourceQueryingMetaDataResolver import ResourceQueryingMetaDataResolver
from api.StrucutureDefinitionParser import resolve_defining_id, extract_value_type
from helper import generate_attribute_key
from model.MappingDataModel import CQLMapping
from model.ResourceQueryingMetaData import ResourceQueryingMetaData
from model.UIProfileModel import VALUE_TYPE_OPTIONS
from model.UiDataModel import TermCode


class CQLMappingGenerator(object):
    def __init__(self, querying_meta_data_resolver: ResourceQueryingMetaDataResolver, parser=FHIRParser):
        """
        :param querying_meta_data_resolver: resolves the for the query relevant meta data for a given FHIR profile
        snapshot
        """
        self.querying_meta_data_resolver = querying_meta_data_resolver
        self.generated_mappings = []
        self.parser = parser
        self.data_set_dir: str = ""
        self.module_dir: str = ""

    def resolve_fhir_path(self, element_id) -> str:
        """
        Based on the element id, this method resolves the FHIR path for the given FHIR Resource attribute
        :param element_id: element id that defines the of the FHIR Resource attribute
        :return: FHIR path
        """
        pass

    def generate_mapping(self, fhir_dataset_dir: str) \
            -> Tuple[Dict[Tuple[TermCode, TermCode], str], Dict[str, CQLMapping]]:
        """
        Generates the FHIR search mappings for the given FHIR dataset directory
        :param fhir_dataset_dir: FHIR dataset directory
        :return: normalized term code FHIR search mapping
        """
        self.data_set_dir = fhir_dataset_dir
        full_context_term_code_cql_mapping_name_mapping: Dict[Tuple[TermCode, TermCode]] | dict = {}
        full_cql_mapping_name_cql_mapping: Dict[str, CQLMapping] | dict = {}
        for module_dir in [folder for folder in os.scandir(fhir_dataset_dir) if folder.is_dir()]:
            self.module_dir: str = module_dir.path
            files = [file.path for file in os.scandir(f"{fhir_dataset_dir}/{module_dir.name}/package") if file.is_file()
                     and file.name.endswith("snapshot.json")]
            for file in files:
                with open(file, "r", encoding="utf8") as f:
                    snapshot = json.load(f)
                    context = TermCode("fdpg.mii.cds", module_dir.name, module_dir.name)
                    context_tc_to_mapping_name, cql_mapping_name_to_mapping = \
                        self.generate_normalized_term_code_cql_mapping(snapshot, context)
                    full_context_term_code_cql_mapping_name_mapping.update(context_tc_to_mapping_name)
                    full_cql_mapping_name_cql_mapping.update(cql_mapping_name_to_mapping)
        return (full_context_term_code_cql_mapping_name_mapping,
                full_cql_mapping_name_cql_mapping)

    def generate_normalized_term_code_cql_mapping(self, profile_snapshot, context: TermCode) \
            -> Tuple[Dict[Tuple[TermCode, TermCode], str], Dict[str, CQLMapping]]:
        """
        Generates the normalized term code to CQL mapping for the given FHIR profile snapshot
        :param profile_snapshot: FHIR profile snapshot
        :param context: context of the FHIR profile
        :return: normalized term code to CQL mapping
        """
        querying_meta_data: List[ResourceQueryingMetaData] = \
            self.querying_meta_data_resolver.get_query_meta_data(profile_snapshot, context)
        term_code_mapping_name_mapping: Dict[Tuple[TermCode, TermCode], str] | dict = {}
        mapping_name_cql_mapping: Dict[str, CQLMapping] | dict = {}
        for querying_meta_data_entry in querying_meta_data:
            if querying_meta_data_entry.name not in self.generated_mappings:
                cql_mapping = self.generate_cql_mapping(profile_snapshot, querying_meta_data_entry)
                self.generated_mappings.append(querying_meta_data_entry.name)
                mapping_name = cql_mapping.name
                mapping_name_cql_mapping[mapping_name] = cql_mapping
            else:
                mapping_name = querying_meta_data_entry.name
            # The logic to get the term_codes here always has to be identical with the mapping Generators!
            term_codes = querying_meta_data_entry.term_codes if querying_meta_data_entry.term_codes else \
                self.parser.get_term_code_by_id(profile_snapshot, querying_meta_data_entry.term_code_defining_id,
                                                self.data_set_dir, self.module_dir)
            primary_keys = [(context, term_code) for term_code in term_codes]
            mapping_names = [mapping_name] * len(primary_keys)
            table = dict(zip(primary_keys, mapping_names))
            term_code_mapping_name_mapping.update(table)
        return term_code_mapping_name_mapping, mapping_name_cql_mapping

    def generate_cql_mapping(self, profile_snapshot, querying_meta_data: ResourceQueryingMetaData) \
            -> CQLMapping:
        """
        Generates the CQL mapping for the given FHIR profile snapshot and querying meta data entry
        :param profile_snapshot: FHIR profile snapshot
        :param querying_meta_data: querying meta data entry
        :return: CQL mapping
        """
        cql_mapping = CQLMapping(querying_meta_data.name)
        cql_mapping.resource_type = querying_meta_data.resource_type
        if tc_defining_id := querying_meta_data.term_code_defining_id:
            cql_mapping.termCodeFhirPath = self.translate_element_id_to_fhir_path_expressions(
                tc_defining_id, profile_snapshot)
        if val_defining_id := querying_meta_data.value_defining_id:
            cql_mapping.termValueFhirPath = self.translate_element_id_to_fhir_path_expressions(
                val_defining_id, profile_snapshot)
        if time_defining_id := querying_meta_data.time_restriction_defining_id:
            cql_mapping.timeRestrictionPath = self.translate_element_id_to_fhir_path_expressions(
                time_defining_id, profile_snapshot)
        for attr_defining_id, attr_type in querying_meta_data.attribute_defining_id_type_map.items():
            attribute_key = generate_attribute_key(attr_defining_id)
            attribute_type = attr_type if attr_type else self.get_attribute_type(profile_snapshot,
                                                                                 attr_defining_id)
            attribute_fhir_path = self.translate_element_id_to_fhir_path_expressions(attr_defining_id,
                                                                                     profile_snapshot)
            cql_mapping.add_attribute(attribute_type, attribute_key, attribute_fhir_path)
        return cql_mapping

    def translate_element_id_to_fhir_path_expressions(self, element_id, profile_snapshot: dict) -> str:
        """
        Translates an element id to a fhir search parameter
        :param element_id: element id
        :param profile_snapshot: FHIR profile snapshot containing the element id
        :return: fhir search parameter
        """
        elements = self.parser.get_element_defining_elements(element_id, profile_snapshot, self.module_dir,
                                                             self.data_set_dir)
        expressions = self.parser.translate_element_to_fhir_path_expression(elements)
        return [self.get_old_path_expression(expression) for expression in expressions][-1]

    @staticmethod
    def get_old_path_expression(path_expression: str) -> str:
        # TODO: Remove this method once the new path expressions are compatible with the cql implementation?
        """
        Translates a path expression to the old path expression
        :param path_expression: path expression
        :return: old path expression
        """
        path = path_expression[path_expression.find('.') + 1:]
        # remove " as *" part
        if " as " in path:
            path = path[:path.find(" as ")]
        return path

    def get_attribute_type(self, profile_snapshot: dict, attribute_id: str) -> VALUE_TYPE_OPTIONS:
        """
        Returns the type of the given attribute
        :param profile_snapshot: FHIR profile snapshot
        :param attribute_id: attribute id
        :return: attribute type
        """
        # remove cast expression as it is irrelevant for the type
        if " as ValueSet" in attribute_id:
            attribute_id = attribute_id.replace(" as ValueSet", "")
        attribute_element = resolve_defining_id(profile_snapshot, attribute_id, self.data_set_dir, self.module_dir)
        return extract_value_type(attribute_element, profile_snapshot.get('name'))
