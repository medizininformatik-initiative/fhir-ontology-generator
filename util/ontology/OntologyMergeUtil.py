import argparse
import importlib.resources
import json
import os
import shutil

from util.log.functions import get_logger
from util.project import Project
from util.sql.SqlMerger import SqlMerger


logger = get_logger(__file__)


def configure_args_parser():
    arg_parser = argparse.ArgumentParser(description='Generate the UI-Profile of the core data set for the MII-FDPG')
    arg_parser.add_argument('--merge_mappings', action='store_true')
    arg_parser.add_argument('--merge_uitrees', action='store_true')
    arg_parser.add_argument('--merge_sqldump', action='store_true')
    arg_parser.add_argument('--merge_dse', action='store_true')
    arg_parser.add_argument(
        '-dp', '--project',
        required=True,  # Makes this argument required
        help="Project to merge ontology files for"
    )
    arg_parser.add_argument(
        '-s', '--dseontodir',
        required=True,  # Makes this argument required
        help="List of directory paths to ontologies to be merged"
    )
    return arg_parser


def path_for_file(base, file_name):
    for root, dir, files in os.walk(base):
        if file_name in files:
            return os.path.join(root, file_name)
    logger.error(f"No file {file_name} in {base}")
    quit()


def load_ontology_file(onto_dir, file_name):
    file_path = path_for_file(onto_dir, file_name)
    with open(file_path, mode="r", encoding="utf-8") as file:
        return json.load(file)


def write_json_to_file(filepath, object):
    with open(filepath, mode="w+", encoding="utf-8") as file:
        json.dump(object, file)


def add_system_urls_to_systems_json(project: Project, system_urls):
    new_terminology_systems = {}

    with (open(project.input("terminology") / "terminology_systems.json", mode='r', encoding='utf-8') as systems_file):
        terminology_systems = json.load(systems_file)

        for terminology_system in terminology_systems:
            new_terminology_systems[terminology_system['url']] = terminology_system['name']

        for system_url in list(system_urls):
            if system_url not in new_terminology_systems:
                name = system_url.split("/")[-1]
                new_terminology_systems[system_url] = name

        terminology_systems = []
        for key, value in new_terminology_systems.items():
            terminology_systems.append({
                "url": key,
                "name": value
            })

        #systems_file.truncate(0)
        #systems_file.seek(0)

        with open(project.output("terminology") / os.path.basename(systems_file.name),
                  mode='w', encoding='utf-8') as output_file:
            json.dump(terminology_systems, output_file)


def collect_all_terminology_systems(merged_ontology_dir):
    system_urls = set()

    cur_ui_termcode_info_dir = os.path.join(merged_ontology_dir, "term-code-info")
    for file_name in os.listdir(cur_ui_termcode_info_dir):
        with open(os.path.join(cur_ui_termcode_info_dir, file_name), mode="r", encoding="utf-8") as termcode_info_file:
            termcode_infos = json.load(termcode_info_file)

            for termcode_info in termcode_infos:
                system_url = termcode_info["term_code"]["system"]
                system_urls.add(system_url)

    cur_ui_value_set_dir = os.path.join(merged_ontology_dir, "value-sets")
    for file_name in os.listdir(cur_ui_value_set_dir):

        if not file_name.endswith(".json"):
            continue

        with open(os.path.join(cur_ui_value_set_dir, file_name), mode="r", encoding="utf-8") as value_set_file:

            value_set = json.load(value_set_file)

            if "contains" not in value_set["expansion"]:
                continue

            for termcode in value_set["expansion"]["contains"]:
                system_url = termcode["system"]
                system_urls.add(system_url)

    return system_urls


