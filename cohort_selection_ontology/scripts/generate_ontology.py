from __future__ import annotations

import argparse
import copy
from collections.abc import Callable
from importlib.resources import open_text
import json
import os
from pathlib import Path
from typing import List, ValuesView, Dict, Tuple

import docker
from docker.models.containers import Container
from jsonschema import validate

import cohort_selection_ontology.resources.schema as schema_files

from cohort_selection_ontology.core.generators.cql.generator import CQLMappingGenerator
from cohort_selection_ontology.core.generators.fhir_search import (
    FHIRSearchMappingGenerator,
)
from cohort_selection_ontology.core.resolvers.querying_metadata import (
    ResourceQueryingMetaDataResolver,
    StandardDataSetQueryingMetaDataResolver,
)
from cohort_selection_ontology.core.resolvers.search_parameter import (
    StandardSearchParameterResolver,
)
from cohort_selection_ontology.core.generators.ui_profile import UIProfileGenerator
from cohort_selection_ontology.core.generators.ui_tree import UITreeGenerator
from cohort_selection_ontology.util.database import DataBaseWriter
from common.util.docker.container import PostgresContainer
from common.util.fhir.terminal import generate_snapshots
from common.util.codec.json import write_object_as_json
from cohort_selection_ontology.model.mapping import MapEntryList
from cohort_selection_ontology.model.mapping.fhirpath import FhirMapping
from cohort_selection_ontology.model.mapping.cql import CQLMapping
from cohort_selection_ontology.model.ui_profile import UIProfile
from cohort_selection_ontology.model.ui_data import TermCode
from common.util.log.functions import get_logger
from common.util.project import Project

logger = get_logger(__file__)

WINDOWS_RESERVED_CHARACTERS = ["<", ">", ":", '"', "/", "\\", "|", "?", "*"]


def validate_fhir_mapping(module_name: str, mapping_name: str, project: Project):
    """
    Validates the FHIR mapping against its JSON schema
    :param module_name: Name of module to validate FHIR mapping for
    :param mapping_name: The name of the mapping file (without extension)
    :param project: Project to generate for
    """
    mapping_file = (
        project.output.cso.mkdirs("modules", module_name, "generated", "fhir")
        / f"{mapping_name}.json"
    )
    with open(mapping_file, mode="r", encoding="utf-8") as f:
        mapping_data = json.load(f)
    with open_text(schema_files, "fhir-mapping-schema.json", encoding="utf-8") as f:
        schema = json.load(f)
    validate(instance=mapping_data, schema=schema)


def validate_mapping_tree(tree_name: str, mapping_tree_folder="mapping-tree"):
    """
    Validates the mapping tree against its JSON schema.
    :param tree_name: The name of the mapping tree file (without extension).
    :param mapping_tree_folder: The directory containing the mapping tree files.
    """
    tree_file = os.path.join(mapping_tree_folder, f"{tree_name}.json")
    with open(tree_file, mode="r", encoding="utf-8") as f:
        tree_data = json.load(f)
    with open_text(schema_files, "codex-code-tree-schema.json", encoding="utf-8") as f:
        schema = json.load(f)
    validate(instance=tree_data, schema=schema)


def write_ui_trees_to_files(
    trees: List,
    module_name: str,
    directory: str | Path = "ui-trees",
):
    """
    Writes UI trees to JSON files in the specified directory.
    :param trees: List of UI tree objects
    :param module_name: Name of the module
    :param directory: Directory to write the UI tree files to.
    """
    for i, tree in enumerate(trees):
        file_name = f"{module_name}_ui_tree_{i}.json"
        sanitized_name = remove_reserved_characters(file_name)
        file_path = os.path.join(directory, sanitized_name)
        write_object_as_json(tree, file_path)


def write_term_code_info_to_file(
    term_code_info_list, directory: str | Path = "term-code-info"
):
    """
    Writes the term code information to JSON files.
    :param term_code_info_list: List of term code information objects.
    :param directory: Directory to write the term code info files to.
    """
    os.makedirs(directory, exist_ok=True)
    for term_code_info in term_code_info_list:
        if term_code_info.entries:
            module_name = term_code_info.entries[0].module.display
            file_name = f"{remove_reserved_characters(module_name)}_term_code_info.json"
            file_path = os.path.join(directory, file_name)
            write_object_as_json(term_code_info, file_path)


