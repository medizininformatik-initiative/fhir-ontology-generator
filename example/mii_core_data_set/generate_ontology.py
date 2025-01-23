from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import sys
import logging
from typing import List, ValuesView, Dict, Tuple

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
from model.UiDataModel import TermCode
from core.docker.Images import POSTGRES_IMAGE

WINDOWS_RESERVED_CHARACTERS = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']


class StandardDataSetQueryingMetaDataResolver(ResourceQueryingMetaDataResolver):
    def __init__(self):
        super().__init__()

    @staticmethod
    def _load_profile_to_metadata_mapping(module_name) -> Dict[str, List[str]]:
        """
        Loads the profile to metadata mapping from a JSON file.
        :return: A dictionary mapping profile names to lists of metadata names.
        """
        mapping_file = os.path.join("CDS_Module", module_name, "profile_to_query_meta_data_resolver_mapping.json")
        with open(mapping_file, "r") as f:
            return json.load(f)

    def get_query_meta_data(
        self, fhir_profile_snapshot: dict, module_name, _context: TermCode = None
    ) -> List[ResourceQueryingMetaData]:
        """
        Retrieves query metadata for a given FHIR profile snapshot.
        :param fhir_profile_snapshot: The FHIR profile snapshot.
        :param _context: The context term code (unused in this implementation).
        :return: A list of ResourceQueryingMetaData objects.
        """
        result = []
        profile_name = fhir_profile_snapshot.get("name")
        self.profile_to_metadata_mapping = self._load_profile_to_metadata_mapping(module_name)
        if profile_name in self.profile_to_metadata_mapping:
            for metadata_name in self.profile_to_metadata_mapping[profile_name]:
                metadata_file = os.path.join("CDS_Module", module_name, "QueryingMetaData", f"{metadata_name}QueryingMetaData.json")
                with open(metadata_file, "r") as file:
                    result.append(ResourceQueryingMetaData.from_json(file))
        else:
            logging.warning(f"No query metadata mapping found for profile: {profile_name}")
        return result


class StandardSearchParameterResolver(SearchParameterResolver):
    def __init__(self, module_name: str):
        self.module_name = module_name
        super().__init__()
    def _load_module_search_parameters(self) -> List[Dict]:
        """
        Loads module-specific search parameters from JSON files.
        :return: A list of search parameter dictionaries.
        """
        params = []
        search_param_dir = os.path.join("CDS_Module", self.module_name, "search_parameter")
        search_param_dir_path = Path(search_param_dir)

        if not search_param_dir_path.exists() or not search_param_dir_path.is_dir():
            return params

        for filename in os.listdir(search_param_dir):
            if filename.endswith(".json"):
                file_path = os.path.join(search_param_dir, filename)
                with open(file_path, "r", encoding="utf-8") as f:
                    params.append(json.load(f))

        return params

def validate_fhir_mapping(mapping_name: str):
    """
    Validates the FHIR mapping against its JSON schema.
    :param mapping_name: The name of the mapping file (without extension).
    """
    mapping_file = os.path.join("generated-ontology", "mapping", "fhir", f"{mapping_name}.json")
    schema_file = os.path.join("resources", "schema", "fhir-mapping-schema.json")
    with open(mapping_file, 'r') as f:
        mapping_data = json.load(f)
    with open(schema_file, 'r') as f:
        schema = json.load(f)
    validate(instance=mapping_data, schema=schema)


def validate_mapping_tree(tree_name: str, mapping_tree_folder="mapping-tree"):
    """
    Validates the mapping tree against its JSON schema.
    :param tree_name: The name of the mapping tree file (without extension).
    :param mapping_tree_folder: The directory containing the mapping tree files.
    """
    tree_file = os.path.join(mapping_tree_folder, f"{tree_name}.json")
    schema_file = os.path.join("resources", "schema", "codex-code-tree-schema.json")
    with open(tree_file, 'r') as f:
        tree_data = json.load(f)
    with open(schema_file, 'r') as f:
        schema = json.load(f)
    validate(instance=tree_data, schema=schema)


