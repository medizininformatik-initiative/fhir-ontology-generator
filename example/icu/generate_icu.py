from __future__ import annotations

import argparse
import copy
import json
import os
from typing import List, ValuesView, Dict
import docker

from FHIRProfileConfiguration import *
from core.FHIRSearchMappingGenerator import FHIRSearchMappingGenerator
from core.ResourceQueryingMetaDataResolver import ResourceQueryingMetaDataResolver
from core.SearchParameterResolver import SearchParameterResolver
from core.StrucutureDefinitionParser import get_element_from_snapshot
from core.UIProfileGenerator import UIProfileGenerator
from core.UITreeGenerator import UITreeGenerator
from database.DataBaseWriter import DataBaseWriter
from helper import download_simplifier_packages, generate_snapshots, write_object_as_json, load_querying_meta_data, \
    generate_result_folder
from model.MappingDataModel import CQLMapping, FhirMapping, MapEntryList
from model.ResourceQueryingMetaData import ResourceQueryingMetaData
from model.UIProfileModel import UIProfile
from model.UiDataModel import TermEntry, TermCode

WINDOWS_RESERVED_CHARACTERS = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']

core_data_sets = [DKTK, MII_SPECIMEN, MII_PERSON]

class ICUDataSetQueryingMetaDataResolver(ResourceQueryingMetaDataResolver):

    def __init__(self):
        super().__init__()

    def get_query_meta_data(self, fhir_profile_snapshot: dict, _context: TermCode) -> List[ResourceQueryingMetaData]:
        """
        Implementation as simple look up table.
        :param fhir_profile_snapshot:
        :param _context:
        :return: List of ResourceQueryingMetaData
        """
        result = []
        print(fhir_profile_snapshot.get("url"))
        key = fhir_profile_snapshot.get("name")
        mapping = self._get_query_meta_data_mapping()
        for value in mapping[key]:
            with open(f"resources/QueryingMetaData/{value}QueryingMetaData.json", "r") as file:
                result.append(ResourceQueryingMetaData.from_json(file))
        return result

    @staticmethod
    def _get_query_meta_data_mapping():
        with open("resources/profile_to_query_meta_data_resolver_mapping.json", "r") as f:
            return json.load(f)
        

class ICUSearchParameterResolver(SearchParameterResolver):
    def _load_module_search_parameters(self) -> List[Dict]:
        params = []
        for file in os.listdir("resources/search_parameter"):
            if file.endswith(".json"):
                with open(os.path.join("resources/search_parameter", file), "r", encoding="utf-8") as f:
                    params.append(json.load(f))
        return params


def write_ui_trees_to_files(trees: List[TermEntry], directory: str = "ui-trees"):
    """
    Writes the ui trees to the ui-profiles folder
    :param trees: ui trees to write
    :param directory: directory to write the ui trees to
    """
    for tree in trees:
        print(tree.display)
        write_object_as_json(tree, f"{directory}/{tree.display}.json")

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
        generate_snapshots("resources/bkfz_differential", core_data_sets)
    # -------------------------------------------------------------

    # You shouldn't need different implementations for the different generators
    resolver = ICUDataSetQueryingMetaDataResolver()

    if args.generate_ui_trees:
        tree_generator = UITreeGenerator(resolver)
        ui_trees = tree_generator.generate_ui_trees("resources/bkfz_differential")
        write_ui_trees_to_files(ui_trees)

    if args.generate_ui_profiles:
        profile_generator = UIProfileGenerator(resolver)
        contextualized_term_code_ui_profile_mapping, named_ui_profiles_dict = \
            profile_generator.generate_ui_profiles("resources/bkfz_differential")
        db_writer.write_ui_profiles_to_db(contextualized_term_code_ui_profile_mapping, named_ui_profiles_dict)
        db_writer.write_vs_to_db(named_ui_profiles_dict.values())

    if args.generate_mapping:
        search_parameter_resolver = ICUSearchParameterResolver()
        fhir_search_generator = FHIRSearchMappingGenerator(resolver, search_parameter_resolver)
        fhir_search_term_code_mappings, fhir_search_concept_mappings = fhir_search_generator.generate_mapping(
            "resources/bkfz_differential")
        # write_mapping_to_db(db_writer, fhir_search_term_code_mappings, fhir_search_concept_mappings, "FHIR_SEARCH",
        #                     args.generate_ui_profiles)



    result = container.exec_run(
        'pg_dump --dbname="codex_ui" -U codex-postgres -a -O -t termcode -t context -t ui_profile -t mapping'
        ' -t contextualized_termcode -t contextualized_termcode_to_criteria_set -t criteria_set -f /opt/db_data/R__Load_latest_ui_profile.sql')
    print("Dumped db")
    container.stop()
    container.remove()