def write_used_value_sets_to_files(
    ui_profiles: List[UIProfile], directory: str | Path = "value-sets"
):
    """
    Writes the value sets used in the UI profiles to the specified directory.
    :param ui_profiles: UI profiles to extract the value sets from.
    :param directory: Directory to write the value sets to.
    """
    os.makedirs(directory, exist_ok=True)
    all_profile_value_sets = []
    for ui_profile in ui_profiles:
        if ui_profile.valueDefinition and ui_profile.valueDefinition.referencedValueSet:
            all_profile_value_sets.append(ui_profile.valueDefinition.referencedValueSet)
        if ui_profile.attributeDefinitions:
            for attribute_definition in ui_profile.attributeDefinitions:
                if attribute_definition.referencedValueSet:
                    all_profile_value_sets.append(attribute_definition.referencedValueSet)
    for one_profile_value_set in all_profile_value_sets:
        for single_value_set in one_profile_value_set:
            file_name = f"{remove_reserved_characters(single_value_set.url.split('/')[-1])}.json"
            file_path = os.path.join(directory, file_name)
            write_object_as_json(single_value_set, file_path)


def write_used_criteria_sets_to_files(
    ui_profiles: List[UIProfile], directory: str | Path = "criteria-sets"
):
    """
    Writes the criteria sets used in the UI profiles to the specified directory.
    :param ui_profiles: UI profiles to extract the criteria sets from.
    :param directory: Directory to write the criteria sets to.
    """
    os.makedirs(directory, exist_ok=True)
    all_profile_criteria_sets = []
    for ui_profile in ui_profiles:
        if ui_profile.attributeDefinitions:
            for attribute_definition in ui_profile.attributeDefinitions:
                if attribute_definition.referencedCriteriaSet:
                    all_profile_criteria_sets.append(attribute_definition.referencedCriteriaSet)
    for one_profile_criteria_set in all_profile_criteria_sets:
        for single_criteria_set in one_profile_criteria_set:
            file_name = f"{remove_reserved_characters(single_criteria_set.url.split('/')[-1])}.json"
            file_path = os.path.join(directory, file_name)
            write_object_as_json(single_criteria_set, file_path)


def remove_reserved_characters(file_name: str) -> str:
    """
    Removes Windows reserved characters from a file name.
    :param file_name: The original file name.
    :return: The sanitized file name.
    """
    return file_name.translate({ord(c): None for c in WINDOWS_RESERVED_CHARACTERS})