def write_ui_trees_to_files(trees: List, module_name: str, directory: str = "ui-trees", ):
    """
    Writes UI trees to JSON files in the specified directory.
    :param trees: List of UI tree objects.
    :param directory: Directory to write the UI tree files to.
    """
    for i, tree in enumerate(trees):
        file_name = f"{module_name}_ui_tree_{i}.json"
        sanitized_name = remove_reserved_characters(file_name)
        file_path = os.path.join(directory, sanitized_name)
        write_object_as_json(tree, file_path)

def write_term_code_info_to_file(term_code_info_list, directory: str = "term-code-info"):
    """
    Writes the term code information to JSON files.
    :param term_code_info_list: List of term code information objects.
    :param directory: Directory to write the term code info files to.
    """
    mkdir_if_not_exists(directory)
    for term_code_info in term_code_info_list:
        if term_code_info.entries:
            module_name = term_code_info.entries[0].module.display
            file_name = f"{remove_reserved_characters(module_name)}_term_code_info.json"
            file_path = os.path.join(directory, file_name)
            write_object_as_json(term_code_info, file_path)


def write_used_value_sets_to_files(ui_profiles: List[UIProfile], directory: str = "value-sets"):
    """
    Writes the value sets used in the UI profiles to the specified directory.
    :param ui_profiles: UI profiles to extract the value sets from.
    :param directory: Directory to write the value sets to.
    """
    mkdir_if_not_exists(directory)
    value_sets = []
    for ui_profile in ui_profiles:
        if ui_profile.valueDefinition and ui_profile.valueDefinition.referencedValueSet:
            value_sets.append(ui_profile.valueDefinition.referencedValueSet)
        if ui_profile.attributeDefinitions:
            for attribute_definition in ui_profile.attributeDefinitions:
                if attribute_definition.referencedValueSet:
                    value_sets.append(attribute_definition.referencedValueSet)
    for value_set in value_sets:
        file_name = f"{remove_reserved_characters(value_set.url.split('/')[-1])}.json"
        file_path = os.path.join(directory, file_name)
        write_object_as_json(value_set, file_path)

def write_used_criteria_sets_to_files(ui_profiles: List[UIProfile], directory: str = "criteria-sets"):
    """
    Writes the criteria sets used in the UI profiles to the specified directory.
    :param ui_profiles: UI profiles to extract the criteria sets from.
    :param directory: Directory to write the criteria sets to.
    """
    mkdir_if_not_exists(directory)
    criteria_sets = []
    for ui_profile in ui_profiles:
        if ui_profile.attributeDefinitions:
            for attribute_definition in ui_profile.attributeDefinitions:
                if attribute_definition.referencedCriteriaSet:
                    criteria_sets.append(attribute_definition.referencedCriteriaSet)
    for criteria_set in criteria_sets:
        file_name = f"{remove_reserved_characters(criteria_set.url.split('/')[-1])}.json"
        file_path = os.path.join(directory, file_name)
        write_object_as_json(criteria_set, file_path)


def remove_reserved_characters(file_name: str) -> str:
    """
    Removes Windows reserved characters from a file name.
    :param file_name: The original file name.
    :return: The sanitized file name.
    """
    return file_name.translate({ord(c): None for c in WINDOWS_RESERVED_CHARACTERS})


def write_ui_profiles_to_files(
    profiles: List[UIProfile] | ValuesView[UIProfile], folder: str = "ui-profiles"
):
    """
    Writes UI profiles to JSON files in the specified folder.
    :param profiles: List or ValuesView of UIProfile objects.
    :param folder: Folder to write the profiles to.
    """
    for profile in profiles:
        file_name = f"{profile.name.replace(' ', '_').replace('.', '_')}.json"
        sanitized_name = remove_reserved_characters(file_name)
        file_path = os.path.join(folder, sanitized_name)
        with open(file_path, 'w', encoding="utf-8") as f:
            f.write(profile.to_json())


