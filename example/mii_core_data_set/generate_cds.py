from __future__ import annotations

import argparse
import copy
import json
import os
from typing import List, ValuesView, Dict, Tuple

import docker
from jsonschema import validate
from lxml import etree

from FHIRProfileConfiguration import *
from core.CQLMappingGenerator import CQLMappingGenerator
from core.FHIRSearchMappingGenerator import FHIRSearchMappingGenerator
from core.PathlingMappingGenerator import PathlingMappingGenerator
from core.ResourceQueryingMetaDataResolver import ResourceQueryingMetaDataResolver
from core.SearchParameterResolver import SearchParameterResolver
from core.StrucutureDefinitionParser import get_element_from_snapshot
from core.UIProfileGenerator import UIProfileGenerator
from core.UITreeGenerator import UITreeGenerator
from database.DataBaseWriter import DataBaseWriter
from helper import download_simplifier_packages, generate_snapshots, write_object_as_json, load_querying_meta_data, \
    generate_result_folder
from model.MappingDataModel import CQLMapping, FhirMapping, MapEntryList, FixedFHIRCriteria, PathlingMapping
from model.ResourceQueryingMetaData import ResourceQueryingMetaData
from model.TreeMap import ContextualizedTermCodeInfoList, TreeMapList
from model.UIProfileModel import UIProfile
from model.UiDataModel import TermCode

core_data_sets = [MII_CONSENT, MII_DIAGNOSE, MII_LAB, MII_MEDICATION, MII_PERSON, MII_PROCEDURE, MII_SPECIMEN]
WINDOWS_RESERVED_CHARACTERS = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']


class MIICoreDataSetQueryingMetaDataResolver(ResourceQueryingMetaDataResolver):
    def __init__(self):
        super().__init__()

    def get_query_meta_data(self, fhir_profile_snapshot: dict, module_name: str) -> List[ResourceQueryingMetaData]:
        query_meta_data = self._get_query_meta_data_by_module_name(fhir_profile_snapshot, module_name)
        if not query_meta_data:
            query_meta_data = self._get_query_meta_data_by_snapshot(fhir_profile_snapshot)
            if not query_meta_data:
                print(
                    f"No query meta data found for profile: {fhir_profile_snapshot.get('name')} and module_name: "
                    f"{module_name}")
        if len(query_meta_data) > 1:
            query_meta_data = self._filter_query_meta_data(query_meta_data, fhir_profile_snapshot)
        return query_meta_data

    @staticmethod
    def _get_query_meta_data_by_module_name(fhir_profile_snapshot: dict, module_name: str) -> \
            List[ResourceQueryingMetaData]:
        return [resource_querying_meta_data for resource_querying_meta_data
                in load_querying_meta_data("resources/QueryingMetaData") if
                resource_querying_meta_data.context.code == module_name and
                resource_querying_meta_data.resource_type == fhir_profile_snapshot["type"]]

    @staticmethod
    def _get_query_meta_data_by_snapshot(fhir_profile_snapshot: dict) -> List[ResourceQueryingMetaData]:
        context_base_type = TermCode("fdpg.mii.cds", fhir_profile_snapshot["baseDefinition"].split("/")[-1],
                                     fhir_profile_snapshot["baseDefinition"].split("/")[-1])
        resolved_by_base_type = [resource_querying_meta_data for resource_querying_meta_data
                                 in load_querying_meta_data("resources/QueryingMetaData") if
                                 resource_querying_meta_data.resource_type == fhir_profile_snapshot["type"]
                                 and resource_querying_meta_data.context == context_base_type]
        context_by_url = TermCode("fdpg.mii.cds", fhir_profile_snapshot["url"].split("/")[-1],
                                  fhir_profile_snapshot["url"].split("/")[-1])
        resolved_by_url = [resource_querying_meta_data for resource_querying_meta_data
                           in load_querying_meta_data("resources/QueryingMetaData") if
                           resource_querying_meta_data.resource_type == fhir_profile_snapshot["type"]
                           and resource_querying_meta_data.context == context_by_url]
        return resolved_by_base_type if resolved_by_base_type else resolved_by_url

    @staticmethod
    def _filter_query_meta_data(query_meta_data: List[ResourceQueryingMetaData], fhir_profile_snapshot: dict) \
            -> List[ResourceQueryingMetaData]:
        """
        Filters the query meta data based on the min property of the fhir_profile_snapshot for the value element
        :param query_meta_data: initial query meta data
        :param fhir_profile_snapshot: FHIR profile snapshot
        :return: filtered query meta data
        """
        result = query_meta_data.copy()
        for meta_data in query_meta_data:
            try:
                value_element = get_element_from_snapshot(fhir_profile_snapshot, meta_data.value_defining_id)
            except KeyError:
                value_element = None
            if not value_element or value_element.get("min") == 0:
                result.remove(meta_data)
        return result if result else query_meta_data