def write_ui_profiles_to_files(
    profiles: List[UIProfile] | ValuesView[UIProfile],
    folder: str | Path = "ui-profiles",
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
        os.makedirs(folder, exist_ok=True)
        with open(file_path, mode="w", encoding="utf-8") as f:
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
            logger.warning(f"No mapping found for term code {term_code.code}")
    return result


def configure_args_parser() -> argparse.ArgumentParser:
    """
    Configures the argument parser for the script.
    :return: An ArgumentParser object.
    """
    parser = argparse.ArgumentParser(
        description="Generate the UI-Profile of the core data set"
    )
    parser.add_argument(
        "--project",
        required=True,
        help="Project to generate cohort selection ontology files for",
    )
    parser.add_argument(
        "--download_packages", action="store_true", help="Download required packages"
    )
    parser.add_argument(
        "--generate_snapshot", action="store_true", help="Generate FHIR snapshots"
    )
    parser.add_argument(
        "--generate_ui_trees", action="store_true", help="Generate UI trees"
    )
    parser.add_argument(
        "--generate_ui_profiles", action="store_true", help="Generate UI profiles"
    )
    parser.add_argument(
        "--generate_mapping", action="store_true", help="Generate mappings"
    )
    parser.add_argument(
        "--module", nargs="+", help="Modules to generate the ontology for"
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
        os.makedirs(dir_path, exist_ok=True)


def managed_db_container(volume_dir: str, container_name: str, on_exit: Callable[[Container], None]) -> PostgresContainer:
    """
    Manages the lifecycle of the Docker container for a module.
    :param volume_dir: The directory to mount in the Docker container.
    :param container_name: The name of the Docker container.
    :param on_exit: Action to execute before container shutdown
    :return: Postgres Docker container context manager instance
    """
    return PostgresContainer(name=container_name, host_port=5430, volume_dir=volume_dir, pg_user='codex-postgres',
                             pg_pw='codex-password', pg_db='codex_ui', on_exit=on_exit)


def generate_ui_trees(
    resolver: ResourceQueryingMetaDataResolver, module_name: str, project: Project
):
    """
    Generates UI trees and writes them to files
    :param resolver: An instance of ResourceQueryingMetaDataResolver
    :param module_name: Name of the module to generate UI trees for
    :param project: Project to generate for
    """
    logger.info("Generating UI trees...")
    result_dir = project.output.cso.mkdirs("modules", module_name)
    tree_generator = UITreeGenerator(project=project, querying_meta_data_resolver=resolver)
    ui_trees = [tree_generator.generate_module_ui_tree(module_name)]
    write_ui_trees_to_files(ui_trees, module_name, result_dir / "ui-trees")

    # Generate term code context info list
    term_code_context_infos = (
        tree_generator.generate_contextualized_term_code_info_list(module_name)
    )

    # Update children count in term code context infos based on ui_trees
    for term_code_context_info in term_code_context_infos:
        for ui_tree in ui_trees:
            if term_code_context_info.entries:
                if (
                    term_code_context_info.entries[0].module.display
                    == ui_tree.module_name
                ):
                    term_code_context_info.update_descendant_count(ui_tree)

    # Write term code info to files
    write_term_code_info_to_file(term_code_context_infos, result_dir / "term-code-info")


def generate_ui_profiles(
    resolver: ResourceQueryingMetaDataResolver,
    db_writer: DataBaseWriter,
    module_name: str,
    project: Project,
):
    """
    Generates UI profiles and writes them to files and database
    :param resolver: An instance of ResourceQueryingMetaDataResolver
    :param db_writer: An instance of DataBaseWriter
    :param module_name: Name of the module to generate UI profiles for
    :param project: Project to generate for
    """
    logger.info("Generating UI profiles...")
    result_dir = project.output.cso.mkdirs("modules", module_name)
    profile_generator = UIProfileGenerator(project, querying_meta_data_resolver=resolver)
    (
        contextualized_term_code_ui_profile_mapping,
        named_ui_profiles_dict,
    ) = profile_generator.generate_ui_profiles(module_name=module_name)
    write_ui_profiles_to_files(
        named_ui_profiles_dict.values(), result_dir / 'ui-profiles'
    )
    db_writer.write_ui_profiles_to_db(
        contextualized_term_code_ui_profile_mapping, named_ui_profiles_dict
    )
    db_writer.write_vs_to_db(named_ui_profiles_dict.values())
    write_used_value_sets_to_files(
        named_ui_profiles_dict.values(), result_dir / "value-sets"
    )
    write_used_criteria_sets_to_files(
        named_ui_profiles_dict.values(), result_dir / "criteria-sets"
    )


def dump_database(container: docker.models.containers.Container):
    """
    Dumps the database to a SQL file in the module's directory.
    """
    container.exec_run(
        'pg_dump --format=plain --dbname="codex_ui" -U codex-postgres -a -O '
        "-t termcode -t context -t ui_profile -t mapping "
        "-t contextualized_termcode -t contextualized_termcode_to_criteria_set "
        "-t criteria_set -f /opt/db_data/R__Load_latest_ui_profile.sql"
    )
    logger.info("Database dumped to R__Load_latest_ui_profile.sql")


def generate_cql_mapping(
    resolver: ResourceQueryingMetaDataResolver, module_name: str, project: Project
):
    """
    Generates CQL mappings and writes them to files
    :param resolver: An instance of ResourceQueryingMetaDataResolver
    :param module_name: Name of the module to generate CQL mapping for
    :param project: Project to run for
    """
    try:
        logger.info("Generating CQL mapping")
        cql_generator = CQLMappingGenerator(project, querying_meta_data_resolver=resolver)
        cql_term_code_mappings, cql_concept_mappings = cql_generator.generate_mapping(
            module_name
        )
        cql_mappings = denormalize_mapping_to_old_format(
            cql_term_code_mappings, cql_concept_mappings
        )
        cql_mapping_file = (
            project.output.cso.mkdirs("modules", module_name, "mapping", "cql")
            / "mapping_cql.json"
        )
        os.makedirs(os.path.dirname(cql_mapping_file), exist_ok=True)
        with open(cql_mapping_file, mode="w", encoding="utf-8") as f:
            f.write(cql_mappings.to_json())
    except Exception as exc:
        raise Exception(
            "CQL mapping generation failed. No mapping will be emitted", exc
        )


def generate_fhir_mapping(
    resolver: ResourceQueryingMetaDataResolver,
    module_name: str,
    project: Project
):
    """
    Generates FHIR mappings and writes them to files.
    :param resolver: An instance of ResourceQueryingMetaDataResolver
    :param module_name: The name of the module to generate FHIR mapping for
    :param project: Project to run for
    """
    logger.info("Generating FHIR mapping")
    search_parameter_resolver = StandardSearchParameterResolver(
        module_path=project.input.cso.mkdirs("modules", module_name)
    )
    fhir_search_generator = FHIRSearchMappingGenerator(
        project=project, querying_meta_data_resolver=resolver, fhir_search_mapping_resolver=search_parameter_resolver
    )
    fhir_search_term_code_mappings, fhir_search_concept_mappings = (
        fhir_search_generator.generate_mapping(module_name)
    )
    fhir_search_mapping = denormalize_mapping_to_old_format(
        fhir_search_term_code_mappings, fhir_search_concept_mappings
    )
    fhir_mapping_file = (
        project.output.cso.mkdirs("modules", module_name, "mapping", "fhir")
        / "mapping_fhir.json"
    )
    os.makedirs(os.path.dirname(fhir_mapping_file), exist_ok=True)
    with open(fhir_mapping_file, mode="w", encoding="utf-8") as f:
        f.write(fhir_search_mapping.to_json())
    # validate_fhir_mapping("mapping_fhir")
    logger.info("FHIR mapping generated and validated.")


def main():
    parser = configure_args_parser()
    args = parser.parse_args()

    project = Project(name=args.project)
    input_dir = project.input
    output_dir = project.output
    input_modules_dir = input_dir.cso / "modules"
    output_modules_dir = output_dir.cso / "modules"

    logger.info(f"Starting FHIR ontology generator for project '{project.name}'")

    modules = (
        args.module
        if args.module
        else [module for module in os.listdir(input_modules_dir)]
    )

    for module in modules:
        try:
            logger.info(f"Generating ontology for module: {module}")

            output_module_directory = str((output_modules_dir / module).resolve())

            generate_result_folder(output_module_directory)

            container_name = f"test_db_{module}"

            def on_exit(c):
                # Dump the database to the module's directory
                if args.generate_ui_profiles:
                    dump_database(c)

            with managed_db_container(output_module_directory, container_name=container_name, on_exit=on_exit) as container:
                db_writer = DataBaseWriter(5430)

                with open(input_modules_dir / module / "required_packages.json", mode="r", encoding="utf-8") as f:
                    required_packages = json.load(f)
                    if args.generate_snapshot:
                        generate_snapshots(input_modules_dir / module, required_packages)

            resolver = StandardDataSetQueryingMetaDataResolver(project=project)
            if args.generate_ui_trees:
                generate_ui_trees(resolver, module, project)

                if args.generate_ui_profiles:
                    generate_ui_profiles(resolver, db_writer, module, project)

                if args.generate_mapping:
                    generate_cql_mapping(resolver, module, project)
                    generate_fhir_mapping(
                        resolver, module, project
                    )
        except Exception as e:
            logger.error(f"An error occurred while running generator for module '{module}': {e}", exc_info=True)


if __name__ == "__main__":
    main()