def denormalize_mapping_to_old_format(
    term_code_to_mapping_name: Dict[Tuple[TermCode, TermCode], str],
    mapping_name_to_mapping: Dict[str, CQLMapping | FhirMapping],
) -> MapEntryList:
    """
    Denormalizes mappings to the old format.
    :param term_code_to_mapping_name: Mapping from term codes to mapping names.
    :param mapping_name_to_mapping: Mappings to use.
    :return: A MapEntryList containing the denormalized entries.
    """
    result = MapEntryList()
    for (context, term_code), mapping_name in term_code_to_mapping_name.items():
        try:
            mapping = copy.copy(mapping_name_to_mapping[mapping_name])
            mapping.key = term_code
            mapping.context = context
            result.entries.append(mapping)
        except KeyError:
            logging.warning(f"No mapping found for term code {term_code.code}")
    return result


def configure_args_parser() -> argparse.ArgumentParser:
    """
    Configures the argument parser for the script.
    :return: An ArgumentParser object.
    """
    parser = argparse.ArgumentParser(description='Generate the UI-Profile of the core data set')
    parser.add_argument('--download_packages', action='store_true', help='Download required packages')
    parser.add_argument('--generate_snapshot', action='store_true', help='Generate FHIR snapshots')
    parser.add_argument('--generate_ui_trees', action='store_true', help='Generate UI trees')
    parser.add_argument('--generate_ui_profiles', action='store_true', help='Generate UI profiles')
    parser.add_argument('--generate_mapping', action='store_true', help='Generate mappings')
    parser.add_argument('--module', nargs='+', help='Modules to generate the ontology for')
    parser.add_argument(
        "--loglevel",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Set the log level",
    )
    return parser


def generate_result_folder(base_dir: str = ""):
    """
    Generates necessary directories for results.
    :param base_dir: Base directory for the ontology results.
    """
    paths = [
        "mapping",
        "mapping/fhir",
        "mapping/cql",
        "mapping-tree",
        "term-code-info",
        "ui-trees",
        "ui-profiles",
        "ui-profiles-old",
        "value-sets",
    ]
    for path in paths:
        dir_path = os.path.join(base_dir, path)
        mkdir_if_not_exists(dir_path)


def setup_logging(log_level: int) -> logging.Logger:
    """
    Sets up the logging configuration.
    :param log_level: Logging level as an integer.
    :return: A configured Logger object.
    """
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger = logging.getLogger("fhir_onto_logger")

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(log_level)
    logger.addHandler(stream_handler)

    return logger


def manage_docker_container(logger: logging.Logger, module_directory: str, container_name: str) -> docker.models.containers.Container:
    """
    Manages the lifecycle of the Docker container for a module.
    :param logger: The logger object.
    :param module_directory: The directory to mount in the Docker container.
    :param container_name: The name of the Docker container.
    :return: The running Docker container.
    """
    client = docker.from_env()
    existing_containers = client.containers.list(all=True, filters={"name": container_name})

    for container in existing_containers:
        logger.info(f"Stopping and removing existing container named '{container_name}'...")
        container.stop()
        container.remove()

    container = client.containers.run(
        POSTGRES_IMAGE,
        detach=True,
        ports={'5432/tcp': 5430},
        name=container_name,
        volumes={module_directory: {'bind': '/opt/db_data', 'mode': 'rw'}},
        environment={
            'POSTGRES_USER': 'codex-postgres',
            'POSTGRES_PASSWORD': 'codex-password',
            'POSTGRES_DB': 'codex_ui',
        },
    )
    logger.info(f"Docker container '{container_name}' started.")
    return container


def download_required_packages(required_packages: List[Dict], logger: logging.Logger):
    """
    Downloads the required FHIR packages.
    :param required_packages: List of required packages.
    :param logger: The logger object.
    """
    logger.info("Downloading required packages...")
    download_simplifier_packages(required_packages)


def generate_fhir_snapshots(differential_folder: str, required_packages: List[Dict], logger: logging.Logger):
    """
    Generates FHIR snapshots.
    :param differential_folder: The folder containing differential profiles.
    :param required_packages: List of required packages.
    :param logger: The logger object.
    """
    logger.info("Generating FHIR snapshots...")
    generate_snapshots(differential_folder)
    generate_snapshots(differential_folder, required_packages)


