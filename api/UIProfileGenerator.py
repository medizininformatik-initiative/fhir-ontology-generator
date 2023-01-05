from __future__ import annotations

import json
import os

from TerminologService.ValueSetResolver import get_termcodes_from_onto_server, get_term_codes_by_id, \
    get_term_entries_from_onto_server
from api import ResourceQueryingMetaDataResolver
from model.ResourceQueryingMetaData import ResourceQueryingMetaData
from model.UIProfileModel import ValueDefinition, UIProfile, VALUE_TYPE_OPTIONS, TermCode, AttributeDefinition
from typing import List, Dict, Tuple

from model.UiDataModel import TermEntry

FHIR_TYPES_TO_VALUE_TYPES = {
    "code": "concept",
    "Quantity": "quantity",
    "Reference": "reference"
}

UCUM_SYSTEM = "http://unitsofmeasure.org"


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
        self.current_module_dir: str = ""

    def generate_ui_profiles(self, fhir_dataset_dir: str):
        """
        Generates the ui trees for all FHIR profiles in the differential directory
        :param fhir_dataset_dir: root directory of the FHIR dataset containing the modules and their packages containing
        the FHIR Profiles and their snapshots of interest
        {FHIR_DATASET_DIR}/{MODULE_NAME}/package/
        :return: ui trees for all FHIR profiles in the differential directory
        """
        result: Dict[TermCode, List[UIProfile]] = {}
        for module_dir in [folder for folder in os.scandir(fhir_dataset_dir) if folder.is_dir()]:
            self.current_module_dir: str = module_dir.path
            files = [file for file in os.scandir(f"{fhir_dataset_dir}/{module_dir.name}/package") if file.is_file()
                     and file.name.endswith("snapshot.json")]
            term_code, ui_profiles = self.generate_contextualized_ui_profile("mii.fdpg.cds", module_dir.name,
                                                                             module_dir.name, files)
            result[term_code] = ui_profiles
        return result

    def generate_contextualized_ui_profile(self, system: str, code: str, display: str,
                                           fhir_profile_snapshots: List[dict]) -> Tuple[TermCode, List[UIProfile]]:
        """
        Generates a UI profile for the given FHIR profile snapshots
        :param system: system of the context
        :param code: code of the context
        :param display: display of the context
        :param fhir_profile_snapshots: fhir profile snapshots
        :return: context term_code and UI profiles for the given FHIR profile snapshots
        """
        term_code = TermCode(system, code, display)
        ui_profiles = [self.generate_ui_profile(profile) for profile in fhir_profile_snapshots]
        return term_code, ui_profiles

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
        for querying_meta_data_entry in querying_meta_data:
            ui_profile = self.generate_ui_profile(profile_snapshot, querying_meta_data_entry)
            term_codes = get_term_codes_by_id(querying_meta_data_entry.term_code_defining_id,
                                              profile_snapshot)
            ui_profile_name = ui_profile.name
            term_code_ui_profile_name_mapping = {**term_code_ui_profile_name_mapping,
                                                 **zip({context, term_codes}, [ui_profile_name] * len(term_codes))}
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
        ui_profile.valueDefinitions = self.get_value_definition(profile_snapshot, querying_meta_data)
        ui_profile.attributeDefinitions = self.get_attribute_definitions(profile_snapshot, querying_meta_data)
        return ui_profile

    def get_value_definition(self, profile_snapshot, value_defining_element_id) -> ValueDefinition:
        """
        Returns the value definition for the given FHIR profile snapshot at the value defining element id
        :param value_defining_element_id: element id that defines the value
        :param profile_snapshot: FHIR profile snapshot
        :return: value definition
        :raises InvalidValueTypeException: if the value type is not supported
        """
        value_defining_element = self.get_element_from_snapshot(profile_snapshot, value_defining_element_id)
        value_type = self.get_value_type(profile_snapshot, value_defining_element)
        value_definition = ValueDefinition(value_type)
        if value_type == "concept":
            value_definition.selectableConcepts = self.get_selectable_concepts(value_defining_element,
                                                                               profile_snapshot.get("name"))
        elif value_type == "quantity":
            # "Observation.valueQuantity.value" -> "Observation.valueQuantity.code"
            unit_defining_element_id = value_defining_element_id.split(".")[:-1].append("code").join(".")
            unit_defining_element = self.get_element_from_snapshot(profile_snapshot, unit_defining_element_id)
            value_definition.allowedUnits = self.get_units(unit_defining_element, profile_snapshot.get("name"))
        elif value_type == "reference":
            value_definition.reference = self.get_reference(profile_snapshot, value_defining_element)
        else:
            raise InvalidValueTypeException("Invalid value type: " + value_type)
        return value_definition

    def get_value_type(self, profile_snapshot, value_defining_element) -> VALUE_TYPE_OPTIONS:
        """
        Returns the value type from the querying meta data if it is extracted from the value defining element
        :param profile_snapshot: FHIR profile snapshot
        :param value_defining_element: element that defines the value
        :return: value type
        """
        querying_meta_data_defined_value_type: VALUE_TYPE_OPTIONS | None = \
            self.querying_meta_data_resolver.get_query_meta_data(profile_snapshot).value_type
        return querying_meta_data_defined_value_type if querying_meta_data_defined_value_type else \
            self.extract_value_type(value_defining_element, profile_snapshot.get("name"))

    @staticmethod
    def extract_value_type(value_defining_element: dict, profile_name: str = "") -> VALUE_TYPE_OPTIONS:
        """
        Extracts the value type for the given FHIR profile snapshot at the value defining element id
        :param value_defining_element: element that defines the value
        :param profile_name: name of the FHIR profile for debugging purposes can be omitted
        :return: value type
        """
        fhir_value_types = value_defining_element.get("type")
        if not fhir_value_types:
            raise InvalidValueTypeException(f"No value type defined in element: {str(value_defining_element)}"
                                            f" in profile: {profile_name}")
        if len(fhir_value_types) > 1:
            raise InvalidValueTypeException(f"More than one value type defined in element: "
                                            f"{str(value_defining_element)} refine the profile: " + profile_name)
        return FHIR_TYPES_TO_VALUE_TYPES[fhir_value_types[0]] if fhir_value_types[0] in FHIR_TYPES_TO_VALUE_TYPES else \
            fhir_value_types[0]

    @staticmethod
    def get_selectable_concepts(concept_defining_element, profile_name: str = "") -> List[TermCode]:
        """
        Returns the answer options for the given concept defining element
        :param concept_defining_element:
        :param profile_name: name of the FHIR profile for debugging purposes can be omitted
        :return: answer options as term codes
        :raises InvalidValueTypeException: if no valueSet is defined for the concept defining element
        """
        if binding := concept_defining_element.get("binding"):
            if value_set_url := binding.get("valueSet"):
                return get_termcodes_from_onto_server(value_set_url)
            else:
                raise InvalidValueTypeException(f"No value set defined in element: {str(binding)}"
                                                f" in profile: {profile_name}")
        else:
            raise InvalidValueTypeException(f"No binding defined in element: {str(concept_defining_element)}"
                                            f" in profile: {profile_name}")

    @staticmethod
    def get_units(unit_defining_element, profile_name: str = "") -> List[TermCode]:
        if unit_code := unit_defining_element.get("fixedCode"):
            return [TermCode(UCUM_SYSTEM, unit_code, unit_code)]
        else:
            raise InvalidValueTypeException(f"No unit defined in element: {str(unit_defining_element)}"
                                            f" in profile: {profile_name}")

    @staticmethod
    def get_value_set_defining_url(value_set_defining_element: dict, profile_name: str = "") -> str:
        """
        Returns the value set defining url for the given value set defining element
        :param value_set_defining_element: element that defines the value set
        :param profile_name: name of the FHIR profile for debugging purposes can be omitted
        :return: canonical url of the value set
        """
        if binding := value_set_defining_element.get("binding"):
            if value_set_url := binding.get("valueSet"):
                return value_set_url
            else:
                raise InvalidValueTypeException(f"No value set defined in element: {str(binding)}"
                                                f" in profile: {profile_name}")
        else:
            raise InvalidValueTypeException(f"No binding defined in element: {str(value_set_defining_element)}"
                                            f" in profile: {profile_name}")

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
        for attribute_defining_id, attribute_type in querying_meta_data.attribute_defining_ids.items():
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
        attribute_defining_element = self.get_element_from_snapshot(profile_snapshot, attribute_defining_element_id)
        attribute_type = attribute_type if attribute_type else self.extract_value_type(attribute_defining_element,
                                                                                       profile_snapshot.get("name"))
        attribute_code = self.generate_attribute_defining_code(profile_snapshot, attribute_defining_element_id)
        attribute_definition = AttributeDefinition(attribute_code, attribute_type)
        if attribute_type == "concept":
            attribute_definition.selectableConcepts = self.get_selectable_concepts(attribute_defining_element,
                                                                                   profile_snapshot.get("name"))
        elif attribute_type == "quantity":
            # "Observation.valueQuantity.value" -> "Observation.valueQuantity.code"
            unit_defining_element_id = "".join(attribute_defining_element_id.split(".")[:-1] + ["code"])
            unit_defining_element = self.get_element_from_snapshot(profile_snapshot, unit_defining_element_id)
            attribute_definition.allowedUnits = self.get_units(unit_defining_element, profile_snapshot.get("name"))
        elif attribute_type == "reference":
            attribute_definition.reference = self.get_reference(profile_snapshot, attribute_defining_element)
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

    @staticmethod
    def get_element_from_snapshot(profile_snapshot, element_id) -> dict:
        """
        Returns the element from the given FHIR profile snapshot at the given element id
        :param profile_snapshot: FHIR profile snapshot
        :param element_id: element id
        :return: element
        """
        try:
            for element in profile_snapshot["snapshot"]["element"]:
                if "id" in element and element["id"] == element_id:
                    return element
        except KeyError:
            print(
                f"KeyError the element id: {element_id} is not in the snapshot or the snapshot has no snapshot "
                f"elements")
        else:
            return {}

    def get_reference(self, profile_snapshot: dict, value_defining_element: str) -> dict:
        pass

    # TODO: move elsewhere
    @staticmethod
    def get_profiles_with_base_definition(fhir_dataset_dir: str, base_definition: str) -> dict:
        """
        Returns the profiles that have the given base definition
        :param fhir_dataset_dir: path to the FHIR dataset directory
        :param base_definition: base definition
        :return: generator of profiles that have the given base definition
        """
        for module_dir in [folder for folder in os.scandir(fhir_dataset_dir) if folder.is_dir()]:
            files = [file for file in os.scandir(f"{module_dir.path}/package") if file.is_file()
                     and file.name.endswith("snapshot.json")]
            for file in files:
                with open(file.path, "r") as f:
                    profile = json.load(f)
                    if profile.get("baseDefinition") == base_definition:
                        return profile
                    elif profile.get("type") == base_definition.split("/")[-1]:
                        return profile

    @staticmethod
    def get_extension_definition(module_dir: str, extension_profile_url: str) -> dict:
        """
        Returns the FHIR extension definition for the given extension profile url, the extension has to be located in 
        {module_dir}/package/extension
        :param module_dir: path to the module directory
        :param extension_profile_url:  extension profile url
        :return: extension definition
        """
        files = [file for file in os.scandir(f"{module_dir}/package/extension") if file.is_file()
                 and file.name.endswith("snapshot.json")]
        for file in files:
            with open(file.path, "r") as f:
                profile = json.load(f)
                if profile.get("url") == extension_profile_url:
                    return profile

    @staticmethod
    def resolve_defining_id(profile_snapshot: dict, defining_id: str, data_set_dir: str, module_dir: str) \
            -> dict | str | List[TermEntry]:
        """
        Basic compiler for the following syntax:
        resolveExpression:
        : 'Resolve' '(' FHIRElementId | resolveExpression')'
        ;
        implicitPathExpression:
        : resolveExpression '.' FHIRElementId
        ;
        castExpression:
        : implicitPathExpression 'as' FHIRType
        ;
        FHIRType:
        'ValueSet'
        ;
        Resolve { element_id }
        example: Resolve(Resolve(Specimen.extension:festgestellteDiagnose).value[x]).code.coding:icd-10-gm as ValueSet
        -> lookup extension url defined at Specimen.extension:festgestellteDiagnose -> Profile with this url
        -> lookup value[x] at the extension profile -> Reference type with value Condition -> lookup Condition profile
        -> lookup code.coding:icd-10-gm at the Condition profile -> extraction as ValueSet
        Resolves the given expression to the specified FHIR type by resolving the element ids to the referenced
        extensions and profiles and then applying the FHIRElementId to the resolved profile or extension and finally
        casting the result to the specified FHIR type. Currently only the ValueSet type is supported.
        :param profile_snapshot: FHIR profile snapshot
        :param defining_id: defining id
        :param module_dir: path to the module directory
        :param data_set_dir: path to the FHIR dataset directory
        :return: resolved defining id
        """
        statement = defining_id
        statements = statement.split("as")
        if "Resolve" in statements[0]:
            statement = statements[0]
            if "ext:" in statement or "ref:" in statement:
                index = statement.find("ext:") if "ext:" in statement else statement.find("ref:")
                end_index = statement.find(")")
                statement = statement[(index - 8):end_index + 1]
            else:
                statement = statement[:statement.find(")")]
                statement = statement.replace("Resolve(", "").replace(")", "")
        if "Resolve" in statement:
            if "ext:" in statement:
                extension_url = statement[statement.find("ext:") + 4:statement.find(")")]
                extension_profile = UIProfileGenerator.get_extension_definition(module_dir, extension_url)
                if extension_profile is not None:
                    extension_type = extension_profile.get("type")
                    defining_id = defining_id.replace(statement, extension_type)
                    return UIProfileGenerator.resolve_defining_id(extension_profile, defining_id, data_set_dir,
                                                                  module_dir)
                else:
                    raise Exception(f"Extension profile not found for {statement}")
            elif "ref:" in statement:
                base_definition = statement[statement.find("ref:") + 4:statement.find(")")]
                reference_profile = UIProfileGenerator.get_profiles_with_base_definition(data_set_dir, base_definition)
                if reference_profile is not None:
                    reference_type = reference_profile.get("type")
                    defining_id = defining_id.replace(statement, reference_type)
                    return UIProfileGenerator.resolve_defining_id(reference_profile, defining_id, data_set_dir,
                                                                  module_dir)
                else:
                    raise Exception(f"Reference profile not found for {statement}")
        elif "as ValueSet" in statement:
            statement = statement.replace(" as ValueSet", "")
            value_set_element = UIProfileGenerator.get_element_from_snapshot(profile_snapshot, statement)
            return UIProfileGenerator.get_value_set_defining_url(value_set_element, profile_snapshot.get("name"))
        else:
            resolved_element = UIProfileGenerator.get_element_from_snapshot(profile_snapshot, statement)
            if value_types := resolved_element.get("type"):
                if len(value_types) > 1:
                    raise Exception(f"Could not resolve {defining_id} too many value types" + value_types)
                for value_type in value_types:
                    if value_type.get("code") == "Reference":
                        reference_url = "ref:" + value_type.get("targetProfile")[0]
                        defining_id = defining_id.replace(statement, reference_url)
                        return UIProfileGenerator.resolve_defining_id(profile_snapshot, defining_id, data_set_dir,
                                                                      module_dir)
                    elif value_type.get("code") == "Extension":
                        extension_url = "ext:" + value_type.get("profile")[0]
                        defining_id = defining_id.replace(statement, extension_url)
                        return UIProfileGenerator.resolve_defining_id(profile_snapshot, defining_id, data_set_dir,
                                                                      module_dir)
                    else:
                        return resolved_element


# if __name__ == "__main__":
#     with open("example/mii_core_data_set/resources/core_data_sets/de.medizininformatikinitiative.kerndatensatz"
#               ".biobank#1.0.3/package/StructureDefinition-Specimen-snapshot.json", "r") as f:
#         profile = json.load(f)
#         print(UIProfileGenerator.resolve_defining_id(profile, "Resolve(Resolve("
#                                                               "Specimen.extension:festgestellteDiagnose)"
#                                                               ".value[x]).code.coding:icd10-gm as ValueSet",
#                                                               "example/mii_core_data_set/resources/core_data_sets",
#                                                               "example/mii_core_data_set/resources/fdpg_differential/"
#                                                               "Bioprobe"))
