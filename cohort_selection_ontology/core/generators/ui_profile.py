from __future__ import annotations

import json
import os
from typing import Dict, Tuple, List

from cohort_selection_ontology.core.terminology.client import CohortSelectionTerminologyClient
from cohort_selection_ontology.core.resolvers.querying_metadata import ResourceQueryingMetaDataResolver
from cohort_selection_ontology.util import structure_definition as sd
from cohort_selection_ontology.util.structure_definition import InvalidValueTypeException, UCUM_SYSTEM, \
    get_binding_value_set_url, \
    ProcessedElementResult, get_fixed_term_codes, FHIR_TYPES_TO_VALUE_TYPES, extract_value_type, get_common_ancestor
from helper import process_element_definition, get_display_from_element_definition
from cohort_selection_ontology.model.query_metadata import ResourceQueryingMetaData
from cohort_selection_ontology.model.ui_profile import ValueDefinition, UIProfile, AttributeDefinition, CriteriaSet
from cohort_selection_ontology.model.ui_data import TermCode
from common.util.log.functions import get_class_logger
from common.util.project import Project

AGE_UNIT_VALUE_SET = "http://hl7.org/fhir/ValueSet/age-units"


class UIProfileGenerator:
    """
    This class is responsible for generating UI profiles for a given FHIR profile.
    """
    __logger = get_class_logger("UIProfileGenerator")

    def __init__(self, project: Project, querying_meta_data_resolver: ResourceQueryingMetaDataResolver):
        """
        :param project: Project to operate on
        :param querying_meta_data_resolver: Resolver for retrieving the query metadata for a given FHIR profile snapshot
        """
        self.querying_meta_data_resolver = querying_meta_data_resolver
        self.module_dir: str = ""
        self.data_set_dir: str = ""
        self.__project = project
        self.__client = CohortSelectionTerminologyClient(self.__project)

    def generate_ui_profiles(self, module_name) -> \
            Tuple[Dict[Tuple[TermCode, TermCode], str], Dict[str, UIProfile]]:
        """
        Generates the ui trees for all FHIR profiles in the differential directory
        the FHIR Profiles and their snapshots of interest
        {FHIR_DATASET_DIR}/{MODULE_NAME}/
        :param module_name: Name of the module to generate UI profiles for
        :return: ui profiles for all FHIR profiles in the differential directory
        """
        modules_dir = self.__project.input("modules")
        full_context_term_code_ui_profile_name_mapping = {}
        full_ui_profile_name_ui_profile_mapping = {}
        for module_dir in [folder for folder in os.scandir(modules_dir) if folder.is_dir()]:
            self.module_dir: str = module_dir.path
            files = [file.path for file in os.scandir(os.path.join(modules_dir, module_dir.name)) if file.is_file()
                     and file.name.endswith("snapshot.json")]
            for file in files:
                with open(file, "r", encoding="utf8") as f:
                    snapshot = json.load(f)
                    context_tc_mapping, profile_name_profile_mapping = \
                        self.generate_normalized_term_code_ui_profile_mapping(snapshot, module_name)
                    full_context_term_code_ui_profile_name_mapping = {**full_context_term_code_ui_profile_name_mapping,
                                                                      **context_tc_mapping}
                    full_ui_profile_name_ui_profile_mapping = {**full_ui_profile_name_ui_profile_mapping,
                                                               **profile_name_profile_mapping}
        return full_context_term_code_ui_profile_name_mapping, full_ui_profile_name_ui_profile_mapping

    def generate_normalized_term_code_ui_profile_mapping(self, profile_snapshot: dict, module_name) \
            -> Tuple[Dict[Tuple[TermCode, TermCode], str], Dict[str, UIProfile]]:
        """
        Generates a mapping from term codes to UI profiles
        :param module_name: name of the module the profile belongs to
        :param profile_snapshot: FHIR profile snapshot
        :return: Tuple of the normalized tables to obtain the mapping from term code + context to UI profile
        {Table: Mapping from context + term code to UI profile name,
        Table: Mapping from UI profile name to the UI profile}
        """
        querying_meta_data: List[ResourceQueryingMetaData] = \
            self.querying_meta_data_resolver.get_query_meta_data(profile_snapshot, module_name)
        term_code_ui_profile_name_mapping = {}
        ui_profile_name_ui_profile_mapping = {}
        for i, querying_meta_data_entry in enumerate(querying_meta_data):
            ui_profile = self.generate_ui_profile(profile_snapshot, querying_meta_data_entry)
            # The logic to get the term_codes here always has to be identical with the mapping
            term_codes = querying_meta_data_entry.term_codes if querying_meta_data_entry.term_codes else \
                sd.get_term_code_by_id(profile_snapshot, querying_meta_data_entry.term_code_defining_id,
                                                self.data_set_dir, self.module_dir, self.__client)
            ui_profile.name += str(i) if i > 0 else ""
            ui_profile_name = ui_profile.name
            primary_keys = [(querying_meta_data_entry.context, term_code) for term_code in term_codes]
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
        self.__logger.info(f"Processing querying metadata '{querying_meta_data.name}'")
        ui_profile = UIProfile(profile_snapshot["name"])
        ui_profile.timeRestrictionAllowed = self.is_time_restriction_allowed(querying_meta_data)
        if querying_meta_data.value_defining_id:
            ui_profile.valueDefinition = self.get_value_definition(profile_snapshot,querying_meta_data)
        ui_profile.attributeDefinitions = self.get_attribute_definitions(profile_snapshot, querying_meta_data)
        return ui_profile

    @staticmethod
    def get_allowed_units_from_quantity(profile_snapshot: dict, value_defining_element: dict) -> List[TermCode]:
        """
        Get the units from 3 possible places in the following order:

        1. the standard way:
            * units are found under: "<path>.code"  \n
            example: FALL (Vitalstatus)
                * id: "Observation.value[x].coding:Vitalstatus"
                * path: "Observation.value[x].coding"

        2. Units in value[x].patternQuantity
            * units are located at: "Element(<id>).patternQuantity" \n
            example: ICU (Arterieller Blutdruck)
                * value_defining_element: "Observation.component:SystolicBP.value[x]"
                * units: "Element(Observation.component:SystolicBP.value[x]).patternQuantity"

        3. Units in value[x]:valueQuantity.patternQuantity
            * units are located at: "Element(<id>):valueQuantity.patternQuantity" \n
            example: ICU (Sauerstoffsättigung)
                * value_defining_element: "Observation.value[x]"
                * units: "Element(Observation.value[x]:valueQuantity).patternQuantity"

        :param profile_snapshot: profile snapshot
        :param value_defining_element: value defining element as set in the QueryingMetaData files
        :raise LookupError: if no units are found
        """

        unit_defining_path = value_defining_element.get("path") + ".code"
        unit_defining_elements = sd.get_element_from_snapshot_by_path(profile_snapshot, unit_defining_path)
        # get the units the standard way
        if len(unit_defining_elements) == 1:
            return sd.get_units(unit_defining_elements[0], profile_snapshot.get("name"))

        # get units from value[x].patternQuantity
        if pattern_quantity := value_defining_element.get("patternQuantity"):
            if pattern_quantity.get("code"):
                return [TermCode(pattern_quantity.get("system"), pattern_quantity.get("code"),
                                 pattern_quantity.get("unit"))]

        # get units from value[x]:valueQuantity.patternQuantity
        if value_quantity := sd.get_element_from_snapshot(profile_snapshot, (
                value_defining_element.get("path") + ":valueQuantity")):
            if pattern_quantity := value_quantity.get("patternQuantity"):
                if pattern_quantity.get("code"):
                    return [TermCode(pattern_quantity.get("system"), pattern_quantity.get("code"),
                                     pattern_quantity.get("unit"))]
        raise LookupError(f"Could not determine allowed units for {value_defining_element.get('path')} in {profile_snapshot.get('name')} ")


    def get_value_definition(self, profile_snapshot, querying_meta_data) -> ValueDefinition:
        """
        Returns the value definition for the given FHIR profile snapshot at the value defining element id
        :param querying_meta_data: The querying meta data for the FHIR profile snapshot
        :param profile_snapshot: FHIR profile snapshot
        :return: value definition
        :raises InvalidValueTypeException: if the value type is not supported
        """
        value_defining_element = sd.resolve_defining_id(profile_snapshot, querying_meta_data.value_defining_id,
                                                                 self.data_set_dir, self.module_dir)
        value_type = querying_meta_data.value_type if querying_meta_data.value_type else \
            FHIR_TYPES_TO_VALUE_TYPES.get(extract_value_type(value_defining_element, profile_snapshot.get('name'))) \
                if extract_value_type(value_defining_element,
                                      profile_snapshot.get(
                                          'name')) in FHIR_TYPES_TO_VALUE_TYPES else extract_value_type(
                value_defining_element, profile_snapshot.get('name'))
        # The only way the value_type equals "code" is if the query_meta_data sets it to "code". This might be necessary
        # for the mapping but the UI profile only supports "concept" so we have to convert it here.
        if value_type == "code":
            value_type = "concept"
        value_definition = ValueDefinition(value_type)
        value_definition.optional = querying_meta_data.value_optional
        if value_type == "concept":
            value_definition.referencedValueSet = sd.get_selectable_concepts(value_defining_element,
                                                                                      profile_snapshot.get("name"))
        elif value_type == "quantity":
            # "Observation.valueQuantity" -> "Observation.valueQuantity.code"
            # unit_defining_path = value_defining_element.get("path") + ".code"
            # unit_defining_elements = self.parser.get_element_from_snapshot_by_path(profile_snapshot, unit_defining_path)
            # if len(unit_defining_elements) > 1:
            #     raise Exception(f"More than one element found for path {unit_defining_path}")
            # value_definition.allowedUnits = self.parser.get_units(unit_defining_elements[0],profile_snapshot.get("name"))
            value_definition.allowedUnits = self.get_allowed_units_from_quantity(profile_snapshot, value_defining_element)

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

        display = process_element_definition(value_defining_element)[1]
        value_definition.display = display

        return value_definition

    def get_attribute_definitions(self, profile_snapshot, querying_meta_data) -> List[AttributeDefinition]:
        """
        Returns the attribute definitions for the given FHIR profile snapshot
        :param profile_snapshot:
        :param querying_meta_data:
        :return:
        """
        attribute_definitions = []
        for attribute_defining_id, attribute_attributes in querying_meta_data.attribute_defining_id_type_map.items():
            attribute_type = attribute_attributes.get("type", "")
            is_attribute_optional = attribute_attributes.get("optional", True)
            attribute_definition = self.get_attribute_definition(profile_snapshot, attribute_defining_id,
                                                                 attribute_type, is_attribute_optional)
            attribute_definitions.append(attribute_definition)
        return attribute_definitions

    def get_attribute_definition(self, profile_snapshot: dict, attribute_defining_element_id: str,
                                 attribute_type: str, optional: bool = True) -> AttributeDefinition:
        """
        Returns an attribute definition for the given attribute defining element
        :param profile_snapshot: FHIR profile snapshot
        :param attribute_defining_element_id: ID of the element that defines the attribute
        :param attribute_type: Type of the attribute if set in querying metadata else it will be inferred from the
        FHIR profile snapshot
        :param optional: Boolean indicating the optionality of the attribute definition
        :return: Attribute definition
        """
        attribute_defining_elements = sd.get_element_defining_elements(attribute_defining_element_id,
                                                                                profile_snapshot, self.module_dir,
                                                                                self.data_set_dir)
        attribute_defining_element = attribute_defining_elements[-1]

        attribute_type = attribute_type if attribute_type else FHIR_TYPES_TO_VALUE_TYPES.get(extract_value_type(
            attribute_defining_element, profile_snapshot.get('name'))) \
            if extract_value_type(attribute_defining_element,
                                  profile_snapshot.get('name')) in FHIR_TYPES_TO_VALUE_TYPES else extract_value_type(
            attribute_defining_element, profile_snapshot.get('name'))

        # TODO: attribute_defining_elements is a list of element but we only ever expect one in this instance (at least that is what the logic can handle)

        if len(attribute_defining_elements)>1:
            self.__logger.warning("more than one attribute definition element, only one supported, using last one instead")

        attribute_code, attribute_display = process_element_definition(attribute_defining_element)

        attribute_definition = AttributeDefinition(attribute_code, attribute_type, optional)
        attribute_definition.display = attribute_display
        if attribute_type == "concept":
            attribute_definition.referencedValueSet = sd.get_selectable_concepts(
                attribute_defining_element,
                profile_snapshot.get("name"))
        elif attribute_type == "quantity":
            unit_defining_path = attribute_defining_element.get("path") + ".code"
            unit_defining_elements = sd.get_element_from_snapshot_by_path(profile_snapshot, unit_defining_path)
            if len(unit_defining_elements) > 1:
                raise Exception(f"More than one element found for path {unit_defining_path}")
            attribute_definition.allowedUnits = sd.get_units(unit_defining_elements[0],
                                                                      profile_snapshot.get("name"))
        elif attribute_type == "reference":
            attribute_definition = self.generate_reference_attribute_definition(profile_snapshot,
                                                                                attribute_defining_element_id)
        elif attribute_type == "composite":
            attribute_definition = self.generate_composite_attribute(profile_snapshot,attribute_defining_element_id)
        else:
            raise InvalidValueTypeException("Invalid value type: " + attribute_type)
        return attribute_definition

    def generate_composite_attribute(self, profile_snapshot, attribute_defining_element_id) -> AttributeDefinition:
        attribute_defining_elements = sd.get_element_defining_elements(attribute_defining_element_id,
                                                                                profile_snapshot, self.module_dir,
                                                                                self.data_set_dir)
        if len(attribute_defining_elements) != 2:
            raise ValueError("composite attributes need to reference 2 elements")
        element = attribute_defining_elements[0]
        predicate = attribute_defining_elements[-1]
        attribute_code = self.generate_composite_attribute_code(profile_snapshot, predicate)
        attribute_definition = AttributeDefinition(attribute_code, "composite")
        attribute_type = sd.get_element_type(element)
        if attribute_type == "Quantity":
            if pattern_quantity := element.get("patternQuantity"):
                if pattern_quantity.get("code"):
                    attribute_definition.allowedUnits = [TermCode(pattern_quantity.get("system"), pattern_quantity.get("code"), pattern_quantity.get("unit"))]
            else:
                unit_defining_path = element.get("path") + ".code"
                unit_defining_elements = sd.get_element_from_snapshot_by_path(profile_snapshot, unit_defining_path)
                if len(unit_defining_elements) > 1:
                    unit_defining_elements = list(filter(lambda x: self.get_slice_name(x) == self.get_slice_name(element),
                                                         unit_defining_elements))
                    if len(unit_defining_elements) > 1:
                        raise Exception(f"More than one element found for path {unit_defining_path}")
                attribute_definition.allowedUnits = sd.get_units(unit_defining_elements[0],profile_snapshot.get("name"))

            attribute_definition.display = get_display_from_element_definition(get_common_ancestor(profile_snapshot, element.get("id"),predicate.get("id")))
            attribute_definition.type = "quantity"
            return attribute_definition
        elif attribute_type == "CodeableConcept":
            if binding := predicate.get("binding"):
                concepts = sd.get_selectable_concepts(
                     predicate,
                     profile_snapshot.get("name"))
                attribute_definition.referencedValueSet = concepts
            elif binding := element.get("binding"):
                concepts = sd.get_selectable_concepts(
                     element,
                     profile_snapshot.get("name"))
                attribute_definition.referencedValueSet = concepts
            else:
                concepts = sd.get_fixed_term_codes(predicate, profile_snapshot, self.module_dir, self.data_set_dir,
                                                   self.__client)
                attribute_definition.referencedCriteriaSet = self.get_reference_criteria_set_from_fixed_term_codes(
                    concepts, self.get_referenced_context(profile_snapshot, self.module_dir))
            return attribute_definition
        else:
            raise InvalidValueTypeException("Invalid value type: " + attribute_type + " for composite attribute " +
                                            attribute_defining_element_id +
                                            " in profile " + profile_snapshot.get("name"))

    @staticmethod
    def get_slice_name(element):
        if element.get("sliceName"):
            return element.get("sliceName")
        elif ':' in element.get("id"):
            # if len(element.get("id").split(':')) == 3:
            #     # Observation.component:SystolicBP.value[x]:---->valueQuantity<----.code
            #     return element.get("id").split(':')[2].split(".")[0]
            # Observation.component:----->SystolicBP<-----.value[x].code
            return element.get("id").split(":")[1].split(".")[0]

        else:
            return ""

    def generate_composite_attribute_code(self, profile_snapshot, element) -> TermCode:
        composite_attribute_code = sd.get_fixed_term_codes(element, profile_snapshot, self.module_dir,
                                                           self.data_set_dir, self.__client)
        if composite_attribute_code:
            return composite_attribute_code[0]

        else:
            raise InvalidValueTypeException(
                "Unable to generate composite attribute code for element: " + element.get("id") +
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
        """
        Generates an attribute definition for a reference attribute
        :param profile_snapshot: FHIR profile snapshot
        :param attribute_defining_element_id: element id that defines the reference
        """
        attribute_defining_elements_with_source_snapshots = sd.get_element_defining_elements_with_source_snapshots(
            attribute_defining_element_id,
            profile_snapshot, self.module_dir,
            self.data_set_dir)
        # TODO: Check if this suffices in all instances
        # Choose first matching ElementDefinition element as subsequent matching elements might already originate from
        # the referenced profile and thus their descriptions miss the context of the attribute (e.g. just 'code of a
        # diagnosis' and not 'code of a diagnosis established using a biopsy sample')
        attribute_code, attribute_display = process_element_definition(
                                                attribute_defining_elements_with_source_snapshots[0].element)
        attribute_definition = AttributeDefinition(attribute_code, "reference")
        attribute_definition.display = attribute_display
        attribute_definition.referencedCriteriaSet = self.get_reference_criteria_set(
            attribute_defining_elements_with_source_snapshots)
        return attribute_definition

    def get_reference_criteria_set(self, elements: List[ProcessedElementResult]) -> CriteriaSet:  #
        element = elements[-1].element
        snapshot = elements[-1].profile_snapshot
        module_dir = elements[-1].module_dir
        context = self.get_referenced_context(snapshot, module_dir)
        if fixed_term_codes := get_fixed_term_codes(element, snapshot, module_dir, self.data_set_dir, self.__client):
            return self.get_reference_criteria_set_from_fixed_term_codes(fixed_term_codes, context)
        elif url := get_binding_value_set_url(elements[-1].element):
            return self.get_reference_criteria_set_from_value_set(url, context)
        else:
            raise Exception("Unable to generate reference criteria set for element: " + element.get("id") +
                            " in profile: " + snapshot.get("name"))

    def get_referenced_context(self, profile_snapshot, module_dir):
        """
        Returns the referenced context for the given FHIR profile snapshot
        :param profile_snapshot: FHIR profile snapshot
        :param module_dir: Module directory of the profile
        :return: Referenced context
        """
        module_name = module_dir.replace("package", "").split(os.sep)[1]
        return self.querying_meta_data_resolver.get_query_meta_data(profile_snapshot,
                                                                    module_name)[0].context

    def get_reference_criteria_set_from_value_set(self, value_set_canonical_url: str, context: TermCode) -> CriteriaSet:
        """
        Returns the criteria set for the given value set
        :param value_set_canonical_url: Canonical URL of the value set
        :param context: Context of the criteria set
        :return: Criteria set
        """
        # TODO: contextualized_url
        term_codes = self.__client.get_termcodes_for_value_set(value_set_canonical_url)
        criteria_set = CriteriaSet(self.create_criteria_set_url_from_vs(value_set_canonical_url, context))
        for term_code in term_codes:
            criteria_set.contextualized_term_codes.append((context, term_code))
        return criteria_set

    def get_reference_criteria_set_from_fixed_term_codes(self, fixed_term_codes: List[TermCode],
                                                         context: TermCode) -> CriteriaSet:
        """
        Returns the criteria set for the given fixed term codes
        :param fixed_term_codes: Fixed term codes
        :param context: Context of the criteria set
        :return: Criteria set
        """
        criteria_set = CriteriaSet(self.create_criteria_set_url_from_tc(fixed_term_codes[0], context))
        for term_code in fixed_term_codes:
            criteria_set.contextualized_term_codes.append((context, term_code))
        return criteria_set

    @staticmethod
    def create_criteria_set_url_from_tc(term_code, context):
        """
        Creates a criteria set url from the given term code and context
        :param term_code: Term code
        :param context: Context
        :return: Criteria set URL
        """
        return f"http://{context.system}/CriteriaSet/{context.code}/{term_code.display}"

    @staticmethod
    def create_criteria_set_url_from_vs(vs, context):
        """
        Creates a criteria set url from the given value set and context
        :param vs: value set
        :param context: Context
        :return: Criteria set URL
        """
        return f"http://{context.system}/CriteriaSet/{context.code}/{vs.split('/')[-1]}"
