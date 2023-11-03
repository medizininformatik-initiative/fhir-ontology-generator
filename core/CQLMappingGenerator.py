from __future__ import annotations

import json
import os
import re
from typing import Tuple, List, Dict

from core import StrucutureDefinitionParser as FHIRParser
from core.ResourceQueryingMetaDataResolver import ResourceQueryingMetaDataResolver
from core.StrucutureDefinitionParser import resolve_defining_id, extract_value_type, extract_reference_type
from helper import generate_attribute_key
from model.MappingDataModel import CQLMapping, CQLAttributeSearchParameter
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
                    context_tc_to_mapping_name, cql_mapping_name_to_mapping = \
                        self.generate_normalized_term_code_cql_mapping(snapshot, module_dir.name)
                    full_context_term_code_cql_mapping_name_mapping.update(context_tc_to_mapping_name)
                    full_cql_mapping_name_cql_mapping.update(cql_mapping_name_to_mapping)
        return (full_context_term_code_cql_mapping_name_mapping,
                full_cql_mapping_name_cql_mapping)

    def generate_normalized_term_code_cql_mapping(self, profile_snapshot, module_name: TermCode) \
            -> Tuple[Dict[Tuple[TermCode, TermCode], str], Dict[str, CQLMapping]]:
        """
        Generates the normalized term code to CQL mapping for the given FHIR profile snapshot
        :param profile_snapshot: FHIR profile snapshot
        :param module_name: name of the module the profile belongs to
        :return: normalized term code to CQL mapping
        """
        querying_meta_data: List[ResourceQueryingMetaData] = \
            self.querying_meta_data_resolver.get_query_meta_data(profile_snapshot, module_name)
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
            primary_keys = [(querying_meta_data_entry.context, term_code) for term_code in term_codes]
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
        cql_mapping.resourceType = querying_meta_data.resource_type
        if tc_defining_id := querying_meta_data.term_code_defining_id:
            cql_mapping.termCodeFhirPath = self.translate_term_element_id_to_fhir_path_expression(
                tc_defining_id, profile_snapshot)
        if val_defining_id := querying_meta_data.value_defining_id:
            cql_mapping.valueFhirPath = self.translate_element_id_to_fhir_path_expressions(
                val_defining_id, profile_snapshot)
            cql_mapping.valueType = self.get_attribute_type(profile_snapshot, val_defining_id)
        if time_defining_id := querying_meta_data.time_restriction_defining_id:
            cql_mapping.timeRestrictionFhirPath = self.translate_element_id_to_fhir_path_expressions(
                time_defining_id, profile_snapshot)
        for attr_defining_id, attr_type in querying_meta_data.attribute_defining_id_type_map.items():
            attribute_key = generate_attribute_key(attr_defining_id)
            attribute_type = attr_type if attr_type else self.get_attribute_type(profile_snapshot,
                                                                                 attr_defining_id)
            # FIXME:
            # This is a hack to change the attribute_type to upper-case Reference to match the FHIR Type while
            # Fhir Search does not use the FHIR types...
            attribute_type = "Reference" if attr_type == "reference" else attribute_type
            attribute_fhir_path = self.translate_term_element_id_to_fhir_path_expression(attr_defining_id,
                                                                                         profile_snapshot)
            attribute = CQLAttributeSearchParameter(attribute_type, attribute_key, attribute_fhir_path)
            if attribute_type == "Reference":
                attribute.attributeReferenceTargetType = self.get_reference_type(profile_snapshot, attr_defining_id)
            cql_mapping.add_attribute(attribute)

        return cql_mapping

    def translate_term_element_id_to_fhir_path_expression(self, element_id, profile_snapshot) -> str:
        elements = self.parser.get_element_defining_elements(element_id, profile_snapshot, self.module_dir,
                                                             self.data_set_dir)
        # TODO: Revisit and evaluate if this really the way to go.
        for element in elements:
            for element_type in element.get("type"):
                if element_type.get("code") == "Reference":
                    return self.get_cql_optimized_path_expression(
                        self.parser.translate_element_to_fhir_path_expression(elements, profile_snapshot)[
                            0]) + ".reference"
        return self.translate_element_id_to_fhir_path_expressions(element_id, profile_snapshot)

    def translate_element_id_to_fhir_path_expressions(self, element_id, profile_snapshot: dict) -> str:
        """
        Translates an element id to a fhir search parameter
        :param element_id: element id
        :param profile_snapshot: FHIR profile snapshot containing the element id
        :return: fhir search parameter
        """
        elements = self.parser.get_element_defining_elements(element_id, profile_snapshot, self.module_dir,
                                                             self.data_set_dir)
        expressions = self.parser.translate_element_to_fhir_path_expression(elements, profile_snapshot)
        return ".".join([self.get_cql_optimized_path_expression(expression) for expression in expressions])

    def get_cql_optimized_path_expression(self, path_expression: str) -> str:
        # TODO: Remove this method once the new path expressions are compatible with the cql implementation?
        """
        Translates a path expression to a cql optimized path expression
        :param path_expression: path expression
        :return: cql optimized path expression
        """
        cql_path_expression = self.convert_as_to_dot_as(path_expression)
        cql_path_expression = self.add_first_after_extension_where_expression(cql_path_expression)
        return cql_path_expression

    @staticmethod
    def convert_as_to_dot_as(path_expression: str) -> str:
        """
        Converts the " as " pattern to ".as("
        :param path_expression: path expression
        :return: converted path expression
        """
        # Discard everything before the first dot
        _, _, path_after_dot = path_expression.partition('.')

        # If there's no content after the first dot, return the original path_expression
        if not path_after_dot:
            return path_expression

        # Partition based on " as " to handle conversion
        before_as, _, remainder = path_after_dot.partition(" as ")

        # If there's no " as " pattern, just return the path after the first dot
        if not remainder:
            return path_after_dot

        after_as, _, rest = remainder.partition('.')
        transformed = f"{before_as}.as({after_as})"

        # Append the rest of the path if there's more after "as "
        if rest:
            transformed += f".{rest}"
        return transformed

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

    def get_reference_type(self, profile_snapshot: dict, attr_defining_id):
        """
        Returns the type of the given attribute
        :param profile_snapshot: FHIR profile snapshot
        :param attr_defining_id: attribute id
        :return: attribute type
        """
        elements = self.parser.get_element_defining_elements(attr_defining_id, profile_snapshot, self.module_dir,
                                                             self.data_set_dir)
        for element in elements:
            for element_type in element.get("type"):
                if element_type.get("code") == "Reference":
                    return extract_reference_type(element_type, self.data_set_dir, profile_snapshot.get('name'))

    @staticmethod
    def add_first_after_extension_where_expression(cql_path_expression):
        """
        Adds the first() after an extension where expression
        :param cql_path_expression: cql path expression
        :return: cql path expression with first() added
        """
        # TODO: Find a better rule than contains extension.where(...) to apply the first() rule
        # Use regex to find the pattern "extension.where(...)"
        match = re.search(r'(extension\.where\([^)]+\))(.+)', cql_path_expression)

        if match:
            before_extension = match.group(1)
            after_extension = match.group(2)
            return f"{before_extension}.first(){after_extension}"

        # If no match is found, return the original string
        return cql_path_expression
