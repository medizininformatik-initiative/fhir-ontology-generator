import argparse
import json
import logging
import os
import shutil
import sys
from pathlib import Path

from SqlMerger import SqlMerger


def configure_args_parser():
    arg_parser = argparse.ArgumentParser(description='Generate the UI-Profile of the core data set for the MII-FDPG')
    arg_parser.add_argument('--merge_mappings', action='store_true')
    arg_parser.add_argument('--merge_uitrees', action='store_true')
    arg_parser.add_argument('--merge_sqldump', action='store_true')
    arg_parser.add_argument('--merge_dse', action='store_true')
    arg_parser.add_argument(
        '-d', '--ontodirs',
        nargs='+',  # Allows multiple arguments for this option
        required=True,  # Makes this argument required
        help="List of directory paths to ontologies to be merged"
    )

    arg_parser.add_argument(
        '-s', '--dseontodir',
        required=True,  # Makes this argument required
        help="List of directory paths to ontologies to be merged"
    )

    arg_parser.add_argument(
        '-o', '--outputdir',
        required=True,  # Makes this argument required
        help="output directory for merged ontology"
    )

    arg_parser.add_argument(
        '--log-level',
        type=str,
        default='DEBUG',  # Default log level if not provided
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],  # Valid log levels
        help="Set the logging level"
    )

    return arg_parser


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


def path_for_file(base, filename):
    for root, dir, files in os.walk(base):
        if filename in files:
            return os.path.join(root, filename)
    log.error(f"no {filename} in {base}")
    quit()


def load_ontology_file(ontodir, filename):
    file_path = path_for_file(ontodir, filename)
    with open(file_path, "r") as file:
        return json.load(file)


def write_json_to_file(filepath, object):
    with open(filepath, "w+") as file:
        json.dump(object, file)


if __name__ == '__main__':

    parser = configure_args_parser()
    args = parser.parse_args()

    log_level = args.log_level
    log = setup_logging(log_level)
    log.info(f"# Starting fhir ontology merger with logging level: {log_level}")

    log.info(f"Merging ontologies from folders: {args.ontodirs}")

    if args.merge_mappings:

        mapping_cql = []
        mapping_fhir = []
        mapping_tree = []

        for ontodir in args.ontodirs:
            mapping_cql = mapping_cql + load_ontology_file(ontodir, "mapping_cql.json")
            mapping_fhir = mapping_fhir + load_ontology_file(ontodir, "mapping_fhir.json")

            cur_ui_tree_dir = f'{ontodir}/ui-trees'
            for filename in os.listdir(cur_ui_tree_dir):
                cur_mapping_tree = load_ontology_file(cur_ui_tree_dir, filename)
                mapping_tree.extend(cur_mapping_tree)

        cql_dir = f"{args.outputdir}/mapping/cql"
        fhir_dir = f"{args.outputdir}/mapping/fhir"
        os.makedirs(cql_dir, exist_ok=True)
        os.makedirs(fhir_dir, exist_ok=True)

        write_json_to_file(f"{cql_dir}/mapping_cql.json", mapping_cql)
        write_json_to_file(f"{fhir_dir}/mapping_fhir.json", mapping_fhir)
        write_json_to_file(f"{args.outputdir}/mapping/mapping_tree.json", mapping_tree)

    if args.merge_uitrees:

        output_ui_tree_dir = f'{args.outputdir}/ui-trees'
        os.makedirs(output_ui_tree_dir, exist_ok=True)

        output_ui_termcode_info_dir = f'{args.outputdir}/term-code-info'
        os.makedirs(output_ui_termcode_info_dir, exist_ok=True)

        output_crit_set_dir = f'{args.outputdir}/criteria-sets'
        os.makedirs(output_crit_set_dir, exist_ok=True)

        output_value_set_dir = f'{args.outputdir}/value-sets'
        os.makedirs(output_value_set_dir, exist_ok=True)

        for ontodir in args.ontodirs:

            cur_ui_tree_dir = f'{ontodir}/ui-trees'
            for filename in os.listdir(cur_ui_tree_dir):
                shutil.copy(f'{cur_ui_tree_dir}/{filename}', f'{output_ui_tree_dir}/{filename}')

            cur_ui_termcode_info_dir = f'{ontodir}/term-code-info'
            for filename in os.listdir(cur_ui_termcode_info_dir):
                shutil.copy(f'{cur_ui_termcode_info_dir}/{filename}', f'{output_ui_termcode_info_dir}/{filename}')

            cur_crit_set_dir = f'{ontodir}/criteria-sets'
            for filename in os.listdir(cur_crit_set_dir):
                shutil.copy(f'{cur_crit_set_dir}/{filename}', f'{output_crit_set_dir}/{filename}')

            cur_value_set_dir = f'{ontodir}/value-sets'
            for filename in os.listdir(cur_value_set_dir):
                shutil.copy(f'{cur_value_set_dir}/{filename}', f'{output_value_set_dir}/{filename}')

    if args.merge_sqldump:

        output_sql_script_dir = f'{args.outputdir}/sql_scripts'
        sql_script_index = 0
        os.makedirs(output_sql_script_dir, exist_ok=True)

        for ontodir in args.ontodirs:
            cur_sql_file_path = path_for_file(ontodir, "R__Load_latest_ui_profile.sql")
            shutil.copy(f'{cur_sql_file_path}',
                        f'{output_sql_script_dir}/R__Load_latest_ui_profile_{str(sql_script_index)}.sql')

        sql_merger = SqlMerger(sql_script_dir=output_sql_script_dir)
        sql_merger.execute_merge()
        sql_merger.shutdown()

    if args.merge_dse:

        output_value_set_dir = f'{args.outputdir}/value-sets'
        os.makedirs(output_value_set_dir, exist_ok=True)
        cur_value_set_dir = f'{args.dseontodir}/value-sets'

        for filename in os.listdir(cur_value_set_dir):
            shutil.copy(f'{cur_value_set_dir}/{filename}', f'{output_value_set_dir}/{filename}')

        cur_sql_file_path = path_for_file(args.dseontodir, "R__load_latest_dse_profiles.sql")
        output_sql_script_dir = f'{args.outputdir}/sql_scripts'
        os.makedirs(output_sql_script_dir, exist_ok=True)
        shutil.copy(f'{cur_sql_file_path}',
                    f'{output_sql_script_dir}/R__load_latest_dse_profiles.sql')

        cur_dse_tree_path = path_for_file(args.dseontodir, "profile_tree.json")

        shutil.copy(f'{cur_dse_tree_path}',
                    f'{args.outputdir}/profile_tree.json')