class MIICoreDataSetSearchParameterResolver(SearchParameterResolver):
    def _load_module_search_parameters(self) -> List[Dict]:
        params = []
        for file in os.listdir("resources/search_parameter"):
            if file.endswith(".json"):
                with open(os.path.join("resources/search_parameter", file), "r", encoding="utf-8") as f:
                    params.append(json.load(f))
        return params




def generate_term_code_mapping(_entries: List):
    """
    Generates the term code mapping for the given entries and saves it in the mapping folder
    :param _entries: TermEntries to generate the mapping for
    """
    pass


def generate_term_code_tree(_entries: List):
    """
    Generates the term code tree for the given entries and saves it in the mapping folder
    :param _entries:
    :return:
    """
    pass


def validate_ui_profile(_profile_name: str):
    """
    Validates the ui profile with the given name against the ui profile schema
    :param _profile_name: name of the ui profile
    :raises: jsonschema.exceptions.ValidationError if the ui profile is not valid
             jsonschema.exceptions.SchemaError if the ui profile schema is not valid
    """
    pass
    # f = open("ui-profiles/" + profile_name + ".json", 'r')
    # validate(instance=json.load(f), schema=json.load(open("resources/schema/ui-profile-schema.json")))


def validate_fhir_mapping(mapping_name: str):
    """
    Validates the fhir mapping with the given name against the fhir mapping schema
    :param mapping_name: name of the fhir mapping file
    :raises: jsonschema.exceptions.ValidationError if the fhir mapping is not valid
             jsonschema.exceptions.SchemaError if the fhir mapping schema is not valid
    """
    f = open("mapping-old/fhir/" + mapping_name + ".json", 'r')
    validate(instance=json.load(f), schema=json.load(open("../../resources/schema/fhir-mapping-schema.json")))


def validate_mapping_tree(tree_name: str):
    """
    Validates the mapping tree with the given name against the mapping tree schema
    :param tree_name: name of the mapping tree
    :raises: jsonschema.exceptions.ValidationError if the mapping tree is not valid
             jsonschema.exceptions.SchemaError if the mapping tree schema is not valid
    """
    f = open("mapping-tree/" + tree_name + ".json", 'r')
    validate(instance=json.load(f), schema=json.load(open("../../resources/schema/codex-code-tree-schema.json")))


def write_ui_trees_to_files(trees: List[TreeMapList], directory: str = "ui-trees"):
    """
    Writes the ui trees to the ui-profiles folder
    :param trees: ui trees to write
    :param directory: directory to write the ui trees to
    """
    for tree in trees:
        write_object_as_json(tree, f"{directory}/{tree.module_name}_tree.json")


def write_term_code_info_to_file(term_code_info: List[ContextualizedTermCodeInfoList], directory: str = "term-code-info"):
    """
    Writes the term code info to the given file
    :param term_code_info: term code info to write
    :param file_name: file name to write the term code info to
    """
    for info in term_code_info:
        if info.entries:
            module_name = info.entries[0].module.display
            write_object_as_json(info, f"{directory}/{module_name}_term_code_info.json")


def write_used_value_sets_to_files(ui_profiles: List[UIProfile], directory: str = "value-sets"):
    """
    Writes the value sets used in the ui profiles to the value-sets folder
    :param ui_profiles: ui profiles to extract the value sets from
    :param directory: directory to write the value sets to
    """
    value_sets = list()
    for ui_profile in ui_profiles:
        if ui_profile.valueDefinition:
            if value_set := ui_profile.valueDefinition.referencedValueSet:
                value_sets.append(value_set)
        if ui_profile.attributeDefinitions:
            for attribute_definition in ui_profile.attributeDefinitions:
                if value_set := attribute_definition.referencedValueSet:
                    value_sets.append(value_set)
    for value_set in value_sets:
        write_object_as_json(value_set, f"{directory}/{remove_reserved_characters(value_set.url.split('/')[-1])}.json")


def write_used_criteria_sets_to_files(ui_profiles: List[UIProfile], directory: str = "criteria-sets"):
    """
    Writes the criteria sets used in the ui profiles to the criteria-sets folder
    :param ui_profiles: ui profiles to extract the criteria sets from
    :param directory: directory to write the criteria sets to
    """
    criteria_sets = list()
    for ui_profile in ui_profiles:
        if ui_profile.attributeDefinitions:
            for attribute_definition in ui_profile.attributeDefinitions:
                if criteria_set := attribute_definition.referenceCriteriaSet:
                    criteria_sets.append(criteria_set)

    for criteria_set in criteria_sets:
        write_object_as_json(criteria_set, f"{directory}/{remove_reserved_characters(criteria_set.url.split('/')[-1])}.json")


