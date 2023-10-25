import functools
import json
import os
from typing import Dict, Tuple, List, OrderedDict

from core.ResourceQueryingMetaDataResolver import ResourceQueryingMetaDataResolver
from core import StrucutureDefinitionParser as FHIRParser
from core.SearchParameterResolver import SearchParameterResolver
from core.StrucutureDefinitionParser import extract_value_type, resolve_defining_id, FHIR_TYPES_TO_VALUE_TYPES
from helper import generate_attribute_key
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

    def __init__(self, querying_meta_data_resolver: ResourceQueryingMetaDataResolver,
                 fhir_search_mapping_resolver: SearchParameterResolver,
                 parser=FHIRParser):
        """
        :param querying_meta_data_resolver: resolves the for the query relevant meta data for a given FHIR profile
        snapshot
        """
        self.querying_meta_data_resolver = querying_meta_data_resolver
        self.generated_mappings = []
        self.parser = parser
        self.data_set_dir: str = ""
        self.module_dir: str = ""
        self.fhir_search_mapping_resolver = fhir_search_mapping_resolver

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
                    context_tc_to_mapping_name, fhir_search_mapping_name_to_mapping = \
                        self.generate_normalized_term_code_fhir_search_mapping(snapshot, module_dir.name)
                    full_context_term_code_fhir_search_mapping_name_mapping.update(context_tc_to_mapping_name)
                    full_fhir_search_mapping_name_fhir_search_mapping.update(fhir_search_mapping_name_to_mapping)
        return (full_context_term_code_fhir_search_mapping_name_mapping,
                full_fhir_search_mapping_name_fhir_search_mapping)

    def resolve_fhir_search_parameter(self, element_id: str, profile_snapshot: dict,
                                      attribute_type: VALUE_TYPE_OPTIONS = None) -> OrderedDict[str, dict]:
        """
        Based on the element id, this method resolves the FHIR search parameter for the given FHIR Resource attribute
        :param element_id: element id that defines the of the FHIR Resource attribute
        :param profile_snapshot: FHIR profile snapshot that contains the element id
        :param attribute_type: type of the FHIR Resource attribute
        :return: FHIR search parameter
        """
        fhir_path_expressions = self.translate_element_id_to_fhir_path_expressions(element_id, profile_snapshot)
        search_parameters = self.fhir_search_mapping_resolver.find_search_parameter(fhir_path_expressions)
        return search_parameters

    def chain_search_parameters(self, search_parameters: OrderedDict[str, dict]) -> str:
        self.validate_chainable(search_parameters.values())
        return ".".join([search_parameter.get("code") for search_parameter in search_parameters.values()])

    def generate_normalized_term_code_fhir_search_mapping(self, profile_snapshot: dict, module_name: str) \
            -> Tuple[Dict[Tuple[TermCode, TermCode], str], Dict[str, FhirMapping]]:
        """
        Generates the normalized term code FHIR search mapping for the given FHIR profile snapshot in the specified
        context
        :param profile_snapshot: FHIR profile snapshot
        :param module_name: name of the module the profile belongs to
        :return: normalized term code FHIR search mapping
        """
        querying_meta_data: List[ResourceQueryingMetaData] = \
            self.querying_meta_data_resolver.get_query_meta_data(profile_snapshot, module_name)
        term_code_mapping_name_mapping = {}
        mapping_name_fhir_search_mapping = {}
        for querying_meta_data_entry in querying_meta_data:
            if querying_meta_data_entry.name not in self.generated_mappings:
                fhir_mapping = self.generate_fhir_search_mapping(profile_snapshot, querying_meta_data_entry)
                self.generated_mappings.append(querying_meta_data_entry.name)
                mapping_name = fhir_mapping.name
                mapping_name_fhir_search_mapping[mapping_name] = fhir_mapping
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
        return term_code_mapping_name_mapping, mapping_name_fhir_search_mapping

    def generate_fhir_search_mapping(self, profile_snapshot: dict, querying_meta_data: ResourceQueryingMetaData) \
            -> FhirMapping:
        """
        Generates the FHIR search mapping for the given FHIR profile snapshot and querying meta data
        :param profile_snapshot: FHIR profile snapshot
        :param querying_meta_data: querying meta data
        :return: FHIR search mapping
        """
        fhir_mapping = FhirMapping(querying_meta_data.name)
        fhir_mapping.fhirResourceType = querying_meta_data.resource_type
        if querying_meta_data.term_code_defining_id:
            self.set_term_code_search_param(fhir_mapping, profile_snapshot, querying_meta_data)
        if querying_meta_data.value_defining_id:
            self.set_value_search_param(fhir_mapping, profile_snapshot, querying_meta_data)
        if querying_meta_data.time_restriction_defining_id:
            fhir_mapping.timeRestrictionParameter = self._handle_search_parameter("date",
                                                                                  self.resolve_fhir_search_parameter(
                                                                                      querying_meta_data.time_restriction_defining_id,
                                                                                      profile_snapshot, "date"))
        for attribute, predefined_type in querying_meta_data.attribute_defining_id_type_map.items():
            self.set_attribute_search_param(attribute, fhir_mapping, predefined_type, profile_snapshot)
        return fhir_mapping

    def _handle_search_parameter(self, param_type, search_params):
        """
        Handle search parameters based on its type.

        Args:
            param_type (str): Type of the parameter ("reference" or other types).
            search_params (dict): Resolved search parameters.

        Returns:
            str: The code of the search parameter if type is "reference", or the chained search parameters otherwise.
        """
        if param_type == "reference":
            return list(search_params.values())[0].get("code")
        else:
            return self.chain_search_parameters(search_params)

    @staticmethod
    def get_updated_attribute_type(attribute_type, attribute_search_params):
        """
        Update the attribute type based on the search parameters.

        Args:
            attribute_type (str): The original attribute type.
            attribute_search_params (dict): Resolved search parameters.
        """
        if list(attribute_search_params.values())[-1].get("type") == "composite":
            if attribute_type == "quantity" or attribute_type == "concept":
                attribute_type = "composite-" + attribute_type
            else:
                raise ValueError("Attribute type {} is not supported for composite search parameter".format(
                    attribute_type))
        return attribute_type

    def set_attribute_search_param(self, attribute, fhir_mapping, predefined_type, profile_snapshot):
        attribute_key = generate_attribute_key(attribute)
        attribute_type = predefined_type if predefined_type else self.get_attribute_type(profile_snapshot,
                                                                                         attribute)
        attribute_search_params = self.resolve_fhir_search_parameter(attribute, profile_snapshot,
                                                                     attribute_type)
        attribute_type = self.get_updated_attribute_type(attribute_type, attribute_search_params)
        fhir_mapping.add_attribute(attribute_type, attribute_key,
                                   self._handle_search_parameter(attribute_type, attribute_search_params))

    def set_value_search_param(self, fhir_mapping, profile_snapshot, querying_meta_data):
        value_type = querying_meta_data.value_type if querying_meta_data.value_type else \
            self.get_attribute_type(profile_snapshot, querying_meta_data.value_defining_id)
        fhir_mapping.valueType = value_type
        value_search_params = self.resolve_fhir_search_parameter(
            querying_meta_data.value_defining_id, profile_snapshot, value_type)
        fhir_mapping.valueSearchParameter = self._handle_search_parameter(value_type, value_search_params)

    def set_term_code_search_param(self, fhir_mapping, profile_snapshot, querying_meta_data):
        term_code_search_params = self.resolve_fhir_search_parameter(
            querying_meta_data.term_code_defining_id, profile_snapshot, "concept")
        search_param_str = self.chain_search_parameters(term_code_search_params)
        fhir_mapping.termCodeSearchParameter = search_param_str

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
        return FHIR_TYPES_TO_VALUE_TYPES.get(extract_value_type(attribute_element, profile_snapshot.get('name'))) \
            if extract_value_type(attribute_element,
                                  profile_snapshot.get('name')) in FHIR_TYPES_TO_VALUE_TYPES else extract_value_type(
            attribute_element, profile_snapshot.get('name'))

    def translate_element_id_to_fhir_path_expressions(self, element_id, profile_snapshot: dict) -> List[str]:
        """
        Translates an element id to a fhir search parameter
        :param element_id: element id
        :param profile_snapshot: FHIR profile snapshot containing the element id
        :return: fhir search parameter
        """
        elements = self.parser.get_element_defining_elements(element_id, profile_snapshot, self.module_dir,
                                                             self.data_set_dir)
        return self.parser.translate_element_to_fhir_path_expression(elements, profile_snapshot)

    @staticmethod
    def validate_chainable(chainable_search_parameter) -> bool:
        """
        Validates the chaining of search parameters
        :param chainable_search_parameter: the search parameter to be chained
        :return: true if the search parameter can be chained else false
        """
        if not chainable_search_parameter:
            raise ValueError("No search parameters to chain")
        elif len(chainable_search_parameter) == 1:
            return True
        return functools.reduce(
            lambda x, y: True if x and len(set(y.get("base", [])).intersection(x.get("target", []))) != 0 else False,
            chainable_search_parameter)
