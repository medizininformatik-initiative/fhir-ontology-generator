from api import ResourceQueryingMetaDataResolver
from model.ResourceQueryingMetaData import ResourceQueryingMetaData
from model.UIProfileModel import ValueDefinition, UIProfile, VALUE_TYPE_OPTIONS, TermCode, AttributeDefinition
from typing import List


class InvalidValueTypeException(Exception):
    pass


class UIProfileGenerator:
    """
    This class is responsible for generating UI profiles for a given FHIR profile.
    """

    def __init__(self, querying_meta_data_resolver: ResourceQueryingMetaDataResolver):
        """
        :param querying_meta_data_resolver: resolves the for the query relevant meta data for a given FHIR profile
        snapshot
        """
        self.querying_meta_data_resolver = querying_meta_data_resolver

    def generate_ui_profile(self, profile_snapshot: dict) -> UIProfile:
        """
        Generates a UI profile for the given FHIR profile snapshot
        :param profile_snapshot:
        :return: UI profile for the given FHIR profile snapshot
        """
        ui_profile = UIProfile(profile_snapshot["name"])
        querying_meta_data = self.querying_meta_data_resolver.get_query_meta_data(profile_snapshot, None)
        ui_profile.timeRestrictionAllowed = self.is_time_restriction_allowed(querying_meta_data)
        ui_profile.valueDefinitions = self.get_value_definition(profile_snapshot, querying_meta_data)
        ui_profile.attributeDefinitions = self.get_attribute_definitions(profile_snapshot, querying_meta_data)

    def get_value_definition(self, profile_snapshot, value_defining_element_id) -> ValueDefinition:
        """
        Returns the value definition for the given FHIR profile snapshot at the value defining element id
        :param value_defining_element_id: element id that defines the value
        :param profile_snapshot: FHIR profile snapshot
        :return: value definition
        :raises InvalidValueTypeException: if the value type is not supported
        """
        value_type = self.get_value_type(profile_snapshot, value_defining_element_id)
        value_definition = ValueDefinition(value_type)
        if value_type == "concept":
            value_definition.selectableConcepts = self.get_selectable_concepts(profile_snapshot,
                                                                               value_defining_element_id)
        elif value_type == "quantity":
            value_definition.allowedUnits = self.get_units(profile_snapshot, value_defining_element_id)
        elif value_type == "reference":
            value_definition.reference = self.get_reference(profile_snapshot, value_defining_element_id)
        else:
            raise InvalidValueTypeException("Invalid value type: " + value_type)
        return value_definition

    def get_value_type(self, profile_snapshot, value_defining_element_id) -> VALUE_TYPE_OPTIONS:
        """
        Returns the value type for the given FHIR profile snapshot at the value defining element id
        :return:
        """
        pass

    def get_answer_options(self):
        pass

    def get_units(self, profile_snapshot, quantity_defining_element_id) -> List[TermCode]:
        pass

    def get_value_set_defining_url(self):
        pass

    def generate_attribute_defining_code(self, profile_snapshot, attribute_defining_element_id) -> TermCode:
        pass

    def get_attribute_definitions(self, profile_snapshot, querying_meta_data) -> List[AttributeDefinition]:
        pass

    def get_selectable_concepts(self, profile_snapshot, value_defining_element_id) -> List[TermCode]:
        """
        Returns the selectable concepts for the given FHIR profile snapshot at the value defining element id
        based on the obtained binding information
        :param profile_snapshot: FHIR profile snapshot
        :param value_defining_element_id: element id that defines the value
        :return: selectable concepts for the value or attribute definition
        """

    @staticmethod
    def is_time_restriction_allowed(querying_meta_data: ResourceQueryingMetaData) -> bool:
        """
        Returns whether time restrictions are allowed for the given FHIR profile snapshot
        :return: return true if a time restricting element is identified in the querying meta data
        """
        return querying_meta_data.time_restriction_defining_id is not None