if __name__ == '__main__':
    parser = configure_args_parser()
    args = parser.parse_args()

    logger.info("Running FHIR Ontology Merger")
    logger.info(f"Merging ontologies for project '{args.project}'")

    project = Project(args.project)
    modules_dir = project.output("modules")
    module_dirs = list(map(lambda d: d.path, filter(lambda e: e.is_dir(), os.scandir(modules_dir))))
    output_dir = project.output("merged_ontology")

    if args.merge_mappings:
        logger.info("Merging CCDL mappings")
        mapping_cql = []
        mapping_fhir = []
        mapping_tree = []

        for module_dir in module_dirs:
            mapping_cql = mapping_cql + load_ontology_file(module_dir, "mapping_cql.json")
            mapping_fhir = mapping_fhir + load_ontology_file(module_dir, "mapping_fhir.json")

            cur_ui_tree_dir = os.path.join(module_dir, "ui-trees")
            for filename in os.listdir(cur_ui_tree_dir):
                cur_mapping_tree = load_ontology_file(cur_ui_tree_dir, filename)
                mapping_tree.extend(cur_mapping_tree)

        cql_dir = os.path.join(output_dir, "mapping", "cql")
        fhir_dir = os.path.join(output_dir, "mapping", "fhir")
        os.makedirs(cql_dir, exist_ok=True)
        os.makedirs(fhir_dir, exist_ok=True)

        write_json_to_file(os.path.join(cql_dir, "mapping_cql.json"), mapping_cql)
        write_json_to_file(os.path.join(fhir_dir, "mapping_fhir.json"), mapping_fhir)
        write_json_to_file(os.path.join(output_dir, "mapping", "mapping_tree.json"), mapping_tree)

    if args.merge_uitrees:
        logger.info("Merging UI trees")
        output_ui_tree_dir = os.path.join(output_dir, "ui-trees")
        os.makedirs(output_ui_tree_dir, exist_ok=True)

        output_ui_termcode_info_dir = os.path.join(output_dir, "term-code-info")
        os.makedirs(output_ui_termcode_info_dir, exist_ok=True)

        output_crit_set_dir = os.path.join(output_dir, "criteria-sets")
        os.makedirs(output_crit_set_dir, exist_ok=True)

        output_value_set_dir = os.path.join(output_dir, "value-sets")
        os.makedirs(output_value_set_dir, exist_ok=True)

        for module_dir in module_dirs:
            cur_ui_tree_dir = os.path.join(module_dir, "ui-trees")
            for filename in os.listdir(cur_ui_tree_dir):
                shutil.copy(os.path.join(cur_ui_tree_dir, filename), os.path.join(output_ui_tree_dir, filename))

            cur_ui_termcode_info_dir = os.path.join(module_dir, "term-code-info")
            for filename in os.listdir(cur_ui_termcode_info_dir):
                shutil.copy(os.path.join(cur_ui_termcode_info_dir, filename),
                            os.path.join(output_ui_termcode_info_dir, filename))

            cur_crit_set_dir = os.path.join(module_dir, "criteria-sets")
            for filename in os.listdir(cur_crit_set_dir):
                shutil.copy(os.path.join(cur_crit_set_dir, filename), os.path.join(output_crit_set_dir, filename))

            cur_value_set_dir = os.path.join(module_dir, "value-sets")
            for filename in os.listdir(cur_value_set_dir):
                shutil.copy(os.path.join(cur_value_set_dir, filename), os.path.join(output_value_set_dir, filename))

    if args.merge_sqldump:
        logger.info("Merging SQL dumps")
        output_sql_script_dir = os.path.join(output_dir, "sql_scripts")
        sql_script_index = 0
        os.makedirs(output_sql_script_dir, exist_ok=True)

        for module_dir in module_dirs:
            cur_sql_file_path = path_for_file(module_dir, "R__Load_latest_ui_profile.sql")
            shutil.copy(str(cur_sql_file_path),
                        os.path.join(output_sql_script_dir, "R__Load_latest_ui_profile_{str(sql_script_index)}.sql"))

            sql_script_index += 1

        sql_merger = SqlMerger(sql_script_dir=output_sql_script_dir)
        sql_merger.execute_merge()
        sql_merger.shutdown()

    if args.merge_dse:
        logger.info("Merging DSE content")
        output_value_set_dir = os.path.join(output_dir, "value-sets")
        os.makedirs(output_value_set_dir, exist_ok=True)
        cur_value_set_dir = os.path.join(args.dseontodir, "value-sets")

        for filename in os.listdir(cur_value_set_dir):
            shutil.copy(os.path.join(cur_value_set_dir, filename), os.path.join(output_value_set_dir, filename))

        cur_sql_file_path = path_for_file(args.dseontodir, "R__load_latest_dse_profiles.sql")
        output_sql_script_dir = os.path.join(output_dir, "sql_scripts")
        os.makedirs(output_sql_script_dir, exist_ok=True)
        shutil.copy(str(cur_sql_file_path),
                    os.path.join(output_sql_script_dir, "R__load_latest_dse_profiles.sql"))

        cur_dse_tree_path = path_for_file(args.dseontodir, "profile_tree.json")

        shutil.copy(str(cur_dse_tree_path),
                    os.path.join(output_dir, "profile_tree.json"))

        cur_dse_mapping_tree_path = path_for_file(args.dseontodir, "dse_mapping_tree.json")

        shutil.copy(str(cur_dse_mapping_tree_path),
                    os.path.join(output_dir, "mapping", "dse_mapping_tree.json"))

    system_urls = collect_all_terminology_systems(output_dir)

    add_system_urls_to_systems_json(project, system_urls)
