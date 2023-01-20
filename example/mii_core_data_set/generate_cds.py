from __future__ import annotations

import argparse
from typing import List, ValuesView, Dict

from lxml import etree

from FHIRProfileConfiguration import *
from api.CQLMappingGenerator import CQLMappingGenerator
from api.FHIRSearchMappingGenerator import FHIRSearchMappingGenerator
from api.ResourceQueryingMetaDataResolver import ResourceQueryingMetaDataResolver
from api.StrucutureDefinitionParser import get_element_from_snapshot
from api.UIProfileGenerator import UIProfileGenerator
from api.UITreeGenerator import UITreeGenerator
from helper import download_simplifier_packages, generate_snapshots, write_object_as_json, load_querying_meta_data, \
    generate_result_folder
from model.MappingDataModel import CQLMapping, FhirMapping
from model.ResourceQueryingMetaData import ResourceQueryingMetaData
from model.UIProfileModel import UIProfile
from model.UiDataModel import TermEntry, TermCode

core_data_sets = [MII_CONSENT, MII_DIAGNOSE, MII_LAB, MII_MEDICATION, MII_PERSON, MII_PROCEDURE, MII_SPECIMEN]
WINDOWS_RESERVED_CHARACTERS = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']


class MIICoreDataSetQueryingMetaDataResolver(ResourceQueryingMetaDataResolver):
    def __init__(self):
        super().__init__()

    def get_query_meta_data(self, fhir_profile_snapshot: dict, context: TermCode) -> List[ResourceQueryingMetaData]:
        query_meta_data = self._get_query_meta_data_by_context(fhir_profile_snapshot, context)
        if not query_meta_data:
            query_meta_data = self._get_query_meta_data_by_snapshot(fhir_profile_snapshot)
            if not query_meta_data:
                print(
                    f"No query meta data found for profile: {fhir_profile_snapshot.get('name')} and context: {context}")
        if len(query_meta_data) > 1:
            print(f"Multiple query meta data found for profile: {fhir_profile_snapshot.get('name')} and  context: "
                  f"{context}")
            query_meta_data = self._filter_query_meta_data(query_meta_data, fhir_profile_snapshot)
        return query_meta_data

    @staticmethod
    def _get_query_meta_data_by_context(fhir_profile_snapshot: dict, context: TermCode) -> \
            List[ResourceQueryingMetaData]:
        return [resource_querying_meta_data for resource_querying_meta_data
                in load_querying_meta_data("resources/QueryingMetaData") if
                resource_querying_meta_data.context == context and
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
        print(result)
        return result if result else query_meta_data


def generate_top_300_loinc_tree():
    top_loinc_tree = etree.parse("resources/additional_resources/Top300Loinc.xml")
    terminology_entry = TermEntry([TermCode("fdpg.mii.cds", "Laboruntersuchung", "Laboruntersuchung")])
    terminology_entry.children = sorted(get_terminology_entry_from_top_300_loinc("11ccdc84-a237-49a5-860a-b0f65068c023",
                                                                                 top_loinc_tree).children)
    terminology_entry.leaf = False
    terminology_entry.selectable = False
    return terminology_entry


def get_terminology_entry_from_top_300_loinc(element_id, element_tree):
    """
    Generates the top 300 loinc tree for the given element id and tree
    :param element_id: the id of the root element of the sub tree initially the id of the root element of the whole tree
    :param element_tree: the element subtree
    :return: Terminology tree
    """
    # TODO: Better namespace handling
    terminology_entry = None
    for element in element_tree.xpath("/xmlns:export/xmlns:scopedIdentifier",
                                      namespaces={'xmlns': "http://schema.samply.de/mdr/common"}):
        if element.get("uuid") == element_id:
            display = get_top_300_display(element)
            if subs := element.xpath("xmlns:sub", namespaces={'xmlns': "http://schema.samply.de/mdr/common"}):
                term_code = TermCode("fdpg.mii.cds", display, display)
                terminology_entry = TermEntry([term_code])
                for sub in subs:
                    terminology_entry.children.append(get_terminology_entry_from_top_300_loinc(sub.text, element_tree))
                    terminology_entry.leaf = False
                    terminology_entry.selectable = False
                terminology_entry.children = sorted(terminology_entry.children)
                return terminology_entry
            term_code = get_term_code(element, display)
            terminology_entry = TermEntry([term_code])
    return terminology_entry


# We already extracted the display from the element, so we don't need to do it again
def get_term_code(element, display):
    """
    Extracts the term code from the element
    :param element: node in the XML tree
    :param display: display of the term code
    :return: TermCode
    """
    coding_system = ""
    code = ""
    for slot in element.xpath("xmlns:slots/xmlns:slot",
                              namespaces={'xmlns': "http://schema.samply.de/mdr/common"}):
        next_is_coding_system = False
        next_is_code = False
        for child in slot:
            if (child.tag == "{http://schema.samply.de/mdr/common}key") and (
                    child.text == "fhir-coding-system"):
                next_is_coding_system = True
            if (child.tag == "{http://schema.samply.de/mdr/common}value") and next_is_coding_system:
                coding_system = child.text
                next_is_coding_system = False
            if (child.tag == "{http://schema.samply.de/mdr/common}key") and (child.text == "terminology-code"):
                next_is_code = True
            if (child.tag == "{http://schema.samply.de/mdr/common}value") and next_is_code:
                code = child.text
                next_is_code = False
    return TermCode(coding_system, code, display)


def get_top_300_display(element):
    """
    Extracts the display from the element if a german display is available it is used otherwise the english display is
    :param element: the element
    :return: the display
    """
    display = None
    for definition in element.xpath("xmlns:definitions/xmlns:definition",
                                    namespaces={'xmlns': "http://schema.samply.de/mdr/common"}):
        if definition.get("lang") == "de":
            for designation in (
                    definition.xpath("xmlns:designation",
                                     namespaces={'xmlns': "http://schema.samply.de/mdr/common"})):
                return designation.text
        if definition.get("lang") == "en":
            for designation in (
                    definition.xpath("xmlns:designation",
                                     namespaces={'xmlns': "http://schema.samply.de/mdr/common"})):
                display = designation.text
    if display:
        return display
    else:
        raise Exception("No display found for element " + element.get("uuid"))


def generate_term_code_mapping(_entries: List[TermEntry]):
    """
    Generates the term code mapping for the given entries and saves it in the mapping folder
    :param _entries: TermEntries to generate the mapping for
    """
    pass


def generate_term_code_tree(_entries: List[TermEntry]):
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


def write_ui_trees_to_files(trees: List[TermEntry], directory: str = "ui-trees"):
    """
    Writes the ui trees to the ui-profiles folder
    :param trees: ui trees to write
    :param directory: directory to write the ui trees to
    """
    for tree in trees:
        write_object_as_json(tree, f"{directory}/{tree.display}.json")


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


def denormalize_to_old_format(ui_tree: List[TermEntry], term_code_to_profile_name: Dict[TermCode, str],
                              ui_profile_name_to_profile: Dict[str, UIProfile]):
    """
    Denormalizes the ui tree and ui profiles to the old format

    :param ui_tree: entries to denormalize
    :param term_code_to_profile_name: mapping from term codes to profile names
    :param ui_profile_name_to_profile: ui profiles to use
    :return: denormalized entries
    """
    for entry in ui_tree:
        if entry.selectable:
            try:
                ui_profile = ui_profile_name_to_profile[term_code_to_profile_name[entry.termCode]]
                entry.to_v1_entry(ui_profile)
            except KeyError:
                print("No profile found for term code " + entry.termCode.code)
        for child in entry.children:
            denormalize_to_old_format([child], term_code_to_profile_name, ui_profile_name_to_profile)


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


def write_mappings_to_files(mappings):
    for mapping in mappings:
        if isinstance(mapping, CQLMapping):
            mapping_dir = "mapping/cql/"
        elif isinstance(mapping, FhirMapping):
            mapping_dir = "mapping/fhir/"
        else:
            raise ValueError("Mapping type not supported" + str(type(mapping)))
        with open(mapping_dir + mapping.name + ".json", 'w', encoding="utf-8") as f:
            f.write(mapping.to_json())
    f.close()


if __name__ == '__main__':

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
        top_300_loinc_tree = generate_top_300_loinc_tree()
        # replace ui tree for loinc with the top 300 loinc tree
        ui_trees = [ui_tree if ui_tree.termCode != top_300_loinc_tree.termCode else top_300_loinc_tree for ui_tree
                    in ui_trees]
        write_ui_trees_to_files(ui_trees)

    if args.generate_ui_profiles:
        profile_generator = UIProfileGenerator(resolver)
        ui_profiles = profile_generator.generate_ui_profiles("resources/fdpg_differential")[1].values()
        write_ui_profiles_to_files(ui_profiles)

    if args.generate_mapping:
        cql_generator = CQLMappingGenerator(resolver)
        cql_concept_mappings = cql_generator.generate_mapping("resources/fdpg_differential")[1].values()
        write_mappings_to_files(cql_concept_mappings)

        fhir_search_generator = FHIRSearchMappingGenerator(resolver)
        fhir_search_mappings = fhir_search_generator.generate_mapping("resources/fdpg_differential")[1].values()
        write_mappings_to_files(fhir_search_mappings)

    if args.generate_old_format:
        tree_generator = UITreeGenerator(resolver)
        ui_trees = tree_generator.generate_ui_trees("resources/fdpg_differential")
        top_300_loinc_tree = generate_top_300_loinc_tree()
        # replace ui tree for loinc with the top 300 loinc tree
        ui_trees = [ui_tree if ui_tree.termCode != top_300_loinc_tree.termCode else top_300_loinc_tree for ui_tree
                    in ui_trees]
        profile_generator = UIProfileGenerator(resolver)
        ui_profiles = profile_generator.generate_ui_profiles("resources/fdpg_differential")
        term_code_to_ui_profile_name = {context_tc[1]: profile_name for context_tc, profile_name in
                                        ui_profiles[0].items()}
        denormalize_to_old_format(ui_trees, term_code_to_ui_profile_name, ui_profiles[1])
        write_ui_trees_to_files(ui_trees, "ui-profiles-old")

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