# Todo: this should be an abstract method that has to be implemented for each use-case
# Todo: move this concrete implementation elsewhere


def write_cds_ui_profile(module_category_entry):
    """
    Writes the ui profile for the given module category entry to the ui-profiles folder
    :param module_category_entry: name of the module category entry
    """
    f = open("ui-profiles/" + module_category_entry.display + ".json", 'w', encoding="utf-8")
    if len(module_category_entry.children) == 1:
        f.write(module_category_entry.children[0].to_json())
    else:
        f.write(module_category_entry.to_json())
    f.close()


def denormalize_mapping_to_old_format(term_code_to_mapping_name, mapping_name_to_mapping):
    """
    Denormalizes the mapping to the old format
    :param term_code_to_mapping_name: mapping from term codes to mapping names
    :param mapping_name_to_mapping: mappings to use
    :return: denormalized entries
    """
    result = MapEntryList()
    for context_and_term_code, mapping_name in term_code_to_mapping_name.items():
        try:
            mapping = copy.copy(mapping_name_to_mapping[mapping_name])
            mapping.key = context_and_term_code[1]
            mapping.context = context_and_term_code[0]
            result.entries.append(mapping)
        except KeyError:
            print("No mapping found for term code " + context_and_term_code[1].code)
    return result


def move_back_other(entries):
    """
    Entries are sorted alphabetically. This method moves the entries that express "Other" to the end of the list
    :param entries: list of entries
    """
    entries_copy = entries.copy()
    for entry in entries_copy:
        for other_naming in ["Sonstige", "sonstige", "andere", "Andere", "Weitere", "Other"]:
            if entry.termCode.display.startswith(other_naming):
                entries.remove(entry)
                entries.append(entry)
        if entry.children:
            move_back_other(entry.children)


def configure_args_parser():
    """
    Configures the argument parser
    :return: the configured argument parser
    """
    arg_parser = argparse.ArgumentParser(description='Generate the UI-Profile of the core data set for the MII-FDPG')
    arg_parser.add_argument('--download_packages', action='store_true')
    arg_parser.add_argument('--generate_snapshot', action='store_true')
    arg_parser.add_argument('--generate_csv', action='store_true')
    arg_parser.add_argument('--generate_ui_trees', action='store_true')
    arg_parser.add_argument('--generate_ui_profiles', action='store_true')
    arg_parser.add_argument('--generate_mapping', action='store_true')
    arg_parser.add_argument('--generate_old_format', action='store_true')
    return arg_parser


def remove_reserved_characters(file_name):
    return file_name.translate({ord(c): None for c in WINDOWS_RESERVED_CHARACTERS})


def write_ui_profiles_to_files(profiles: List[UIProfile] | ValuesView[UIProfile], folder: str = "ui-profiles"):
    for profile in profiles:
        with open(
                folder + "/" + remove_reserved_characters(profile.name).replace(" ", "_").replace(".", "_") + ".json",
                'w', encoding="utf-8") as f:
            f.write(profile.to_json())
    f.close()


def write_mappings_to_files(mappings, mapping_folder="mapping"):
    for mapping in mappings:
        if isinstance(mapping, CQLMapping):
            mapping_dir = f"{mapping_folder}/cql/"
        elif isinstance(mapping, FhirMapping):
            mapping_dir = f"{mapping_folder}/fhir/"
        elif isinstance(mapping, PathlingMapping):
            mapping_dir = f"{mapping_folder}/pathling/"
        else:
            raise ValueError("Mapping type not supported" + str(type(mapping)))
        with open(mapping_dir + mapping.name + ".json", 'w', encoding="utf-8") as f:
            f.write(mapping.to_json())
    f.close()


def write_mapping_tree_to_file(tree, mapping_tree_folder="mapping-tree"):
    with open(mapping_tree_folder + "/mapping_tree.json", 'w', encoding="utf-8") as f:
        f.write(tree.to_json())
    f.close()


def write_v1_mapping_to_file(mapping, mapping_folder="mapping-old"):
    if isinstance(mapping.entries[0], CQLMapping):
        mapping_file = f"{mapping_folder}/cql/mapping_cql.json"
    elif isinstance(mapping.entries[0], FhirMapping):
        mapping_file = f"{mapping_folder}/fhir/mapping_fhir.json"
    elif isinstance(mapping.entries[0], PathlingMapping):
        mapping_file = f"{mapping_folder}/pathling/mapping_pathling.json"
    else:
        raise ValueError("Mapping type not supported" + str(type(mapping)))
    with open(mapping_file, 'w', encoding="utf-8") as f:
        f.write(mapping.to_json())
    f.close()


