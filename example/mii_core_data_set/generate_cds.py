from __future__ import annotations

import argparse
import os
from typing import List, ValuesView

from FHIRProfileConfiguration import *
from api.ResourceQueryingMetaDataResolver import ResourceQueryingMetaDataResolver
from api.UIProfileGenerator import UIProfileGenerator
from api.UITreeGenerator import UITreeGenerator
from api.CQLMappingGenerator import CQLMappingGenerator
from api.FHIRSearchMappingGenerator import FHIRSearchMappingGenerator
from helper import download_simplifier_packages, generate_snapshots, write_object_as_json, load_querying_meta_data
from main import generate_result_folder
from model.MappingDataModel import MapEntry
from model.ResourceQueryingMetaData import ResourceQueryingMetaData
from model.UIProfileModel import UIProfile
from model.UiDataModel import TermEntry, TermCode

core_data_sets = [MII_CONSENT, MII_DIAGNOSE, MII_LAB, MII_MEDICATION, MII_PERSON, MII_PROCEDURE, MII_SPECIMEN]


class MIICoreDataSetQueryingMetaDataResolver(ResourceQueryingMetaDataResolver):
    def __init__(self):
        super().__init__()

    def get_query_meta_data(self, fhir_profile_snapshot: dict, context: TermCode) -> List[ResourceQueryingMetaData]:
        query_meta_data = self._get_query_meta_data_by_context(fhir_profile_snapshot, context)
        return query_meta_data if query_meta_data else self._get_query_meta_data_by_snapshot(fhir_profile_snapshot)

    @staticmethod
    def _get_query_meta_data_by_context(fhir_profile_snapshot: dict, context: TermCode) -> \
            List[ResourceQueryingMetaData]:
        return [resource_querying_meta_data for resource_querying_meta_data
                in load_querying_meta_data("resources/QueryingMetaData") if
                resource_querying_meta_data.context == context and
                resource_querying_meta_data.resource_type == fhir_profile_snapshot["type"]]

    @staticmethod
    def _get_query_meta_data_by_snapshot(fhir_profile_snapshot: dict) -> List[ResourceQueryingMetaData]:
        context = TermCode("fdpg.mii.cds", fhir_profile_snapshot["baseDefinition"].split("/")[-1],
                           fhir_profile_snapshot["baseDefinition"].split("/")[-1])
        return [resource_querying_meta_data for resource_querying_meta_data
                in load_querying_meta_data("resources/QueryingMetaData") if
                resource_querying_meta_data.resource_type == fhir_profile_snapshot["type"]
                and resource_querying_meta_data.context == context]


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


def get_profile_snapshot_from_module(module: str) -> List[str]:
    """
    Returns the FHIR profiles of the given module
    :param module: name of the module
    :return: List of the FHIR profiles snapshot paths in the module
    """
    return [f"resources/core_data_sets/{module}/package/{f.name}" for f in
            os.scandir(f"resources/core_data_sets/{module}/package") if
            not f.is_dir() and "-snapshot" in f.name]


def get_module_category_entry_from_module_name(module: str) -> TermEntry:
    module_name = module.split(' ')[0].split(".")[-1].capitalize()
    module_code = TermCode("fdpg.mii.cds", module_name, module_name)
    return TermEntry([module_code], "Category", selectable=False, leaf=False)


def write_ui_trees_to_files(trees: List[TermEntry]):
    """
    Writes the ui trees to the ui-profiles folder
    :param trees: ui trees to write
    """
    for tree in trees:
        write_object_as_json(tree, f"ui-profiles/{tree.display}.json")


# Todo: this should be an abstract method that has to be implemented for each use-case
# Todo: move this concrete implementation elsewhere


def write_cds_ui_profile(module_category_entry):
    """
    Writes the ui profile for the given module category entry to the ui-profiles folder
    :param module_category_entry: name of the module category entry
    """
    f = open("ui-trees/" + module_category_entry.display + ".json", 'w', encoding="utf-8")
    if len(module_category_entry.children) == 1:
        f.write(module_category_entry.children[0].to_json())
    else:
        f.write(module_category_entry.to_json())
    f.close()


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
    return arg_parser


def write_ui_profiles_to_files(profiles: List[UIProfile] | ValuesView[UIProfile]):
    for profile in profiles:
        with open("ui-profiles/" + profile.name + ".json", 'w', encoding="utf-8") as f:
            f.write(profile.to_json())
    f.close()


def write_mappings_to_files(_mappings) -> List[MapEntry]:
    pass


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
        write_ui_trees_to_files(ui_trees)

    if args.generate_ui_profiles:
        profile_generator = UIProfileGenerator(resolver)
        ui_profiles = profile_generator.generate_ui_profiles("resources/fdpg_differential")[1].values()
        write_ui_profiles_to_files(ui_profiles)

    if args.generate_mapping:
        cql_generator = CQLMappingGenerator(resolver)
        cql_concept_mappings = cql_generator.generate_mapping("resources/fdpg_differential")
        write_mappings_to_files(cql_concept_mappings)

        fhir_search_generator = FHIRSearchMappingGenerator(resolver)
        fhir_search_mappings = fhir_search_generator.generate_mapping("resources/fdpg_differential")
        write_mappings_to_files(fhir_search_mappings)

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