def generate_ui_trees(
    resolver: ResourceQueryingMetaDataResolver, differential_folder: str, onto_result_dir: str, module_name: str, logger: logging.Logger
):
    """
    Generates UI trees and writes them to files.
    :param resolver: An instance of ResourceQueryingMetaDataResolver.
    :param differential_folder: The folder containing differential profiles.
    :param onto_result_dir: The base directory for output files.
    :param logger: The logger object.
    """
    logger.info("Generating UI trees...")
    tree_generator = UITreeGenerator(resolver)
    ui_trees = tree_generator.generate_ui_trees(differential_folder, module_name)
    write_ui_trees_to_files(ui_trees, module_name, os.path.join(onto_result_dir, 'ui-trees'))

    # Generate term code context info list
    term_code_context_infos = tree_generator.generate_contextualized_term_code_info_list(differential_folder, module_name)

    # Update children count in term code context infos based on ui_trees
    for term_code_context_info in term_code_context_infos:
        for ui_tree in ui_trees:
            if term_code_context_info.entries:
                if term_code_context_info.entries[0].module.display == ui_tree.module_name:
                    term_code_context_info.update_children_count(ui_tree)

    # Write term code info to files
    write_term_code_info_to_file(term_code_context_infos, os.path.join(onto_result_dir, 'term-code-info'))


def generate_ui_profiles(
    resolver: ResourceQueryingMetaDataResolver,
    differential_folder: str,
    onto_result_dir: str,
    db_writer: DataBaseWriter,
    container: docker.models.containers.Container,
    module_name: str,
    logger: logging.Logger,
):
    """
    Generates UI profiles and writes them to files and database.
    :param resolver: An instance of ResourceQueryingMetaDataResolver.
    :param differential_folder: The folder containing differential profiles.
    :param onto_result_dir: The base directory for output files.
    :param db_writer: An instance of DataBaseWriter.
    :param container: The Docker container running the database.
    :param logger: The logger object.
    """
    logger.info("Generating UI profiles...")
    profile_generator = UIProfileGenerator(resolver)
    (
        contextualized_term_code_ui_profile_mapping,
        named_ui_profiles_dict,
    ) = profile_generator.generate_ui_profiles(differential_folder, module_name=module_name)
    write_ui_profiles_to_files(
        named_ui_profiles_dict.values(), os.path.join(onto_result_dir, 'ui-profiles')
    )
    db_writer.write_ui_profiles_to_db(
        contextualized_term_code_ui_profile_mapping, named_ui_profiles_dict
    )
    db_writer.write_vs_to_db(named_ui_profiles_dict.values())
    write_used_value_sets_to_files(named_ui_profiles_dict.values(), os.path.join(onto_result_dir, 'value-sets'))
    write_used_criteria_sets_to_files(named_ui_profiles_dict.values(), os.path.join(onto_result_dir, 'criteria-sets'))


def dump_database(container: docker.models.containers.Container, module_directory: str, logger: logging.Logger):
    """
    Dumps the database to a SQL file in the module's directory.
    """
    container.exec_run(
        'pg_dump --dbname="codex_ui" -U codex-postgres -a -O '
        '-t termcode -t context -t ui_profile -t mapping '
        '-t contextualized_termcode -t contextualized_termcode_to_criteria_set '
        '-t criteria_set -f /opt/db_data/R__Load_latest_ui_profile.sql'
    )
    logger.info("Database dumped to R__Load_latest_ui_profile.sql")

def generate_cql_mapping(
    resolver: ResourceQueryingMetaDataResolver, differential_folder: str, onto_result_dir: str, module_name, logger: logging.Logger
):
    """
    Generates CQL mappings and writes them to files.
    :param resolver: An instance of ResourceQueryingMetaDataResolver.
    :param differential_folder: The folder containing differential profiles.
    :param onto_result_dir: The base directory for output files.
    :param logger: The logger object.
    """
    logger.info("Generating CQL mapping...")
    cql_generator = CQLMappingGenerator(resolver)
    cql_term_code_mappings, cql_concept_mappings = cql_generator.generate_mapping(differential_folder, module_name)
    cql_mappings = denormalize_mapping_to_old_format(cql_term_code_mappings, cql_concept_mappings)
    cql_mapping_file = os.path.join(onto_result_dir, 'mapping', 'cql', 'mapping_cql.json')
    with open(cql_mapping_file, 'w', encoding='utf-8') as f:
        f.write(cql_mappings.to_json())


