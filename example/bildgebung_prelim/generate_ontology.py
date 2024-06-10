from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import logging
from typing import List, ValuesView, Dict

import docker
from jsonschema import validate

from core.CQLMappingGenerator import CQLMappingGenerator
from core.FHIRSearchMappingGenerator import FHIRSearchMappingGenerator
from core.ResourceQueryingMetaDataResolver import ResourceQueryingMetaDataResolver
from core.SearchParameterResolver import SearchParameterResolver
from core.UIProfileGenerator import UIProfileGenerator
from core.UITreeGenerator import UITreeGenerator
from database.DataBaseWriter import DataBaseWriter
from helper import download_simplifier_packages, generate_snapshots, write_object_as_json, mkdir_if_not_exists
from model.MappingDataModel import CQLMapping, FhirMapping, MapEntryList
from model.ResourceQueryingMetaData import ResourceQueryingMetaData
from model.UIProfileModel import UIProfile
from model.UiDataModel import TermEntry, TermCode
from model.termCodeTree import to_term_code_node

WINDOWS_RESERVED_CHARACTERS = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']

class StandardDataSetQueryingMetaDataResolver(ResourceQueryingMetaDataResolver):
    def __init__(self):
        super().__init__()

    def get_query_meta_data(self, fhir_profile_snapshot: dict, _context: TermCode) -> List[ResourceQueryingMetaData]:
        result = []
        profile_name = fhir_profile_snapshot.get("name")
        mapping = self._get_query_meta_data_mapping()
        for metadata_name in mapping[profile_name]:
            with open(f"resources/QueryingMetaData/{metadata_name}.json", "r") as file:
                result.append(ResourceQueryingMetaData.from_json(file))
        return result

    @staticmethod
    def _get_query_meta_data_mapping():
        with open("resources/profile_to_query_meta_data_resolver_mapping.json", "r") as f:
            return json.load(f)


class StandardSearchParameterResolver(SearchParameterResolver):
    def _load_module_search_parameters(self) -> List[Dict]:
        params = []
        for file in os.listdir("resources/search_parameter"):
            if file.endswith(".json"):
                with open(os.path.join("resources/search_parameter", file), "r", encoding="utf-8") as f:
                    params.append(json.load(f))
        return params


def generate_term_code_mapping(_entries: List[TermEntry]):
    pass


def generate_term_code_tree(_entries: List[TermEntry]):
    pass


def validate_ui_profile(_profile_name: str):
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
        print(tree.display)
        write_object_as_json(tree, f"{directory}/{tree.display}.json")


# Todo: this should be an abstract method that has to be implemented for each use-case
# Todo: move this concrete implementation elsewhere


def write_cds_ui_profile(module_category_entry):

    f = open("ui-profiles/" + module_category_entry.display + ".json", 'w', encoding="utf-8")
    if len(module_category_entry.children) == 1:
        f.write(module_category_entry.children[0].to_json())
    else:
        f.write(module_category_entry.to_json())
    f.close()


def denormalize_ui_profile_to_old_format(ui_tree: List[TermEntry], term_code_to_profile_name: Dict[TermCode, str],
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
            denormalize_ui_profile_to_old_format([child], term_code_to_profile_name, ui_profile_name_to_profile)


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
            result.entries.add(mapping)
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
    arg_parser = argparse.ArgumentParser(description='Generate the UI-Profile of the core data set for the MII-FDPG')
    arg_parser.add_argument('--download_packages', action='store_true')
    arg_parser.add_argument('--generate_snapshot', action='store_true')
    arg_parser.add_argument('--generate_ui_trees', action='store_true')
    arg_parser.add_argument('--generate_ui_profiles', action='store_true')
    arg_parser.add_argument('--generate_mapping', action='store_true')
    arg_parser.add_argument("--loglevel", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], default="INFO",
                        help="Set the log level")
    return arg_parser

def generate_result_folder(onto_dir = ""):
    """
    Generates the mapping, csv and ui-profiles folder if they do not exist in the result folder
    :return:
    """

    if onto_dir != "":
        onto_dir = f"{onto_dir}/"
        mkdir_if_not_exists(f"{onto_dir}")

    mkdir_if_not_exists(f"{onto_dir}mapping")
    mkdir_if_not_exists(f"{onto_dir}mapping-tree")
    mkdir_if_not_exists(f"{onto_dir}mapping")
    mkdir_if_not_exists(f"{onto_dir}mapping/fhir")
    mkdir_if_not_exists(f"{onto_dir}mapping/cql")
    mkdir_if_not_exists(f"{onto_dir}ui-trees")
    mkdir_if_not_exists(f"{onto_dir}csv")
    mkdir_if_not_exists(f"{onto_dir}ui-profiles")
    mkdir_if_not_exists(f"{onto_dir}ui-profiles-old")

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
        else:
            raise ValueError("Mapping type not supported" + str(type(mapping)))
        with open(mapping_dir + mapping.name + ".json", 'w', encoding="utf-8") as f:
            f.write(mapping.to_json())
    f.close()


def write_mapping_to_file(mapping, mapping_folder="mapping-old"):
    if isinstance(mapping.entries[0], CQLMapping):
        mapping_file = f"{mapping_folder}/cql/mapping_cql.json"
    elif isinstance(mapping.entries[0], FhirMapping):
        mapping_file = f"{mapping_folder}/fhir/mapping_fhir.json"
    else:
        raise ValueError("Mapping type not supported" + str(type(mapping)))
    with open(mapping_file, 'w', encoding="utf-8") as f:
        f.write(mapping.to_json())
    f.close()

