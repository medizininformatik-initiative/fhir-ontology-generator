from __future__ import annotations

import os
from typing import Tuple, List, Dict

from cohort_selection_ontology.core.terminology.client import CohortSelectionTerminologyClient
from cohort_selection_ontology.core.resolvers.querying_metadata import ResourceQueryingMetaDataResolver
from common.model.structure_definition import StructureDefinitionSnapshot
from common.util.project import Project
from cohort_selection_ontology.model.mapping import PathlingMapping, PathlingAttributeSearchParameter
from cohort_selection_ontology.model.query_metadata import ResourceQueryingMetaData
from cohort_selection_ontology.model.ui_profile import VALUE_TYPE_OPTIONS
from cohort_selection_ontology.model.ui_data import TermCode
from common.util.structure_definition.functions import (
    extract_value_type,
    get_element_defining_elements,
    resolve_defining_id,
)


class PathlingMappingGenerator(object):
    def __init__(self, project: Project, querying_meta_data_resolver: ResourceQueryingMetaDataResolver):
        """
        :param querying_meta_data_resolver: resolves the for the query relevant metadata for a given FHIR profile
        snapshot
        :param project: Project instance the pathling mapping should be generated for
        """
        self.__project = project
        self.__client = CohortSelectionTerminologyClient(self.__project)
        self.querying_meta_data_resolver = querying_meta_data_resolver
        self.generated_mappings = []
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
            -> Tuple[Dict[Tuple[TermCode, TermCode], str], Dict[str, PathlingMapping]]:
        """
        Generates the FHIR search mappings for the given FHIR dataset directory
        :param fhir_dataset_dir: FHIR dataset directory
        :return: normalized term code FHIR search mapping
        """
        self.data_set_dir = fhir_dataset_dir
        full_context_term_code_pathling_mapping_name_mapping: Dict[Tuple[TermCode, TermCode]] | dict = {}
        full_pathling_mapping_name_pathling_mapping: Dict[str, PathlingMapping] | dict = {}
        for module_dir in [folder for folder in os.scandir(fhir_dataset_dir) if folder.is_dir()]:
            self.module_dir: str = module_dir.path
            files = [file.path for file in os.scandir(f"{fhir_dataset_dir}/{module_dir.name}/package") if file.is_file()
                     and file.name.endswith("snapshot.json")]
            for file in files:
                with open(file, "r", encoding="utf8") as f:
                    snapshot = StructureDefinitionSnapshot.model_validate_json(f.read())
                    context_tc_to_mapping_name, pathling_mapping_name_to_mapping = \
                        self.generate_normalized_term_code_pathling_mapping(snapshot, module_dir.name)
                    full_context_term_code_pathling_mapping_name_mapping.update(context_tc_to_mapping_name)
                    full_pathling_mapping_name_pathling_mapping.update(pathling_mapping_name_to_mapping)
        return (full_context_term_code_pathling_mapping_name_mapping,
                full_pathling_mapping_name_pathling_mapping)

    def generate_normalized_term_code_pathling_mapping(self, profile_snapshot: StructureDefinitionSnapshot, module_name: str) \
            -> Tuple[Dict[Tuple[TermCode, TermCode], str], Dict[str, PathlingMapping]]:
        """
        Generates the normalized term code to pathling mapping for the given FHIR profile snapshot
        :param profile_snapshot: FHIR profile snapshot
        :param module_name: Name of the module the profile belongs to
        :return: normalized Term code to pathling mapping
        """
        querying_meta_data: List[ResourceQueryingMetaData] = \
            self.querying_meta_data_resolver.get_query_meta_data(profile_snapshot, module_name)
        term_code_mapping_name_mapping: Dict[Tuple[TermCode, TermCode], str] | dict = {}
        mapping_name_pathling_mapping: Dict[str, PathlingMapping] | dict = {}
        for querying_meta_data_entry in querying_meta_data:
            if querying_meta_data_entry.name not in self.generated_mappings:
                pathling_mapping = self.generate_pathling_mapping(profile_snapshot, querying_meta_data_entry)
                self.generated_mappings.append(querying_meta_data_entry.name)
                mapping_name = pathling_mapping.name
                mapping_name_pathling_mapping[mapping_name] = pathling_mapping
            else:
                mapping_name = querying_meta_data_entry.name
            # The logic to get the term_codes here always has to be identical with the mapping
            term_codes = querying_meta_data_entry.term_codes if querying_meta_data_entry.term_codes else \
                profile_snapshot.get_term_code_by_id(querying_meta_data_entry.term_code_defining_id,
                                                self.data_set_dir, self.module_dir, self.__client)
            primary_keys = [(querying_meta_data_entry.context, term_code) for term_code in term_codes]
            mapping_names = [mapping_name] * len(primary_keys)
            table = dict(zip(primary_keys, mapping_names))
            term_code_mapping_name_mapping.update(table)
        return term_code_mapping_name_mapping, mapping_name_pathling_mapping

    def generate_pathling_mapping(self, profile_snapshot: StructureDefinitionSnapshot, querying_meta_data: ResourceQueryingMetaData) \
            -> PathlingMapping:
        """
        Generates the pathling mapping for the given FHIR profile snapshot and querying metadata entry
        :param profile_snapshot: FHIR profile snapshot
        :param querying_meta_data: querying metadata entry
        :return: pathling mapping
        """
        pathling_mapping = PathlingMapping(querying_meta_data.name)
        pathling_mapping.resourceType = querying_meta_data.resource_type
        if tc_defining_id := querying_meta_data.term_code_defining_id:
            pathling_mapping.termCodeFhirPath = self.translate_term_element_id_to_fhir_path_expression(
                tc_defining_id, profile_snapshot)
        if val_defining_id := querying_meta_data.value_defining_id:
            pathling_mapping.valueFhirPath = self.translate_element_id_to_fhir_path_expressions(
                val_defining_id, profile_snapshot)
            pathling_mapping.valueType = self.get_attribute_type(profile_snapshot, val_defining_id)
        if time_defining_id := querying_meta_data.time_restriction_defining_id:
            pathling_mapping.timeRestrictionFhirPath = self.translate_element_id_to_fhir_path_expressions(
                time_defining_id, profile_snapshot)
        for attr_defining_id, attr_attributes in querying_meta_data.attribute_defining_id_type_map.items():
            attr_type = attr_attributes.type
            attribute_key = profile_snapshot.generate_attribute_key(attr_defining_id)
            attribute_type = attr_type if attr_type else self.get_attribute_type(profile_snapshot,
                                                                                 attr_defining_id)
            # FIXME:
            # This is a hack to change the attribute_type to upper-case Reference to match the FHIR Type while
            # Fhir Search does not use the FHIR types...
            attribute_type = "Reference" if attr_type == "reference" else attribute_type
            attribute_fhir_path = self.translate_term_element_id_to_fhir_path_expression(attr_defining_id,
                                                                                         profile_snapshot)
            attribute = PathlingAttributeSearchParameter(types=attribute_type, key=attribute_key, attributePath=attribute_fhir_path)
            # if attribute_type == "Reference":
            #     attribute.attributeReferenceTargetType = self.get_reference_type(profile_snapshot, attr_defining_id)
            pathling_mapping.add_attribute(attribute)

        return pathling_mapping

    def translate_term_element_id_to_fhir_path_expression(self, element_id: str, profile_snapshot: StructureDefinitionSnapshot) -> str:
        elements = get_element_defining_elements(profile_snapshot, element_id,self.module_dir,self.data_set_dir)
        # TODO: Revisit and evaluate if this really the way to go.
        for element in elements:
            for element_type in element.type:
                if element_type.code == "Reference":
                    return (
                        self.get_pathling_optimized_path_expression(
                            profile_snapshot.translate_element_to_fhir_path_expression(
                                elements
                            )[0]
                        )
                        + ".reference"
                    )
        return self.translate_element_id_to_fhir_path_expressions(element_id, profile_snapshot)

    def translate_element_id_to_fhir_path_expressions(self, element_id: str, profile_snapshot: StructureDefinitionSnapshot) -> str:
        """
        Translates an element id to a fhir search parameter
        :param element_id: element id
        :param profile_snapshot: FHIR profile snapshot containing the element id
        :return: fhir search parameter
        """
        elements = get_element_defining_elements(profile_snapshot, element_id, self.module_dir,
                                                             self.data_set_dir)
        expressions = profile_snapshot.translate_element_to_fhir_path_expression(elements)
        return ".".join([self.get_pathling_optimized_path_expression(expression) for expression in expressions])

    def get_pathling_optimized_path_expression(self, path_expression: str) -> str:
        # TODO: Remove this method once the new path expressions are compatible with the pathling implementation?
        """
        Translates a path expression to a pathling optimized path expression
        :param path_expression: path expression
        :return: pathling optimized path expression
        """
        pathling_path_expression = self.convert_as_to_combined_name(path_expression)
        # pathling_path_expression = self.add_first_after_extension_where_expression(pathling_path_expression)
        return pathling_path_expression

    @staticmethod
    def convert_as_to_combined_name(path_expression: str) -> str:
        """
        Converts the "X as Y" pattern to "XY"
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
        transformed = f"{before_as}{after_as[0].upper()}{after_as[1:]}"

        # Append the rest of the path if there's more after "as "
        if rest:
            transformed += f".{rest}"
        return transformed

    def get_attribute_type(self, profile_snapshot: StructureDefinitionSnapshot, attribute_id: str) -> VALUE_TYPE_OPTIONS:
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
        return extract_value_type(attribute_element, profile_snapshot.name)

    # def get_reference_type(self, profile_snapshot: dict, attr_defining_id):
    #     """
    #     Returns the type of the given attribute
    #     :param profile_snapshot: FHIR profile snapshot
    #     :param attr_defining_id: attribute id
    #     :return: attribute type
    #     """
    #     elements = sd.get_element_defining_elements(attr_defining_id, profile_snapshot, self.module_dir,
    #                                                          self.data_set_dir)
    #     for element in elements:
    #         for element_type in element.get("type"):
    #             if element_type.get("code") == "Reference":
    #                 return extract_reference_type(element_type, self.data_set_dir, profile_snapshot.get('name'))

    # @staticmethod
    # def add_first_after_extension_where_expression(pathling_path_expression):
    #     """
    #     Adds the first() after an extension where expression
    #     :param pathling_path_expression: pathling path expression
    #     :return: pathling path expression with first() added
    #     """
    #     # TODO: Find a better rule than contains extension.where(...) to apply the first() rule
    #     # Use regex to find the pattern "extension.where(...)"
    #     match = re.search(r'(extension\.where\([^)]+\))(.+)', pathling_path_expression)
    #
    #     if match:
    #         before_extension = match.group(1)
    #         after_extension = match.group(2)
    #         return f"{before_extension}.first(){after_extension}"
    #
    #     # If no match is found, return the original string
    #     return pathling_path_expression