def reformat_diagnosis_tree(ui_tree):
    for child in ui_tree.children:
        child.selectable = False
    return ui_tree


def reformate_medicaiton_tree(ui_tree):
    for child in ui_tree.children:
        child.selectable = False
    return ui_tree


def reformat_lab_tree(ui_tree):
    return ui_tree()


def reformate_consent_tree(ui_tree):
    for child in ui_tree.children:
        child.selectable = False
    return ui_tree


def reformate_procedure_tree(ui_tree):
    for child in ui_tree.children:
        child.selectable = False
    return ui_tree


def update_patient_gender_ui_profile(ui_profile: UIProfile) -> UIProfile:
    # Probably the wrong way of doing it. Gender should be mandatory by default. But due to bad design decisions
    # in the past, we now do it this way until people understand that it makes no sense to query the existence of
    # mandatory fields...
    ui_profile.valueDefinition.optional = False
    return ui_profile


def update_patient_age_ui_profile(ui_profile: UIProfile) -> UIProfile:
    # Probably the wrong way of doing it. Age should be mandatory by default. But due to bad design decisions
    # in the past, we now do it this way until people understand that it makes no sense to query the existence of
    # mandatory fields...
    ui_profile.valueDefinition.optional = False
    return ui_profile


def apply_additional_tree_rules(ui_tree):
    term_code_reformat_map = {
        TermCode("fdpg.mii.cds", "Laboruntersuchung", "Laboruntersuchung"): reformat_lab_tree,
        TermCode("fdpg.mii.cds", "Diagnose", "Diagnose"): reformat_diagnosis_tree,
        TermCode("fdpg.mii.cds", "Medikamentenverabreichung", "Medikamentenverabreichung"
                 ): reformate_medicaiton_tree,
        TermCode("fdpg.mii.cds", "Einwilligung", "Einwilligung"): reformate_consent_tree,
        TermCode("fdpg.mii.cds", "Prozedur", "Prozedur"): reformate_procedure_tree
    }
    reformat_function = term_code_reformat_map.get(ui_tree.termCode)
    if reformat_function is not None:
        return reformat_function(ui_tree)
    else:
        return ui_tree


def get_combined_consent_fhir_mapping():
    combined_consent_fhir_mapping = FhirMapping("CombinedConsent")
    combined_consent_fhir_mapping.key = TermCode("fdpg.mii.cds", "combined-consent",
                                                 "Einwilligung für die zentrale Datenanalyse")
    combined_consent_fhir_mapping.context = TermCode("fdpg.mii.cds", "Einwilligung", "Einwilligung")
    combined_consent_fhir_mapping.fhirResourceType = "Consent"
    combined_consent_fhir_mapping.timeRestrictionParameter = "date"
    combined_consent_fhir_mapping.fixedCriteria = get_combined_fhir_search_consent_fixed_critieria()
    return combined_consent_fhir_mapping


def get_combined_consent_cql_mapping():
    combined_consent_cql_mapping = CQLMapping("CombinedConsent")
    combined_consent_cql_mapping.timeRestrictionFhirPath = "Consent.datetime"
    combined_consent_cql_mapping.fhirResourceType = "Consent"
    primaryCode = TermCode("http://loinc.org", "54133-1", "Consent Document")
    combined_consent_cql_mapping.primaryCode = primaryCode
    combined_consent_cql_mapping.fixedCriteria = get_combined_cql_consent_fixed_critieria()
    return combined_consent_cql_mapping