def generate_fhir_mapping(
    resolver: ResourceQueryingMetaDataResolver,
    differential_folder: str,
    onto_result_dir: str,
    search_parameter_resolver: SearchParameterResolver,
    module_name: str,
    logger: logging.Logger,
):
    """
    Generates FHIR mappings and writes them to files.
    :param resolver: An instance of ResourceQueryingMetaDataResolver.
    :param differential_folder: The folder containing differential profiles.
    :param onto_result_dir: The base directory for output files.
    :param search_parameter_resolver: An instance of SearchParameterResolver.
    :param module_name: The name of the module.
    :param logger: The logger object.
    """
    logger.info("Generating FHIR mapping...")
    fhir_search_generator = FHIRSearchMappingGenerator(resolver, search_parameter_resolver)
    fhir_search_term_code_mappings, fhir_search_concept_mappings = fhir_search_generator.generate_mapping(
        differential_folder, module_name
    )
    fhir_search_mapping = denormalize_mapping_to_old_format(
        fhir_search_term_code_mappings, fhir_search_concept_mappings
    )
    fhir_mapping_file = os.path.join(onto_result_dir, 'mapping', 'fhir', 'mapping_fhir.json')
    with open(fhir_mapping_file, 'w', encoding='utf-8') as f:
        f.write(fhir_search_mapping.to_json())
    # validate_fhir_mapping("mapping_fhir")
    logger.info("FHIR mapping generated and validated.")


def main():
    parser = configure_args_parser()
    args = parser.parse_args()

    log_level = getattr(logging, args.loglevel)
    logger = setup_logging(log_level)
    logger.info(f"Starting FHIR ontology generator with logging level: {args.loglevel}")


    onto_result_dir = "generated-ontology"
    differential_folder = "differential"

    modules = args.modules if args.modules else [module for module in os.listdir("CDS_Module")]

    for module in modules:

        try:
            logger.info(f"Generating ontology for module: {module}")

            module_directory = Path("CDS_Module") / module / onto_result_dir
            module_directory = module_directory.resolve()
            module_directory_str = str(module_directory)

            generate_result_folder(module_directory_str)

            container_name = f"test_db_{module}"
            container = manage_docker_container(logger, module_directory_str, container_name=container_name)

            db_writer = DataBaseWriter(5430)

            with open(os.path.join("CDS_Module", module, "required_packages.json"), "r") as f:
                requried_packages = json.load(f)
                if args.generate_snapshot:
                    generate_snapshots(os.path.join("CDS_Module", module, differential_folder), requried_packages, logger)

            resolver = StandardDataSetQueryingMetaDataResolver()
            if args.generate_ui_trees:
                generate_ui_trees(resolver, os.path.join("CDS_Module", module, "differential"), os.path.join("CDS_Module", module, onto_result_dir), module, logger)

            if args.generate_ui_profiles:
                generate_ui_profiles(
                    resolver, os.path.join("CDS_Module", module, "differential"), os.path.join("CDS_Module", module, onto_result_dir), db_writer, container, module, logger
                )


            if args.generate_mapping:
                generate_cql_mapping(
                    resolver, os.path.join("CDS_Module", module, "differential"), os.path.join("CDS_Module", module, onto_result_dir), module, logger
                )

                generate_fhir_mapping(
                    resolver, os.path.join("CDS_Module", module, "differential"), os.path.join("CDS_Module", module, onto_result_dir), StandardSearchParameterResolver(module), module, logger
                )
        except Exception as e:
            logger.error(f"An error occurred: {e}", exc_info=True)
        finally:
            # Dump the database to the module's directory
            if args.generate_ui_profiles:
                dump_database(container, module_directory_str, logger)

            # Stop and remove the container
            container.stop()
            container.remove()

if __name__ == '__main__':
    main()
