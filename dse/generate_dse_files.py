import argparse
import logging
import os
import json
from typing import Union, Literal

import requests
from urllib.parse import urlparse

from core.ProfileDetailGenerator import ProfileDetailGenerator
from core.ProfileTreeGenerator import ProfileTreeGenerator
from TerminologService.TermServerConstants import TERMINOLOGY_SERVER_ADDRESS, SERVER_CERTIFICATE, PRIVATE_KEY
from TerminologService.valueSetToRoots import get_closure_map, remove_non_direct_ancestors, create_concept_map
from model.TreeMap import TreeMap, TermEntryNode
from model.UiDataModel import TermCode

from util.LoggingUtil import init_logger, log_to_stdout

logger = init_logger("dse", logging.DEBUG)

module_translation = {
    "de-DE": {
        "modul-diagnose": "Diagnose",
        "modul-prozedur": "Prozedur",
        "modul-person": "Person",
        "modul-labor": "Labor",
        "modul-medikation": "Medikation",
        "modul-fall": "Fall",
        "modul-biobank": "Biobank",
        "modul-consent": "Einwilligung"
    },
    "en-US": {
        "modul-diagnose": "Diagnosis",
        "modul-prozedur": "Procedure",
        "modul-person": "Person",
        "modul-labor": "Laboratory",
        "modul-medikation": "Medication",
        "modul-fall": "Case",
        "modul-biobank": "Biobank",
        "modul-consent": "Consent"
    }
}

module_order = ["modul-diagnose", "modul-prozedur", "modul-person", "modul-labor", "modul-medikation", "modul-fall", "modul-biobank", "modul-consent"]

def configure_args_parser():

    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('--download_packages', action='store_true')
    arg_parser.add_argument('--generate_profile_details', action='store_true')
    arg_parser.add_argument('--download_value_sets', action='store_true')
    arg_parser.add_argument('--generate_mapping_trees', action='store_true')
    arg_parser.add_argument(
        "--loglevel",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Set the log level",
    )
    return arg_parser

def download_simplifier_packages(package_names):

    prev_dir = os.getcwd()
    os.chdir("dse-packages")

    for package in package_names:
        os.system(f"fhir install {package} --here")

    os.chdir(prev_dir)

def download_and_save_value_set(value_set_url, session):
    value_set_folder = os.path.join('generated', 'value-sets')

    onto_server_value_set_url = f'{TERMINOLOGY_SERVER_ADDRESS}ValueSet/$expand?url={value_set_url}'

    response = session.get(onto_server_value_set_url, cert=(SERVER_CERTIFICATE, PRIVATE_KEY))

    if response.status_code == 200:
        value_set_data = response.json()
        value_set_name = value_set_data.get('name', urlparse(value_set_data.get('url')).path.split('/ValueSet/', 1)[-1].replace('/', ''))

        with open(f"{value_set_folder}/{value_set_name}.json", "w+") as value_set_file:
            json.dump(value_set_data, value_set_file)

def download_all_value_sets(profile_details):

    session = requests.Session()

    value_set_urls = set()

    for detail in profile_details:
        for filter in (filter for filter in detail['filters'] if filter['ui_type'] == 'code'):
            for value_set_url in filter['valueSetUrls']:
                value_set_urls.add(value_set_url)

    for value_set_url in list(value_set_urls):
        download_and_save_value_set(value_set_url, session)

def generate_r_load_sql(profile_details):
    with open(os.path.join("generated", "R__load_latest_dse_profiles.sql"), "w+") as sql_file:
        sql_file.write("DELETE FROM dse_profile;\n")
        sql_file.write("ALTER SEQUENCE public.dse_profile_id_seq RESTART WITH 1;\n")
        sql_file.write("INSERT INTO dse_profile(id, url, entry) VALUES \n")

        for index, profile_detail in enumerate(profile_details):

            profile_detaildb = json.dumps(profile_detail).replace("'", "''")
            value_line = f"({index + 1},'{profile_detail['url']}','{profile_detaildb}')"
            sql_file.write(value_line)
            if index < len(profile_details) - 1:
                sql_file.write(",\n")
            else:
                sql_file.write(";")


def extract_concepts_from_value_set(vs: dict, target: dict, mode: Literal['compose', 'expansion']) -> None:
    match mode:
        case 'compose':
            for cs_entry in vs['compose']['include']:
                system = cs_entry.get('system', None)
                version = cs_entry.get('version', None)
                if system not in target:
                    target[system] = dict()
                system_dict = target[system]
                if version not in system_dict:
                    system_dict[version] = set()
                concept_set = system_dict[version]
                for concept in cs_entry.get('concept', []):
                    concept_set.add((concept['code'], concept.get('display', None)))
        case 'expansion':
            for concept in vs['expansion']['contains']:
                system = concept.get('system', None)
                version = concept.get('version', None)
                code = concept.get('code', None)
                display = concept.get('display', None)
                if system not in target:
                    target[system] = dict()
                system_dict = target[system]
                if version not in system_dict:
                    system_dict[version] = set()
                concept_set = system_dict[version]
                concept_set.add((code, display))
        case _:
            raise Exception(f"No such mode [actual='{mode}',expected={{'compose','expansion'}}]")