def get_combined_fhir_search_consent_fixed_critieria():
    active = TermCode("http://hl7.org/fhir/consent-state-codes", "active", "Active")
    active_fixed_criteria = FixedFHIRCriteria("code", "status", [active])

    consent_system = "urn:oid:2.16.840.1.113883.3.1937.777.24.5.3"
    idat_bereitstellen_eu_dsgvo_niveau_code = "2.16.840.1.113883.3.1937.777.24.5.3.5"
    idat_bereitstellen_eu_dsgvo_niveau_display = "IDAT bereitstellen EU DSGVO NIVEAU"
    idat_bereitstellen_eu_dsgvo_niveau = TermCode(consent_system, idat_bereitstellen_eu_dsgvo_niveau_code,
                                                  idat_bereitstellen_eu_dsgvo_niveau_display)
    idat_bereitstellen_eu_dsgvo_niveau_fixed_critiera = FixedFHIRCriteria("coding", "mii-provision-provision-code",
                                                                          [idat_bereitstellen_eu_dsgvo_niveau])
    idat_erheben_code = "2.16.840.1.113883.3.1937.777.24.5.3.2"
    idat_erheben_display = "IDAT erheben"
    idat_erhben = TermCode(consent_system, idat_erheben_code, idat_erheben_display)
    idat_erheben_fixed_critiera = FixedFHIRCriteria("coding", "mii-provision-provision-code",
                                                    [idat_erhben])
    idat_speichern_verarbeiten_code = "2.16.840.1.113883.3.1937.777.24.5.3.3"
    idat_speichern_verarbeiten_display = "IDAT speichern/verarbeiten"
    idat_speichern_verarbeiten = TermCode(consent_system, idat_speichern_verarbeiten_code,
                                          idat_speichern_verarbeiten_display)
    idat_speichern_verarbeiten_fixed_critiera = FixedFHIRCriteria("coding", "mii-provision-provision-code",
                                                                  [idat_speichern_verarbeiten])
    idat_zusammenfuehren_dritte_code = "2.16.840.1.113883.3.1937.777.24.5.3.4"
    idat_zusammenfuehren_dritte_display = "IDAT zusammenfuehren mit Dritte"
    idat_zusammenfuehren_dritte = TermCode(consent_system, idat_zusammenfuehren_dritte_code,
                                           idat_zusammenfuehren_dritte_display)
    idat_zusammenfuehren_dritte_fixed_critiera = FixedFHIRCriteria("coding", "mii-provision-provision-code",
                                                                   [idat_zusammenfuehren_dritte])
    mdat_erheben_code = "2.16.840.1.113883.3.1937.777.24.5.3.6"
    mdat_erheben_display = "MDAT erheben"
    mdat_erheben = TermCode(consent_system, mdat_erheben_code, mdat_erheben_display)
    mdat_erheben_fixed_critiera = FixedFHIRCriteria("coding", "mii-provision-provision-code", [mdat_erheben])

    mdat_speichern_verarbeiten_code = "2.16.840.1.113883.3.1937.777.24.5.3.7"
    mdat_speichern_verarbeiten_display = "MDAT speichern/verarbeiten"
    mdat_speichern_verarbeiten = TermCode(consent_system, mdat_speichern_verarbeiten_code,
                                          mdat_speichern_verarbeiten_display)
    mdat_speichern_verarbeiten_fixed_critiera = FixedFHIRCriteria("coding", "mii-provision-provision-code",
                                                                  [mdat_speichern_verarbeiten])
    mdat_wissenschaftlich_nutzen_eu_dsgvo_niveau_code = "2.16.840.1.113883.3.1937.777.24.5.3.8"
    mdat_wissenschaftlich_nutzen_eu_dsgvo_niveau_display = "MDAT wissenschaftlich nutzen EU DSGVO NIVEAU"
    mdat_wissenschaftlich_nutzen_eu_dsgvo_niveau = TermCode(consent_system,
                                                            mdat_wissenschaftlich_nutzen_eu_dsgvo_niveau_code,
                                                            mdat_wissenschaftlich_nutzen_eu_dsgvo_niveau_display)
    mdat_wissenschaftlich_nutzen_eu_dsgvo_niveau_fixed_critiera = FixedFHIRCriteria("coding",
                                                                                    "mii-provision-provision-code",
                                                                                    [
                                                                                        mdat_wissenschaftlich_nutzen_eu_dsgvo_niveau])

    mdat_zusammenfuehren_dritte_code = "2.16.840.1.113883.3.1937.777.24.5.3.9"
    mdat_zusammenfuehren_dritte_display = "MDAT zusammenfuehren mit Dritte"
    mdat_zusammenfuehren_dritte = TermCode(consent_system, mdat_zusammenfuehren_dritte_code,
                                           mdat_zusammenfuehren_dritte_display)
    mdat_zusammenfuehren_dritte_fixed_critiera = FixedFHIRCriteria("coding", "mii-provision-provision-code",
                                                                   [mdat_zusammenfuehren_dritte])

    # patdat_erheben_speichern_nutzen_code = "2.16.840.1.113883.3.1937.777.24.5.3.1"
    # patdat_erheben_speichern_nutzen_display = "PATDAT erheben/speichern/nutzen"
    # patdat_erheben_speichern_nutzen = TermCode(consent_system, patdat_erheben_speichern_nutzen_code,
    #                                            patdat_erheben_speichern_nutzen_display)
    # patdat_erheben_speichern_nutzen_fixed_critiera = FixedCriteria("coding", "mii-provision-provision-code",
    #                                                                "provision.provision.code",
    #                                                                [patdat_erheben_speichern_nutzen])
    # rekontaktierung_ergaenzungen_code = "2.16.840.1.113883.3.1937.777.24.5.3.26"
    # rekontaktierung_ergaenzungen_display = "Rekontaktierung/Ergaenzungen"
    # rekontaktierung_ergaenzungen = TermCode(consent_system, rekontaktierung_ergaenzungen_code,
    #                                         rekontaktierung_ergaenzungen_display)
    # rekontaktierung_ergaenzungen_fixed_critiera = FixedCriteria("coding", "mii-provision-provision-code",
    #                                                             "provision.provision.code",
    #                                                             [rekontaktierung_ergaenzungen])

    return [active_fixed_criteria, idat_bereitstellen_eu_dsgvo_niveau_fixed_critiera, idat_erheben_fixed_critiera,
            idat_speichern_verarbeiten_fixed_critiera, idat_zusammenfuehren_dritte_fixed_critiera,
            mdat_erheben_fixed_critiera, mdat_speichern_verarbeiten_fixed_critiera,
            mdat_wissenschaftlich_nutzen_eu_dsgvo_niveau_fixed_critiera, mdat_zusammenfuehren_dritte_fixed_critiera]