def write_mapping_tree_to_file(tree, mapping_tree_folder="mapping-tree"):
    with open(mapping_tree_folder + "/mapping_tree.json", 'w', encoding="utf-8") as f:
        f.write(tree.to_json())
    f.close()

def validate_fhir_mapping(mapping_name: str):
    """
    Validates the fhir mapping with the given name against the fhir mapping schema
    :param mapping_name: name of the fhir mapping file
    :raises: jsonschema.exceptions.ValidationError if the fhir mapping is not valid
             jsonschema.exceptions.SchemaError if the fhir mapping schema is not valid
    """
    f = open("generated-ontology/mapping/fhir/" + mapping_name + ".json", 'r')
    validate(instance=json.load(f), schema=json.load(open("../../resources/schema/fhir-mapping-schema.json")))

def validate_mapping_tree(tree_name: str, mapping_tree_folder="mapping-tree"):
    """
    Validates the mapping tree with the given name against the mapping tree schema
    :param tree_name: name of the mapping tree
    :raises: jsonschema.exceptions.ValidationError if the mapping tree is not valid
             jsonschema.exceptions.SchemaError if the mapping tree schema is not valid
    """
    f = open(f'{mapping_tree_folder}/{tree_name}.json', 'r')
    validate(instance=json.load(f), schema=json.load(open("../../resources/schema/codex-code-tree-schema.json")))

def setup_logging(log_level):
    # Configure logging
    logging.basicConfig(
        level=log_level,  # Set the logging level
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",  # Define the format of the log messages
    )

    logger = logging.getLogger("fhir_onto_logger")

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(log_level)  # Set the log level for stdout logging
    logger.addHandler(stream_handler)

    return logger

if __name__ == '__main__':

    parser = configure_args_parser()
    args = parser.parse_args()

    log_level = getattr(logging, args.loglevel)
    log = setup_logging(log_level)
    log.info(f"# Starting fhir ontology generator with logging level: {args.loglevel}")
    client = docker.from_env()
    existing_containers = client.containers.list(all=True, filters={"name": "test_db"})

    for container in existing_containers:
        container.stop()
        container.remove()

    container = client.containers.run("postgres:latest", detach=True, ports={'5432/tcp': 5430},
                                      name="test_db",
                                      volumes={f"{os.getcwd()}/generated-ontology": {'bind': '/opt/db_data', 'mode': 'rw'}},
                                      environment={
                                          'POSTGRES_USER': 'codex-postgres',
                                          'POSTGRES_PASSWORD': 'codex-password',
                                          'POSTGRES_DB': 'codex_ui'
                                      })
    db_writer = DataBaseWriter(5430)

    onto_result_dir = "generated-ontology"
    differential_folder = "resources/differential"
    generate_result_folder(onto_result_dir)

    with open("resources/required_packages.json", "r") as f:
        required_packages = json.load(f)

    if args.download_packages:
        log.info(f"# Downloading Packages...")

        download_simplifier_packages(required_packages)

    if args.generate_snapshot:
        log.info(f"# Generating Snapshots...")
        generate_snapshots(differential_folder)
        generate_snapshots(differential_folder, required_packages)

    resolver = StandardDataSetQueryingMetaDataResolver()

    if args.generate_ui_trees:
        log.info(f"# Generating UI Trees...")
        tree_generator = UITreeGenerator(resolver)
        ui_trees = tree_generator.generate_ui_trees(differential_folder)
        write_ui_trees_to_files(ui_trees, f'{onto_result_dir}/ui-trees')

        mapping_tree = to_term_code_node(ui_trees)
        write_mapping_tree_to_file(mapping_tree, f'{onto_result_dir}/mapping')
        validate_mapping_tree("mapping_tree", f'{onto_result_dir}/mapping' )

    if args.generate_ui_profiles:
        log.info(f"# Generating UI Profiles...")
        profile_generator = UIProfileGenerator(resolver)
        contextualized_term_code_ui_profile_mapping, named_ui_profiles_dict = \
            profile_generator.generate_ui_profiles(differential_folder)
        db_writer.write_ui_profiles_to_db(contextualized_term_code_ui_profile_mapping, named_ui_profiles_dict)
        db_writer.write_vs_to_db(named_ui_profiles_dict.values())

        result = container.exec_run(
            'pg_dump --dbname="codex_ui" -U codex-postgres -a -O -t termcode -t context -t ui_profile -t mapping'
            ' -t contextualized_termcode -t contextualized_termcode_to_criteria_set -t criteria_set -f /opt/db_data/R__Load_latest_ui_profile.sql')

    if args.generate_mapping:
        # CQL
        log.info(f"# Generating CQL Mapping...")
        cql_generator = CQLMappingGenerator(resolver)
        cql_mappings = cql_generator.generate_mapping(differential_folder)
        cql_term_code_mappings = cql_mappings[0]
        cql_concept_mappings = cql_mappings[1]
        cql_mappings = denormalize_mapping_to_old_format(cql_term_code_mappings, cql_concept_mappings)
        write_mapping_to_file(cql_mappings, f'{onto_result_dir}/mapping')

        #FHIR
        log.info(f"# Generating FHIR Mapping...")
        search_parameter_resolver = StandardSearchParameterResolver()
        fhir_search_generator = FHIRSearchMappingGenerator(resolver, search_parameter_resolver)
        fhir_search_term_code_mappings, fhir_search_concept_mappings = fhir_search_generator.generate_mapping(
            differential_folder)

        fhir_search_mapping = denormalize_mapping_to_old_format(fhir_search_term_code_mappings,
                                                                   fhir_search_concept_mappings)
        write_mapping_to_file(fhir_search_mapping, f'{onto_result_dir}/mapping')
        validate_fhir_mapping("mapping_fhir")



    container.stop()
    container.remove()
