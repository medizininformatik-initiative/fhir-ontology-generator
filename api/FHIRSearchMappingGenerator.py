import json
import os
import re
from typing import Dict, Tuple

from api.ResourceQueryingMetaDataResolver import ResourceQueryingMetaDataResolver
from api.StrucutureDefinitionParser import extract_value_type, resolve_defining_id
from helper import find_search_parameter
from model.MappingDataModel import FhirMapping
from model.ResourceQueryingMetaData import ResourceQueryingMetaData
from model.UIProfileModel import VALUE_TYPE_OPTIONS
from model.UiDataModel import TermCode


class FHIRSearchMappingGenerator(object):
    """
    This class is responsible for generating FHIR mappings for a given FHIR profile.
    """

    def __init__(self, querying_meta_data_resolver: ResourceQueryingMetaDataResolver):
        """
        :param querying_meta_data_resolver: resolves the for the query relevant meta data for a given FHIR profile
        snapshot
        """
        self.querying_meta_data_resolver = querying_meta_data_resolver
        self.data_set_dir: str = ""
        self.module_dir: str = ""

    def generate_mapping(self, fhir_dataset_dir: str) \
            -> Tuple[Dict[Tuple[TermCode, TermCode], str], Dict[str, FhirMapping]]:
        """
        Generates the FHIR search mappings for the given FHIR dataset directory
        :param fhir_dataset_dir: FHIR dataset directory
        :return: normalized term code FHIR search mapping
        """
        self.data_set_dir = fhir_dataset_dir
        full_context_term_code_fhir_search_mapping_name_mapping: Dict[Tuple[TermCode, TermCode]] = {}
        full_fhir_search_mapping_name_fhir_search_mapping: Dict[str, FhirMapping] = {}
        for module_dir in [folder for folder in os.scandir(fhir_dataset_dir) if folder.is_dir()]:
            self.module_dir: str = module_dir.path
            files = [file.path for file in os.scandir(f"{fhir_dataset_dir}/{module_dir.name}/package") if file.is_file()
                     and file.name.endswith("snapshot.json")]
            for file in files:
                with open(file, "r", encoding="utf8") as f:
                    snapshot = json.load(f)
                    context = TermCode("fdpg.mii.cds", module_dir.name, module_dir.name)
                    context_tc_to_mapping_name, fhir_search_mapping_name_to_mapping = \
                        self.generate_normalized_term_code_fhir_search_mapping(snapshot, context)
                    full_context_term_code_fhir_search_mapping_name_mapping.update(context_tc_to_mapping_name)
                    full_fhir_search_mapping_name_fhir_search_mapping.update(fhir_search_mapping_name_to_mapping)
        return (full_context_term_code_fhir_search_mapping_name_mapping,
                full_fhir_search_mapping_name_fhir_search_mapping)

    @staticmethod
    def resolve_fhir_search_parameter(element_id) -> str:
        """
        Based on the element id, this method resolves the FHIR search parameter for the given FHIR Resource attribute
        :param element_id: element id that defines the of the FHIR Resource attribute
        :return: FHIR search parameter
        """
        # TODO: This has to consider and execute the resolve expressions
        if ":" in element_id:
            element_id = element_id.split(":")[0]
            return find_search_parameter(element_id)

    # TODO: Move to helper class
    @staticmethod
    def generate_attribute_key(element_id: str, context: TermCode) -> TermCode:
        """
        Generates the attribute key for the given element id
        :param element_id: element id
        :param context: context
        :return: attribute key
        """
        if '(' and ')' in element_id:
            element_id = element_id[element_id.rfind('(') + 1:element_id.find(')')]
        if ':' in element_id:
            element_id = element_id.split(':')[1]
            key = element_id[: re.search(r'\w+', element_id).start()]
        else:
            key = element_id.split('.')[:-1]
        return TermCode(context.system, key, key)

    def generate_normalized_term_code_fhir_search_mapping(self, profile_snapshot: dict, context: TermCode = None) \
            -> Tuple[Dict[Tuple[TermCode, TermCode], str], Dict[str, FhirMapping]]:
        """
        Generates the normalized term code FHIR search mapping for the given FHIR profile snapshot in the specified
        context
        :param profile_snapshot:
        :param context:
        :return: normalized term code FHIR search mapping
        """
        pass

    def generate_fhir_search_mapping(self, profile_snapshot: dict, querying_meta_data: ResourceQueryingMetaData) \
            -> FhirMapping:
        """
        Generates the FHIR search mapping for the given FHIR profile snapshot in the specified context
        :param profile_snapshot: FHIR profile snapshot
        :param querying_meta_data: querying meta data
        :return: FHIR search mapping
        """
        term_code_search_parameter = self.resolve_fhir_search_parameter(querying_meta_data.term_code_defining_id)
        fhir_mapping = FhirMapping(querying_meta_data.context.code, term_code_search_parameter)
        if querying_meta_data.value_defining_id:
            fhir_mapping.valueSearchParameter = self.resolve_fhir_search_parameter(
                querying_meta_data.value_defining_id)
            fhir_mapping.valueType = querying_meta_data.value_type if querying_meta_data.value_type else \
                self.get_attribute_type(profile_snapshot, querying_meta_data.value_defining_id)
        if querying_meta_data.time_restriction_defining_id:
            fhir_mapping.timeRestrictionParameter = self.resolve_fhir_search_parameter(
                querying_meta_data.time_restriction_defining_id)
        for attribute, predefined_type in querying_meta_data.attribute_defining_id_type_map.items():
            attribute_key = self.generate_attribute_key(attribute, querying_meta_data.context)
            attribute_search_parameter = self.resolve_fhir_search_parameter(attribute)
            attribute_type = predefined_type if predefined_type else self.get_attribute_type(profile_snapshot,
                                                                                             attribute)
            fhir_mapping.add_attribute(attribute_type, attribute_key, attribute_search_parameter)
        return fhir_mapping

    def get_attribute_type(self, profile_snapshot: dict, attribute_id: str) -> VALUE_TYPE_OPTIONS:
        """
        Returns the type of the given attribute
        :param profile_snapshot: FHIR profile snapshot
        :param attribute_id: attribute id
        :return: attribute type
        """
        # remove cast expression as it is irrelevant for the type
        if " as " in attribute_id:
            attribute_id = attribute_id.split(" as ")[0]
        attribute_element = resolve_defining_id(profile_snapshot, attribute_id, self.data_set_dir, self.module_dir)
        return extract_value_type(attribute_element, profile_snapshot.get('name'))