def get_combined_cql_consent_fixed_critieria():
    active = TermCode("http://hl7.org/fhir/consent-state-codes", "active", "Active")
    active_fixed_criteria = FixedFHIRCriteria("code", "status", [active])

    consent_system = "urn:oid:2.16.840.1.113883.3.1937.777.24.5.3"
    idat_bereitstellen_eu_dsgvo_niveau_code = "2.16.840.1.113883.3.1937.777.24.5.3.5"
    idat_bereitstellen_eu_dsgvo_niveau_display = "IDAT bereitstellen EU DSGVO NIVEAU"
    idat_bereitstellen_eu_dsgvo_niveau = TermCode(consent_system, idat_bereitstellen_eu_dsgvo_niveau_code,
                                                  idat_bereitstellen_eu_dsgvo_niveau_display)
    idat_bereitstellen_eu_dsgvo_niveau_fixed_critiera = FixedFHIRCriteria("Coding",
                                                                          "mii-provision-provision-code.coding",
                                                                          [idat_bereitstellen_eu_dsgvo_niveau])
    idat_erheben_code = "2.16.840.1.113883.3.1937.777.24.5.3.2"
    idat_erheben_display = "IDAT erheben"
    idat_erhben = TermCode(consent_system, idat_erheben_code, idat_erheben_display)
    idat_erheben_fixed_critiera = FixedFHIRCriteria("Coding", "mii-provision-provision-code.coding",
                                                    [idat_erhben])
    idat_speichern_verarbeiten_code = "2.16.840.1.113883.3.1937.777.24.5.3.3"
    idat_speichern_verarbeiten_display = "IDAT speichern/verarbeiten"
    idat_speichern_verarbeiten = TermCode(consent_system, idat_speichern_verarbeiten_code,
                                          idat_speichern_verarbeiten_display)
    idat_speichern_verarbeiten_fixed_critiera = FixedFHIRCriteria("Coding", "mii-provision-provision-code.coding",
                                                                  [idat_speichern_verarbeiten])
    idat_zusammenfuehren_dritte_code = "2.16.840.1.113883.3.1937.777.24.5.3.4"
    idat_zusammenfuehren_dritte_display = "IDAT zusammenfuehren mit Dritte"
    idat_zusammenfuehren_dritte = TermCode(consent_system, idat_zusammenfuehren_dritte_code,
                                           idat_zusammenfuehren_dritte_display)
    idat_zusammenfuehren_dritte_fixed_critiera = FixedFHIRCriteria("Coding", "mii-provision-provision-code.coding",
                                                                   [idat_zusammenfuehren_dritte])
    mdat_erheben_code = "2.16.840.1.113883.3.1937.777.24.5.3.6"
    mdat_erheben_display = "MDAT erheben"
    mdat_erheben = TermCode(consent_system, mdat_erheben_code, mdat_erheben_display)
    mdat_erheben_fixed_critiera = FixedFHIRCriteria("Coding", "mii-provision-provision-code.coding", [mdat_erheben])

    mdat_speichern_verarbeiten_code = "2.16.840.1.113883.3.1937.777.24.5.3.7"
    mdat_speichern_verarbeiten_display = "MDAT speichern/verarbeiten"
    mdat_speichern_verarbeiten = TermCode(consent_system, mdat_speichern_verarbeiten_code,
                                          mdat_speichern_verarbeiten_display)
    mdat_speichern_verarbeiten_fixed_critiera = FixedFHIRCriteria("Coding", "mii-provision-provision-code.coding",
                                                                  [mdat_speichern_verarbeiten])
    mdat_wissenschaftlich_nutzen_eu_dsgvo_niveau_code = "2.16.840.1.113883.3.1937.777.24.5.3.8"
    mdat_wissenschaftlich_nutzen_eu_dsgvo_niveau_display = "MDAT wissenschaftlich nutzen EU DSGVO NIVEAU"
    mdat_wissenschaftlich_nutzen_eu_dsgvo_niveau = TermCode(consent_system,
                                                            mdat_wissenschaftlich_nutzen_eu_dsgvo_niveau_code,
                                                            mdat_wissenschaftlich_nutzen_eu_dsgvo_niveau_display)
    mdat_wissenschaftlich_nutzen_eu_dsgvo_niveau_fixed_critiera = FixedFHIRCriteria("Coding",
                                                                                    "mii-provision-provision-code.coding",
                                                                                    [
                                                                                        mdat_wissenschaftlich_nutzen_eu_dsgvo_niveau])

    mdat_zusammenfuehren_dritte_code = "2.16.840.1.113883.3.1937.777.24.5.3.9"
    mdat_zusammenfuehren_dritte_display = "MDAT zusammenfuehren mit Dritte"
    mdat_zusammenfuehren_dritte = TermCode(consent_system, mdat_zusammenfuehren_dritte_code,
                                           mdat_zusammenfuehren_dritte_display)
    mdat_zusammenfuehren_dritte_fixed_critiera = FixedFHIRCriteria("Coding", "mii-provision-provision-code.coding",
                                                                   [mdat_zusammenfuehren_dritte])

    # patdat_erheben_speichern_nutzen_code = "2.16.840.1.113883.3.1937.777.24.5.3.1"
    # patdat_erheben_speichern_nutzen_display = "PATDAT erheben/speichern/nutzen"
    # patdat_erheben_speichern_nutzen = TermCode(consent_system, patdat_erheben_speichern_nutzen_code,
    #                                            patdat_erheben_speichern_nutzen_display)
    # patdat_erheben_speichern_nutzen_fixed_critiera = FixedCriteria("coding", "mii-provision-provision-code.coding",
    #                                                                "provision.provision.code",
    #                                                                [patdat_erheben_speichern_nutzen])
    # rekontaktierung_ergaenzungen_code = "2.16.840.1.113883.3.1937.777.24.5.3.26"
    # rekontaktierung_ergaenzungen_display = "Rekontaktierung/Ergaenzungen"
    # rekontaktierung_ergaenzungen = TermCode(consent_system, rekontaktierung_ergaenzungen_code,
    #                                         rekontaktierung_ergaenzungen_display)
    # rekontaktierung_ergaenzungen_fixed_critiera = FixedCriteria("coding", "mii-provision-provision-code.coding",
    #                                                             "provision.provision.code",
    #                                                             [rekontaktierung_ergaenzungen])

    return [active_fixed_criteria, idat_bereitstellen_eu_dsgvo_niveau_fixed_critiera, idat_erheben_fixed_critiera,
            idat_speichern_verarbeiten_fixed_critiera, idat_zusammenfuehren_dritte_fixed_critiera,
            mdat_erheben_fixed_critiera, mdat_speichern_verarbeiten_fixed_critiera,
            mdat_wissenschaftlich_nutzen_eu_dsgvo_niveau_fixed_critiera, mdat_zusammenfuehren_dritte_fixed_critiera]


