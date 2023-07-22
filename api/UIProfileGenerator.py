from __future__ import annotations

import json
import os
from typing import Dict, Tuple, List

from api import ResourceQueryingMetaDataResolver
from api import StrucutureDefinitionParser as FHIRParser
from api.StrucutureDefinitionParser import InvalidValueTypeException, UCUM_SYSTEM
from helper import generate_attribute_key
from model.ResourceQueryingMetaData import ResourceQueryingMetaData
from model.UIProfileModel import ValueDefinition, UIProfile, AttributeDefinition
from model.UiDataModel import TermCode

AGE_UNIT_VALUE_SET = "http://hl7.org/fhir/ValueSet/age-units"


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
            # The logic to get the term_codes here always has to be identical with the mapping Generators!
            term_codes = querying_meta_data_entry.term_codes if querying_meta_data_entry.term_codes else \
                self.parser.get_term_code_by_id(profile_snapshot, querying_meta_data_entry.term_code_defining_id,
                                                self.data_set_dir, self.module_dir)
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
        ui_profile.time_restriction_allowed = self.is_time_restriction_allowed(querying_meta_data)
        if querying_meta_data.value_defining_id:
            ui_profile.value_definition = self.get_value_definition(profile_snapshot,
                                                                    querying_meta_data)
        ui_profile.attribute_definitions = self.get_attribute_definitions(profile_snapshot, querying_meta_data)
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
        value_type = querying_meta_data.value_type if querying_meta_data.value_type else \
            self.parser.extract_value_type(value_defining_element, profile_snapshot.get("name"))
        value_definition = ValueDefinition(value_type)
        if value_type == "concept":
            value_definition.selectableConcepts = self.parser.get_selectable_concepts(value_defining_element,
                                                                                      profile_snapshot.get("name"))
        elif value_type == "quantity":
            # "Observation.valueQuantity" -> "Observation.valueQuantity.code"
            unit_defining_path = value_defining_element.get("path") + ".code"
            unit_defining_elements = self.parser.get_element_from_snapshot_by_path(profile_snapshot, unit_defining_path)
            if len(unit_defining_elements) > 1:
                raise Exception(f"More than one element found for path {unit_defining_path}")
            value_definition.allowedUnits = self.parser.get_units(unit_defining_elements[0],
                                                                  profile_snapshot.get("name"))
        elif value_type == "Age":
            value_definition.type = "quantity"
            # TODO: This could be the better option once the ValueSet is available, but then we might want to limit the
            #  allowed units for security reasons
            # value_definition.allowedUnits = get_termcodes_from_onto_server(AGE_UNIT_VALUE_SET)
            value_definition.allowedUnits = [TermCode(UCUM_SYSTEM, "a", "a"), TermCode(UCUM_SYSTEM, "mo", "mo"),
                                             TermCode(UCUM_SYSTEM, "wk", "wk"), TermCode(UCUM_SYSTEM, "d", "d")]
        elif value_type == "integer":
            value_definition.type = "quantity"
        elif value_type == "calculated":
            pass
        elif value_type == "reference":
            raise InvalidValueTypeException("Reference type need to be resolved using the Resolve().elementid syntax")
        else:
            raise InvalidValueTypeException(
                f"Invalid value type: {value_type} in profile {profile_snapshot.get('name')}")
        return value_definition

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
        attribute_code = generate_attribute_key(attribute_defining_element_id)
        attribute_definition = AttributeDefinition(attribute_code, attribute_type)
        if attribute_type == "concept":
            attribute_definition.selectableConcepts = self.parser.get_selectable_concepts(
                attribute_defining_elements[-1],
                profile_snapshot.get("name"))
        elif attribute_type == "quantity":
            unit_defining_path = attribute_defining_elements[-1].get("path") + ".code"
            unit_defining_elements = self.parser.get_element_from_snapshot_by_path(profile_snapshot, unit_defining_path)
            if len(unit_defining_elements) > 1:
                raise Exception(f"More than one element found for path {unit_defining_path}")
            attribute_definition.allowedUnits = self.parser.get_units(unit_defining_elements[0],
                                                                      profile_snapshot.get("name"))
        elif attribute_type == "reference":
            raise InvalidValueTypeException("Reference type need to be resolved using the Resolve().elementid syntax")
            # attribute_definition = self.generate_reference_attribute_definition(profile_snapshot,
            #                                                                     attribute_defining_element_id)
        elif attribute_type == "composed":
            attribute_definition = self.generate_composed_attribute(profile_snapshot,
                                                                    attribute_defining_element_id)
        else:
            raise InvalidValueTypeException("Invalid value type: " + attribute_type)
        return attribute_definition

    def generate_composed_attribute(self, profile_snapshot, attribute_defining_element_id) -> AttributeDefinition:
        attribute_defining_elements = self.parser.get_element_defining_elements(attribute_defining_element_id,
                                                                                profile_snapshot, self.module_dir,
                                                                                self.data_set_dir)
        element = self.parser.get_element_from_snapshot(profile_snapshot, attribute_defining_element_id)
        attribute_code = self.generate_composed_attribute_code(profile_snapshot, attribute_defining_element_id)
        attribute_definition = AttributeDefinition(attribute_code, "composed")
        attribute_type = self.parser.get_element_type(element)
        if attribute_type == "Quantity":
            unit_defining_path = attribute_defining_elements[-1].get("path") + ".code"
            unit_defining_elements = self.parser.get_element_from_snapshot_by_path(profile_snapshot, unit_defining_path)
            if len(unit_defining_elements) > 1:
                unit_defining_elements = list(filter(lambda x: self.get_slice_name(x) == self.get_slice_name(element),
                                                     unit_defining_elements))
                if len(unit_defining_elements) > 1:
                    raise Exception(f"More than one element found for path {unit_defining_path}")
            attribute_definition.allowedUnits = self.parser.get_units(unit_defining_elements[0],
                                                                      profile_snapshot.get("name"))
            return attribute_definition
        elif attribute_type == "CodeableConcept":
            attribute_definition.selectableConcepts = self.parser.get_selectable_concepts(
                attribute_defining_elements[-1],
                profile_snapshot.get("name"))
            return attribute_definition
        else:
            raise InvalidValueTypeException("Invalid value type: " + attribute_type + " for composed attribute " +
                                            attribute_defining_element_id +
                                            " in profile " + profile_snapshot.get("name"))

    @staticmethod
    def get_slice_name(element):
        if element.get("sliceName"):
            return element.get("sliceName")
        elif ':' in element.get("id"):
            return element.get("id").split(":")[1].split(".")[0]
        else:
            return ""

    def generate_composed_attribute_code(self, profile_snapshot, attribute_defining_element_id) -> TermCode:
        element = self.parser.get_element_from_snapshot(profile_snapshot, attribute_defining_element_id)
        element_path = element.get("path")
        if "component" in element_path:
            element_path = element_path.split(".component")[0] + ".component.code.coding"
            code_elements = self.parser.get_element_from_snapshot_by_path(profile_snapshot, element_path)
            for code_element in code_elements:
                if code_element.get("min") == 1 and "patternCoding" in code_element:
                    return self.parser.pattern_coding_to_term_code(code_element)
        else:
            raise InvalidValueTypeException(
                "Unable to generate composed attribute code for element: " + element_path +
                "in profile: " + profile_snapshot.get("name"))

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

    def generate_reference_attribute_definition(self, profile_snapshot, attribute_defining_element_id):
        pass
