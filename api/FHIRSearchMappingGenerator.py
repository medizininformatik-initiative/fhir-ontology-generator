import json
import os
import re
from typing import Dict, Tuple, List

from TerminologService.ValueSetResolver import get_term_codes_by_id
from api.ResourceQueryingMetaDataResolver import ResourceQueryingMetaDataResolver
from api import StrucutureDefinitionParser as FHIRParser
from api.StrucutureDefinitionParser import extract_value_type, resolve_defining_id
from helper import find_search_parameter
from model.MappingDataModel import FhirMapping
from model.ResourceQueryingMetaData import ResourceQueryingMetaData
from model.UIProfileModel import VALUE_TYPE_OPTIONS
from model.UiDataModel import TermCode

SUPPORTED_TYPES = ['date', 'dateTime', 'decimal', 'integer', 'Age', 'CodeableConcept', 'Coding', 'Quantity',
                   'Reference', 'code', 'Extension']


class InvalidElementTypeException(Exception):
    pass


class FHIRSearchMappingGenerator(object):
    """
    This class is responsible for generating FHIR mappings for a given FHIR profile.
    """

    def __init__(self, querying_meta_data_resolver: ResourceQueryingMetaDataResolver, parser=FHIRParser):
        """
        :param querying_meta_data_resolver: resolves the for the query relevant meta data for a given FHIR profile
        snapshot
        """
        self.querying_meta_data_resolver = querying_meta_data_resolver
        self.parser = parser
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
    def resolve_fhir_search_parameter(element_id: str, resource_type: str, attribute_type: VALUE_TYPE_OPTIONS) -> str:
        """
        Based on the element id, this method resolves the FHIR search parameter for the given FHIR Resource attribute
        :param element_id: element id that defines the of the FHIR Resource attribute
        :param resource_type: FHIR Resource type
        :param attribute_type: type of the FHIR Resource attribute
        :return: FHIR search parameter
        """
        element_id = element_id[:element_id.rfind(":") + 1]
        return find_search_parameter(element_id, resource_type, attribute_type)

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
        querying_meta_data: List[ResourceQueryingMetaData] = \
            self.querying_meta_data_resolver.get_query_meta_data(profile_snapshot, context)
        term_code_mapping_name_mapping = {}
        mapping_name_fhir_search_mapping = {}
        for querying_meta_data_entry in querying_meta_data:
            fhir_mapping = self.generate_fhir_search_mapping(profile_snapshot, querying_meta_data_entry)
            term_codes = get_term_codes_by_id(querying_meta_data_entry.term_code_defining_id, profile_snapshot)
            mapping_name = fhir_mapping.name
            primary_keys = [(context, term_code) for term_code in term_codes]
            mapping_names = [mapping_name] * len(primary_keys)
            table = dict(zip(primary_keys, mapping_names))
            term_code_mapping_name_mapping.update(table)
            mapping_name_fhir_search_mapping[mapping_name] = fhir_mapping
        return term_code_mapping_name_mapping, mapping_name_fhir_search_mapping

    def generate_fhir_search_mapping(self, profile_snapshot: dict, querying_meta_data: ResourceQueryingMetaData) \
            -> FhirMapping:
        """
        Generates the FHIR search mapping for the given FHIR profile snapshot in the specified context
        :param profile_snapshot: FHIR profile snapshot
        :param querying_meta_data: querying meta data
        :return: FHIR search mapping
        """
        fhir_mapping = FhirMapping(querying_meta_data.name)
        fhir_mapping.resource_type = querying_meta_data.resource_type
        if querying_meta_data.term_code_defining_id:
            fhir_mapping.termCodeSearchParameter = self.resolve_fhir_search_parameter(
                querying_meta_data.term_code_defining_id, fhir_mapping.resource_type, "concept")
        if querying_meta_data.value_defining_id:
            value_type = querying_meta_data.value_type if querying_meta_data.value_type else \
                self.get_attribute_type(profile_snapshot, querying_meta_data.value_defining_id)
            fhir_mapping.valueType = value_type
            fhir_mapping.valueSearchParameter = self.resolve_fhir_search_parameter(
                querying_meta_data.value_defining_id, fhir_mapping.resource_type, value_type)
        if querying_meta_data.time_restriction_defining_id:
            fhir_mapping.timeRestrictionParameter = self.resolve_fhir_search_parameter(
                querying_meta_data.time_restriction_defining_id, fhir_mapping.resource_type, "date")
        for attribute, predefined_type in querying_meta_data.attribute_defining_id_type_map.items():
            attribute_key = self.generate_attribute_key(attribute, querying_meta_data.context)
            attribute_type = predefined_type if predefined_type else self.get_attribute_type(profile_snapshot,
                                                                                             attribute)
            attribute_search_parameter = self.resolve_fhir_search_parameter(attribute, fhir_mapping.resource_type,
                                                                            attribute_type)
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
        if " as ValueSet" in attribute_id:
            attribute_id = attribute_id.replace(" as ValueSet", "")
        attribute_element = resolve_defining_id(profile_snapshot, attribute_id, self.data_set_dir, self.module_dir)
        print(attribute_element)
        return extract_value_type(attribute_element, profile_snapshot.get('name'))

    def translate_element_id_to_fhir_path_expressions(self, element_id, profile_snapshot: dict) -> List[str]:
        """
        Translates an element id to a fhir search parameter
        :param element_id: element id
        :param profile_snapshot: FHIR profile snapshot containing the element id
        :return: fhir search parameter
        """
        elements = self.parser.get_element_defining_elements(element_id, profile_snapshot, self.module_dir,
                                                             self.data_set_dir)
        return self.translate_element_to_fhir_path_expression(elements)

    def translate_element_to_fhir_path_expression(self, elements: List[dict]) -> List[str]:
        """
        Translates an element to a fhir search parameter. Be aware not every element is translated alone to a
        fhir path expression. I.E. Extensions elements are translated together with the prior element.
        :param elements: elements for which the fhir path expressions should be obtained
        :return: fhir path expressions
        """
        element = elements.pop(0)
        element_path = element.get("path")
        element_type = self.get_element_type(element)
        if element_type == "Extension":
            if element[0].get("type") != "Extension":
                raise Exception("translating an element that references an extension and is not followed by an "
                                "extension element is invalid")
            elements.pop(0)
            element_path = f"{element_path}.where(url='{self.get_extension_url(element)}').value"
        elif element_type == "Coding":
            if element_path.endswith(".coding"):
                return element_path.replace(".coding", "")
        if '[x]' in element_path:
            element_path = element_path.replace('[x]', f' as {element_type}')
        result = [element_path]
        if elements:
            result.extend(self.translate_element_to_fhir_path_expression(elements))
        return result

    @staticmethod
    def get_extension_url(element):
        extension_profiles = element.get('type')[0].get('profile')
        if len(extension_profiles) > 1:
            raise Exception("More than one extension found")
        if not extension_profiles:
            raise Exception("No extension profile url found in element: \n" + element)
        return extension_profiles[0]

    @staticmethod
    def get_element_type(element):
        """
        Returns the type of the given element
        :param element: element
        :return: type of the element
        """
        element_types = element.get("type")
        if len(element_types) == 2:
            types = [element_type.get("code") for element_type in element_types]
            if "dateTime" in types and "Period" in types:
                return "dateTime"
        elif len(element_types) > 1:
            raise Exception("Multiple types are currently not supported")
        elif not element_types:
            raise Exception("No type found for element " + element.get("id") + " in profile element \n" + element)
        return element_types[0].get("code")


if __name__ == '__main__':
    print(FHIRSearchMappingGenerator.resolve_fhir_search_parameter(
        "((Specimen.extension:festgestellteDiagnose as Reference).value[x] as Reference)"
        ".code.coding:icd10-gm as ValueSet",
        "Specimen", "concept"))