def apply_additional_profile_rules(named_profile: Tuple[str, UIProfile]):
    ui_profile_reformat_map = {
        "Person1": update_patient_gender_ui_profile,
        "Person": update_patient_age_ui_profile
    }
    reformat_function = ui_profile_reformat_map.get(named_profile[0])
    if reformat_function is not None:
        return reformat_function(named_profile[1])
    else:
        return named_profile[1]


if __name__ == '__main__':
    client = docker.from_env()
    # Check if container with the name "test_db" already exists
    existing_containers = client.containers.list(all=True, filters={"name": "test_db"})

    for container in existing_containers:
        print("Stopping and removing existing container named 'test_db'...")
        container.stop()
        container.remove()

    container = client.containers.run("postgres:latest", detach=True, ports={'5432/tcp': 5430},
                                      name="test_db",
                                      volumes={f"{os.getcwd()}": {'bind': '/opt/db_data', 'mode': 'rw'}},
                                      environment={
                                          'POSTGRES_USER': 'codex-postgres',
                                          'POSTGRES_PASSWORD': 'codex-password',
                                          'POSTGRES_DB': 'codex_ui'
                                      })
    db_writer = DataBaseWriter(5430)

    parser = configure_args_parser()
    args = parser.parse_args()

    generate_result_folder()

    # Download the packages
    if args.download_packages:
        download_simplifier_packages(core_data_sets)
    # ----Time consuming: Only execute initially or on changes----
    if args.generate_snapshot:
        # generate_snapshots("resources/core_data_sets")
        generate_snapshots("resources/fdpg_differential", core_data_sets)
    # -------------------------------------------------------------

    # You shouldn't need different implementations for the different generators
    resolver = MIICoreDataSetQueryingMetaDataResolver()

    if args.generate_ui_trees:
        tree_generator = UITreeGenerator(resolver)
        ui_trees = tree_generator.generate_ui_trees("resources/fdpg_differential")
        # ui_trees = [apply_additional_tree_rules(ui_tree) for ui_tree in ui_trees]
        write_ui_trees_to_files(ui_trees)

        term_code_context_infos = tree_generator.generate_contextualized_term_code_info_list("resources/fdpg_differential")
        print(term_code_context_infos.__len__())

        for term_code_context_info in term_code_context_infos:
            for tree_map_list in ui_trees:
                if term_code_context_info.entries:
                    if term_code_context_info.entries[0].module.display == tree_map_list.module_name:
                        term_code_context_info.update_children_count(tree_map_list)

        write_term_code_info_to_file(term_code_context_infos)

        # validate_mapping_tree("mapping_tree")

    if args.generate_ui_profiles:
        profile_generator = UIProfileGenerator(resolver)
        contextualized_term_code_ui_profile_mapping, named_ui_profiles_dict = \
            profile_generator.generate_ui_profiles("resources/fdpg_differential")
        named_ui_profiles_dict = {name: apply_additional_profile_rules((name, profile)) for name, profile in
                                  named_ui_profiles_dict.items()}
        write_ui_profiles_to_files(named_ui_profiles_dict.values())
        write_used_value_sets_to_files(named_ui_profiles_dict.values())
        write_used_criteria_sets_to_files(named_ui_profiles_dict.values())
        db_writer.write_ui_profiles_to_db(contextualized_term_code_ui_profile_mapping, named_ui_profiles_dict)
        db_writer.write_vs_to_db(named_ui_profiles_dict.values())

        result = container.exec_run(
            'pg_dump --dbname="codex_ui" -U codex-postgres -a -O -t termcode -t context -t ui_profile -t mapping'
            ' -t contextualized_termcode -t contextualized_termcode_to_criteria_set -t criteria_set -f /opt/db_data/R__Load_latest_ui_profile.sql')

    if args.generate_mapping:
        cql_generator = CQLMappingGenerator(resolver)
        cql_mappings = cql_generator.generate_mapping("resources/fdpg_differential")
        cql_term_code_mappings = cql_mappings[0]
        cql_concept_mappings = cql_mappings[1]
        write_mappings_to_files(cql_concept_mappings.values())
        v1_cql_mappings = denormalize_mapping_to_old_format(cql_term_code_mappings, cql_concept_mappings)
        write_v1_mapping_to_file(v1_cql_mappings, "mapping-old")

        # pathling_generator = PathlingMappingGenerator(resolver)
        # pathling_mappings = pathling_generator.generate_mapping("resources/fdpg_differential")
        # pathling_term_code_mappings = pathling_mappings[0]
        # pathling_concept_mappings = pathling_mappings[1]
        # write_mappings_to_files(pathling_concept_mappings.values())
        # v1_pathling_mappings = denormalize_mapping_to_old_format(pathling_term_code_mappings, pathling_concept_mappings)
        # write_v1_mapping_to_file(v1_pathling_mappings, "mapping-old")

        search_param_resolver = MIICoreDataSetSearchParameterResolver()
        fhir_search_generator = FHIRSearchMappingGenerator(resolver, search_param_resolver)
        fhir_search_term_code_mappings, fhir_search_concept_mappings = fhir_search_generator.generate_mapping(
            "resources/fdpg_differential")
        # write_mapping_to_db(db_writer, fhir_search_term_code_mappings, fhir_search_concept_mappings, "FHIR_SEARCH",
        #                     args.generate_ui_profiles)

        v1_fhir_search_mapping = denormalize_mapping_to_old_format(fhir_search_term_code_mappings,
                                                                   fhir_search_concept_mappings)
        v1_fhir_search_mapping.entries.append(get_combined_consent_fhir_mapping())
        write_v1_mapping_to_file(v1_fhir_search_mapping, "mapping-old")
        validate_fhir_mapping("mapping_fhir")


    print("Dumped db")
    container.stop()
    container.remove()

    # core_data_category_entries = generate_core_data_set()
    #
    # for core_data_category_entry in core_data_category_entries:
    #     write_cds_ui_profile(core_data_category_entry)
    #     validate_ui_profile(core_data_category_entry.display)

    # move_back_other(category_entries)
    #
    # category_entries += core_data_category_entries
    # dbw = DataBaseWriter()
    # dbw.add_ui_profiles_to_db(category_entries)
    # generate_term_code_mapping(category_entries)
    # generate_term_code_tree(category_entries)
    # if args.generate_csv:
    #     to_csv(category_entries)

    # dump data from db with
    # docker exec -t 7ac5bfb77395 pg_dump --dbname="codex_ui" --username=codex-postgres
    # --table=UI_PROFILE_TABLE > ui_profile_dump_230822