def generate_cs_tree_map(system: str, version: str | None, concepts: set) -> TreeMap:
    logger.debug("Initializing closure table")
    create_concept_map(name="dse-closure")
    term_codes = list(map(lambda t: TermCode(system, t[0], t[1], version), concepts))
    treemap: TreeMap = TreeMap({}, None, system, version)
    treemap.entries = {term_code.code: TermEntryNode(term_code) for term_code in term_codes}
    logger.debug("Building closure table")
    try:
        closure_map = get_closure_map(term_codes, closure_name="dse-closure")
        if groups := closure_map.get("group"):
            if len(groups) > 1:
                raise Exception("Multiple groups in closure map. Currently not supported.")
            logger.debug("Building tree map")
            for group in groups:
                subsumption_map = group["element"]
                subsumption_map = {item['code']: [target['code'] for target in item['target']] for item in subsumption_map}
                for _, parents in subsumption_map.items():
                    remove_non_direct_ancestors(parents, subsumption_map)
                for node, parents, in subsumption_map.items():
                    treemap.entries[node].parents += parents
                    for parent in parents:
                        treemap.entries[parent].children.append(node)
    except Exception as e:
        logger.error(e, exc_info=e)

    return treemap


def generate_dse_mapping_trees(vs_dir_path: Union[str, os.PathLike]) -> list[dict]:
    # Check presence of downloaded value sets
    if not os.path.isdir(vs_dir_path):
        logger.error("Directory with downloaded value sets does not exist")
        raise Exception(f"Directory with downloaded value sets does not exist [path='{os.path.abspath(vs_dir_path)}']")
    elif len(os.listdir(vs_dir_path)) == 0:
        logger.warning("Downloaded value set dir is empty. Empty mapping tree file will be generated")

    # Read value sets and aggregate concepts by code systems
    logger.info("Aggregating code system concepts from value sets")
    code_systems = dict()
    for file_name in os.listdir(vs_dir_path):
        if not file_name.endswith(".json"):
            logger.warning(f"Directory entry '{file_name}' is not a JSON file. Skipping")
        else:
            logger.info(f"Processing value set file '{file_name}'")
            with open(os.path.join(vs_dir_path, file_name), mode="r", encoding="utf-8") as file:
                # We assume JSON format
                vs_json = json.load(file)
                if 'compose' in vs_json:
                    extract_concepts_from_value_set(vs_json, code_systems, 'compose')
                elif 'expansion' in vs_json:
                    extract_concepts_from_value_set(vs_json, code_systems, 'expansion')
                else:
                    logger.warning("Value set does not lists content explicitly. Skipping")

    # Generate mapping tree for each code system
    logger.info("Generating mapping tree")
    tree_maps = []
    for system, version_map in code_systems.items():
        for version, concept_set in version_map.items():
            logger.info(f"Generating tree map [system='{system}',version='{version}']")
            tree_maps.append(generate_cs_tree_map(system, version, concept_set))

    return [tree_map.to_dict() for tree_map in tree_maps]


if __name__ == '__main__':

    parser = configure_args_parser()
    args = parser.parse_args()

    # Configure logging to stdout
    log_level = getattr(logging, args.loglevel)
    log_to_stdout("dse", level=log_level)
    log_to_stdout("valueSetToRoots", level=log_level)

    if args.download_packages:
        with open("required-packages.json", "r") as f:
            required_packages = json.load(f)

        download_simplifier_packages(required_packages)

    with open("exclude-dirs.json", "r") as f:
        exclude_dirs = json.load(f)

    packages_dir = os.path.join(os.getcwd(), "dse-packages", "dependencies")

    tree_generator = ProfileTreeGenerator(packages_dir, exclude_dirs, module_order, module_translation)
    tree_generator.get_profiles()

    profile_tree = tree_generator.generate_profiles_tree()

    with open(os.path.join("generated", "profile_tree.json"), "w") as f:
        json.dump(profile_tree, f)


    mapping_type_code = {"Observation": "code",
                         "Condition": "code",
                         "Consent": "provision.provision.code",
                         "Procedure": "code",
                         "MedicationAdministration": "medication.code",
                         "MedicationStatement": "medication.code",
                         "Specimen": "type"
                         }

    blacklistedValueSets = ['http://hl7.org/fhir/ValueSet/observation-codes']

    if args.generate_profile_details:

        profiles = tree_generator.profiles
        fields_to_exclude = [".meta", ".id", ".subject", ".extension"]
        profile_detail_generator = ProfileDetailGenerator(profiles, mapping_type_code, blacklistedValueSets, fields_to_exclude)
        profile_details = []

        with open("profile_details_all_translations.json", "r") as f:
            translated_profiles = json.load(f)

        for profile in profiles:

            profile_detail = profile_detail_generator.generate_detail_for_profile(profiles[profile])
            #profile_detail = profile_detail_generator.translate_detail_for_profile(profile_detail)

            if profile_detail:
                profile_details.append(profile_detail)

        with open(os.path.join("generated", "profile_details_all.json"), "w+") as p_details_f:
            json.dump(profile_details, p_details_f)

        generate_r_load_sql(profile_details)

        if args.download_value_sets:
            download_all_value_sets(profile_details)

        if args.generate_mapping_trees:
            dse_mapping_trees = generate_dse_mapping_trees(os.path.join('generated', 'value-sets'))

            with open(os.path.join('generated', 'dse_mapping_tree.json'), "w+") as dse_tree_f:
                json.dump(dse_mapping_trees, dse_tree_f)
