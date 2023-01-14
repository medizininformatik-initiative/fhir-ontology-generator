from __future__ import annotations

import json
import os
from typing import Dict, Tuple, List

from TerminologService.ValueSetResolver import get_term_codes_by_id
from api import ResourceQueryingMetaDataResolver
from api import StrucutureDefinitionParser as FHIRParser
from api.StrucutureDefinitionParser import InvalidValueTypeException
from model.ResourceQueryingMetaData import ResourceQueryingMetaData
from model.UIProfileModel import ValueDefinition, UIProfile, AttributeDefinition
from model.UiDataModel import TermCode


class UIProfileGenerator:
    """
    This class is responsible for generating UI profiles for a given FHIR profile.
    """

    def __init__(self, querying_meta_data_resolver: ResourceQueryingMetaDataResolver, parser=FHIRParser):
        """
        :param querying_meta_data_resolver: resolves the for the query relevant meta data for a given FHIR profile
        :param parser: parser for the FHIR profile
        snapshot
        """
        self.querying_meta_data_resolver = querying_meta_data_resolver
        self.module_dir: str = ""
        self.data_set_dir: str = ""
        self.parser = parser

    def generate_ui_profiles(self, fhir_dataset_dir: str) -> \
            Tuple[Dict[Tuple[TermCode, TermCode], str], Dict[str, UIProfile]]:
        """
        Generates the ui trees for all FHIR profiles in the differential directory
        :param fhir_dataset_dir: root directory of the FHIR dataset containing the modules and their packages containing
        the FHIR Profiles and their snapshots of interest
        {FHIR_DATASET_DIR}/{MODULE_NAME}/package/
        :return: ui trees for all FHIR profiles in the differential directory
        """
        self.data_set_dir = fhir_dataset_dir
        full_context_term_code_ui_profile_name_mapping = {}
        full_ui_profile_name_ui_profile_mapping = {}
        for module_dir in [folder for folder in os.scandir(fhir_dataset_dir) if folder.is_dir()]:
            self.module_dir: str = module_dir.path
            files = [file.path for file in os.scandir(f"{fhir_dataset_dir}/{module_dir.name}/package") if file.is_file()
                     and file.name.endswith("snapshot.json")]
            for file in files:
                with open(file, "r", encoding="utf8") as f:
                    snapshot = json.load(f)
                    context = TermCode("fdpg.mii.cds", module_dir.name, module_dir.name)
                    context_tc_mapping, profile_name_profile_mapping = \
                        self.generate_normalized_term_code_ui_profile_mapping(snapshot, context)
                    full_context_term_code_ui_profile_name_mapping = {**full_context_term_code_ui_profile_name_mapping,
                                                                      **context_tc_mapping}
                    full_ui_profile_name_ui_profile_mapping = {**full_ui_profile_name_ui_profile_mapping,
                                                               **profile_name_profile_mapping}
        return full_context_term_code_ui_profile_name_mapping, full_ui_profile_name_ui_profile_mapping

    def generate_normalized_term_code_ui_profile_mapping(self, profile_snapshot: dict, context: TermCode = None) \
            -> Tuple[Dict[Tuple[TermCode, TermCode], str], Dict[str, UIProfile]]:
        """
        Generates a mapping from term codes to UI profiles
        :param context: context of the FHIR Profile
        :param profile_snapshot: FHIR profile snapshot
        :return: Tuple of the normalized tables to obtain the mapping from term code + context to UI profile
        {Table: Mapping from context + term code to UI profile name,
        Table: Mapping from UI profile name to the UI profile}
        """
        querying_meta_data: List[ResourceQueryingMetaData] = \
            self.querying_meta_data_resolver.get_query_meta_data(profile_snapshot, context)
        term_code_ui_profile_name_mapping = {}
        ui_profile_name_ui_profile_mapping = {}
        for i, querying_meta_data_entry in enumerate(querying_meta_data):
            ui_profile = self.generate_ui_profile(profile_snapshot, querying_meta_data_entry)
            term_codes = get_term_codes_by_id(querying_meta_data_entry.term_code_defining_id,
                                              profile_snapshot)
            ui_profile.name += str(i) if i > 0 else ""
            ui_profile_name = ui_profile.name
            primary_keys = [(context, term_code) for term_code in term_codes]
            ui_profile_names = [ui_profile_name] * len(primary_keys)
            table = dict(zip(primary_keys, ui_profile_names))
            term_code_ui_profile_name_mapping = {**term_code_ui_profile_name_mapping,
                                                 **table}
            ui_profile_name_ui_profile_mapping[ui_profile_name] = ui_profile
        return term_code_ui_profile_name_mapping, ui_profile_name_ui_profile_mapping

    def generate_ui_profile(self, profile_snapshot: dict, querying_meta_data) -> UIProfile:
        """
        Generates a UI profile for the given FHIR profile snapshot
        :param querying_meta_data: The querying meta data for the FHIR profile snapshot
        :param profile_snapshot: FHIR profile snapshot
        :return: UI profile for the given FHIR profile snapshot
        """
        ui_profile = UIProfile(profile_snapshot["name"])
        ui_profile.timeRestrictionAllowed = self.is_time_restriction_allowed(querying_meta_data)
        if querying_meta_data.value_defining_id:
            ui_profile.valueDefinitions = self.get_value_definition(profile_snapshot,
                                                                    querying_meta_data)
        ui_profile.attributeDefinitions = self.get_attribute_definitions(profile_snapshot, querying_meta_data)
        return ui_profile

    def get_value_definition(self, profile_snapshot, querying_meta_data) -> ValueDefinition:
        """
        Returns the value definition for the given FHIR profile snapshot at the value defining element id
        :param querying_meta_data: The querying meta data for the FHIR profile snapshot
        :param profile_snapshot: FHIR profile snapshot
        :return: value definition
        :raises InvalidValueTypeException: if the value type is not supported
        """
        value_defining_element = self.parser.resolve_defining_id(profile_snapshot, querying_meta_data.value_defining_id,
                                                                 self.data_set_dir, self.module_dir)
        print("value_defining_element", value_defining_element)
        value_type = querying_meta_data.value_type if querying_meta_data.value_type else \
            self.parser.extract_value_type(value_defining_element, profile_snapshot.get("name"))
        value_definition = ValueDefinition(value_type)
        if value_type == "concept":
            value_definition.selectableConcepts = self.parser.get_selectable_concepts(value_defining_element,
                                                                                      profile_snapshot.get("name"))
        elif value_type == "quantity":
            # "Observation.valueQuantity" -> "Observation.valueQuantity.code"
            unit_defining_element_id = querying_meta_data.value_defining_id + ".code"
            unit_defining_element = self.parser.get_element_from_snapshot(profile_snapshot, unit_defining_element_id)
            value_definition.allowedUnits = self.parser.get_units(unit_defining_element, profile_snapshot.get("name"))
        elif value_type == "calculated":
            pass
        elif value_type == "reference":
            raise InvalidValueTypeException("Reference type need to be resolved using the Resolve().elementid syntax")
        else:
            raise InvalidValueTypeException(
                f"Invalid value type: {value_type} in profile {profile_snapshot.get('name')}")
        return value_definition

    def generate_attribute_defining_code(self, profile_snapshot, attribute_defining_element_id) -> TermCode:
        pass

    def get_attribute_definitions(self, profile_snapshot, querying_meta_data) -> List[AttributeDefinition]:
        """
        Returns the attribute definitions for the given FHIR profile snapshot
        :param profile_snapshot:
        :param querying_meta_data:
        :return:
        """
        attribute_definitions = []
        for attribute_defining_id, attribute_type in querying_meta_data.attribute_defining_id_type_map.items():
            attribute_definition = self.get_attribute_definition(profile_snapshot, attribute_defining_id,
                                                                 attribute_type)
            attribute_definitions.append(attribute_definition)
        return attribute_definitions

    def get_attribute_definition(self, profile_snapshot: dict, attribute_defining_element_id: str,
                                 attribute_type: str) -> AttributeDefinition:
        """
        Returns an attribute definition for the given attribute defining element
        :param profile_snapshot: FHIR profile snapshot
        :param attribute_defining_element_id: id of the element that defines the attribute
        :param attribute_type: type of the attribute if set in querying meta data else it will be inferred from the
        FHIR profile snapshot
        :return: attribute definition
        """
        attribute_defining_elements = self.parser.get_element_defining_elements(attribute_defining_element_id,
                                                                                profile_snapshot, self.module_dir,
                                                                                self.data_set_dir)
        attribute_type = attribute_type if attribute_type else self.parser.extract_value_type(
            attribute_defining_elements[-1], profile_snapshot.get("name"))
        attribute_code = self.generate_attribute_defining_code(profile_snapshot, attribute_defining_element_id)
        attribute_definition = AttributeDefinition(attribute_code, attribute_type)
        if attribute_type == "concept":
            attribute_definition.selectableConcepts = self.parser.get_selectable_concepts(
                attribute_defining_elements[-1],
                profile_snapshot.get("name"))
        elif attribute_type == "quantity":
            # "Observation.valueQuantity.value" -> "Observation.valueQuantity.code"
            unit_defining_element_id = "".join(attribute_defining_element_id.split(".")[:-1] + ["code"])
            unit_defining_element = self.parser.get_element_from_snapshot(profile_snapshot, unit_defining_element_id)
            attribute_definition.allowedUnits = self.parser.get_units(unit_defining_element,
                                                                      profile_snapshot.get("name"))
        elif attribute_type == "reference":
            raise InvalidValueTypeException("Reference type need to be resolved using the Resolve().elementid syntax")
        else:
            raise InvalidValueTypeException("Invalid value type: " + attribute_type)
        return attribute_definition

    def get_referenced_profile_data(self, profile_snapshot, reference_defining_element_id) -> dict:
        """
        Returns the referenced profile data for the given FHIR profile snapshot at the reference defining element id
        :param profile_snapshot: FHIR profile snapshot
        :param reference_defining_element_id: element id that defines the reference
        :return: referenced FHIR profile
        """
        pass

    @staticmethod
    def is_time_restriction_allowed(querying_meta_data: ResourceQueryingMetaData) -> bool:
        """
        Returns whether time restrictions are allowed for the given FHIR profile snapshot
        :return: return true if a time restricting element is identified in the querying meta data
        """
        return querying_meta_data.time_restriction_defining_id is not None