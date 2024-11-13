from __future__ import annotations

import json
import os
import re
from typing import Tuple, List, Dict
from lxml import etree

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
        self.primary_paths = self.get_primary_paths_per_resource()
        self.generated_mappings = []
        self.parser = parser
        self.data_set_dir: str = ""
        self.module_dir: str = ""

    @staticmethod
    def get_primary_paths_per_resource() -> Dict[str, str]:
        primary_paths = {}
        with open("../../resources/cql/elm-modelinfo.xml", encoding="utf-8") as f:
            root = etree.parse(f)
            namespace_map = {'elm': 'urn:hl7-org:elm-modelinfo:r1'}
            for type_info in root.xpath('.//elm:typeInfo', namespaces=namespace_map):
                resource_type = type_info.get('name')
                primary_path = type_info.get('primaryCodePath')
                if resource_type and primary_path:
                    primary_paths[resource_type] = primary_path
        return primary_paths

    def resolve_fhir_path(self, element_id) -> str:
        """
        Based on the element id, this method resolves the FHIR path for the given FHIR Resource attribute
        :param element_id: element id that defines the of the FHIR Resource attribute
        :return: FHIR path
        """
        pass

    def generate_mapping(self, fhir_dataset_dir: str, module_name) \
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
            files = [file.path for file in os.scandir(f"{fhir_dataset_dir}/{module_dir.name}") if file.is_file()
                     and file.name.endswith("snapshot.json")]
            for file in files:
                with open(file, "r", encoding="utf8") as f:
                    snapshot = json.load(f)
                    context_tc_to_mapping_name, cql_mapping_name_to_mapping = \
                        self.generate_normalized_term_code_cql_mapping(snapshot, module_name)
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

    def is_primary_path(self, resource_type, fhir_path: str) -> bool:
        """
        Checks if the given fhir path is not a primary path according to the cql elm modelinfo
        :param resource_type: resource type
        :param fhir_path: fhir path
        :return: true if the given fhir path is not a primary path, false otherwise
        """
        if resource_type in self.primary_paths:
            return self.sub_path_equals(self.primary_paths[resource_type], fhir_path)
        return False

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
            term_code_fhir_path = self.translate_term_element_id_to_fhir_path_expression(
                tc_defining_id, profile_snapshot)
            if not self.is_primary_path(cql_mapping.resourceType, term_code_fhir_path):
                cql_mapping.termCodeFhirPath = term_code_fhir_path
        if val_defining_id := querying_meta_data.value_defining_id:
            cql_mapping.valueFhirPath = self.translate_element_id_to_fhir_path_expressions(
                val_defining_id, profile_snapshot)
            cql_mapping.valueType = self.get_attribute_type(profile_snapshot, val_defining_id)
        if time_defining_id := querying_meta_data.time_restriction_defining_id:
            cql_mapping.timeRestrictionFhirPath = self.translate_element_id_to_fhir_path_expressions_time_restriction(
                time_defining_id, profile_snapshot)
        for attr_defining_id, attr_attributes in querying_meta_data.attribute_defining_id_type_map.items():
            attr_type = attr_attributes.get("type", "")
            self.set_attribute_search_param(attr_defining_id, cql_mapping, attr_type, profile_snapshot)

        return cql_mapping

    def set_attribute_search_param(self, attr_defining_id, cql_mapping, attr_type, profile_snapshot):
        attribute_key = generate_attribute_key(attr_defining_id)
        attribute_type = attr_type if attr_type else self.get_attribute_type(profile_snapshot,
                                                                             attr_defining_id)
        # FIXME:
        # This is a hack to change the attribute_type to upper-case Reference to match the FHIR Type while
        # Fhir Search does not use the FHIR types...
        attribute_type = "Reference" if attr_type == "reference" else attribute_type
        if attribute_type == "composite":
            attribute_fhir_path = self.translate_composite_attribute_to_fhir_path_expression(
                attr_defining_id, profile_snapshot)
            attribute_key = self.get_composite_code(attr_defining_id, profile_snapshot)
            attribute_type = self.get_composite_attribute_type(attr_defining_id, profile_snapshot)
        else:
            attribute_fhir_path = self.translate_term_element_id_to_fhir_path_expression(attr_defining_id,
                                                                                         profile_snapshot)
        attribute = CQLAttributeSearchParameter(attribute_type, attribute_key, attribute_fhir_path)
        if attribute_type == "Reference":
            attribute.attributeReferenceTargetType = self.get_reference_type(profile_snapshot, attr_defining_id)

        cql_mapping.add_attribute(attribute)

    def get_composite_code(self, attribute, profile_snapshot):
        attribute_parsed = self.parser.get_element_defining_elements(attribute, profile_snapshot, self.module_dir,
                                                                     self.data_set_dir)
        if len(attribute_parsed) != 2:
            raise ValueError("Composite search parameters must have exactly two elements")
        where_clause_element = attribute_parsed[-1]
        return self.parser.get_fixed_term_codes(where_clause_element, profile_snapshot, self.data_set_dir,
                                                self.module_dir)[0]

    def get_composite_attribute_type(self, attribute, profile_snapshot):
        attribute_parsed = self.parser.get_element_defining_elements(attribute, profile_snapshot, self.module_dir,
                                                                     self.data_set_dir)
        if len(attribute_parsed) != 2:
            raise ValueError("Composite search parameters must have exactly two elements")
        value_element = attribute_parsed[0]
        return self.parser.get_element_type(value_element)

    @staticmethod
    def find_balanced_parentheses(s):
        stack = []
        start = 0
        for i, char in enumerate(s):
            if char == '(':
                if not stack:
                    start = i
                stack.append(char)
            elif char == ')':
                stack.pop()
                if not stack:
                    return s[start:i + 1]
        return ""

    def extract_where_clause(self, updated_attribute_path):
        where_clause_match = re.search(r"\.where\(", updated_attribute_path)
        if where_clause_match:
            remaining_string = updated_attribute_path[where_clause_match.end() - 1:]
            where_clause = self.find_balanced_parentheses(remaining_string)
            prefix = updated_attribute_path[:where_clause_match.end() - 1 + len(where_clause)]
            return where_clause, prefix
        else:
            return "", ""

    def translate_composite_attribute_to_fhir_path_expression(self, attribute, profile_snapshot):
        elements = self.parser.get_element_defining_elements(attribute, profile_snapshot, self.module_dir,
                                                             self.data_set_dir)
        expressions = self.parser.translate_element_to_fhir_path_expression(elements, profile_snapshot)
        value_clause = expressions[0]
        composite_code = self.get_composite_code(attribute, profile_snapshot)
        updated_where_clause = f".where(code.coding.exists(system = {composite_code.system} and code = {composite_code.code}))"
        # replace original where clause in attribute using string manipulation and regex
        updated_attribute_path = re.sub(r"\.where\([^\)]*\)", f"{updated_where_clause}", attribute)

        where_clause, prefix = self.extract_where_clause(updated_attribute_path)

        # Find the common prefix dynamically
        common_prefix_length = 0
        for i in range(min(len(updated_attribute_path), len(value_clause))):
            if updated_attribute_path[i] == value_clause[i]:
                common_prefix_length = i + 1
            else:
                break

        common_prefix = updated_attribute_path[:common_prefix_length]

        # Remove the common prefix from expr2 to get the uncommon part
        uncommon_expr2 = value_clause[len(common_prefix):]

        # Construct the new expression
        full_composite_path = prefix + "." + uncommon_expr2 if uncommon_expr2[0] != "." else prefix + uncommon_expr2
        return full_composite_path

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

    def translate_element_id_to_fhir_path_expressions_time_restriction(self, element_id, profile_snapshot: dict) -> str:
        """
        Translates an element id to a fhir search parameter
        :param element_id: element id
        :param profile_snapshot: FHIR profile snapshot containing the element id
        :return: fhir search parameter
        """
        elements = self.parser.get_element_defining_elements(element_id, profile_snapshot, self.module_dir,
                                                             self.data_set_dir)
        expressions = self.parser.translate_element_to_fhir_path_expression(elements, profile_snapshot)
        return ".".join([self.get_cql_path_time_restriction(expression) for expression in expressions])

    def get_cql_path_time_restriction(self, path_expression: str) -> str:
        cql_path_time_expression = self.remove_cast(path_expression)
        return cql_path_time_expression

    @staticmethod
    def remove_cast(path_expression: str) -> str:
        """
        Removes the cast from the path expression
        :param path_expression: path expression
        :return: path expression without cast
        """
        # Discard everything before the first dot
        _, _, path_after_dot = path_expression.partition('.')

        # If there's no content after the first dot, return the original path_expression
        if not path_after_dot:
            return path_expression
        return path_after_dot.split(" as ")[0]

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

        attribute_type = extract_value_type(attribute_element, profile_snapshot.get('name'))

        if attribute_type == "CodeableConcept":
            attribute_type = "Coding"

        return attribute_type

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

    @staticmethod
    def sub_path_equals(sub_path, path):
        """
        Checks if the given sub_path equals the given path or any truncated version of it.
        :param sub_path: sub path
        :param path: path
        :return: true if the given sub_path equals the given path or any truncated version, false otherwise
        """
        if sub_path == path:
            return True

        path_elements = path.split('.')
        # Iterate over the path elements from the end and check if the current truncated path matches the sub_path.
        for i in range(len(path_elements), 0, -1):
            current_path = '.'.join(path_elements[:i])
            if sub_path == current_path:
                return True
        return False


