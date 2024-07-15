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
    arg_parser.add_argument("--loglevel", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], default="INFO",
                        help="Set the log level")
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


if __name__ == '__main__':

    parser = configure_args_parser()
    args = parser.parse_args()

    log_level = getattr(logging, args.loglevel)
    log = setup_logging(log_level)
    log.info(f"# Starting fhir ontology merger with logging level: {args.loglevel}")

    if "ONTOPATH_LEFT" in os.environ and "ONTOPATH_RIGHT" in os.environ and "ONTOPATH_JOINED" in os.environ and "SQL_SCRIPT_DIR" in os.environ:
        ontopath_left = os.environ.get("ONTOPATH_LEFT")
        ontopath_right = os.environ.get("ONTOPATH_RIGHT")
        ontopath_joined = os.environ.get("ONTOPATH_JOINED")
        sql_scriptdir = os.environ.get("SQL_SCRIPT_DIR")
        uitree_dir_left = os.getenv("UITREE_DIR_LEFT", "ui-trees/")
        uitree_dir_right = os.getenv("UITREE_DIR_RIGHT", "ui-trees/")
        log.info(f"# merging ontologies on paths, left: {ontopath_left}, right: {ontopath_right}, to: {ontopath_joined}")
    else:
        log.error("NOT ALL REQUIRED ENVIRONMENT VARIABLES SET")
        quit()

    if args.merge_mappings or args.merge_uitrees or args.merge_sqldump:
        Path(ontopath_joined).mkdir(parents=True, exist_ok=True)
        Path(ontopath_joined + "ui_trees/").mkdir(parents=True, exist_ok=True)
        Path(ontopath_joined + "migration/").mkdir(parents=True, exist_ok=True)

    if args.merge_mappings:
        log.info(f"# merging cql mapping ")
        ontopath_left_cqlmapping = path_for_file(ontopath_left, "mapping_cql.json")
        ontopath_right_cqlmapping = path_for_file(ontopath_right, "mapping_cql.json")
        with open(ontopath_left_cqlmapping, "r") as onto_left, open(ontopath_right_cqlmapping, "r") as onto_right:
            onto_left_json = json.load(onto_left)
            onto_right_json = json.load(onto_right)
            onto_joined_json = onto_left_json + onto_right_json
            with open(ontopath_joined + "mapping_cql.json", "w+") as onto_joined_file:
                json.dump(onto_joined_json, onto_joined_file)

        ontopath_left_fhirmapping = path_for_file(ontopath_left, "mapping_fhir.json")
        ontopath_right_fhirmapping = path_for_file(ontopath_right, "mapping_fhir.json")
        log.info(f"merging fhir mapping")
        with open(ontopath_left_fhirmapping, "r") as onto_left, open(ontopath_right_fhirmapping, "r") as onto_right:
            onto_left_json = json.load(onto_left)
            onto_right_json = json.load(onto_right)
            onto_joined_json = onto_left_json + onto_right_json
            with open(ontopath_joined + "mapping_fhir.json", "w+") as onto_joined_file:
                json.dump(onto_joined_json, onto_joined_file)

        ontopath_left_mappingtree = path_for_file(ontopath_left, "mapping_tree.json")
        ontopath_right_mappingtree = path_for_file(ontopath_right, "mapping_tree.json")
        log.info(f"merging mapping tree")
        with open(ontopath_left_mappingtree, "r") as onto_left, open(ontopath_right_mappingtree, "r") as onto_right:
            onto_left_json = json.load(onto_left)
            onto_right_json = json.load(onto_right)
            onto_joined_json = onto_left_json["children"].extend(onto_right_json["children"])
            with open(ontopath_joined + "mapping_tree.json", "w+") as onto_joined_file:
                json.dump(onto_joined_json, onto_joined_file)

    if args.merge_uitrees:
        log.info(f"merging ui trees")
        for filename in os.listdir(ontopath_left + uitree_dir_left):
            shutil.copy(ontopath_left + uitree_dir_left + filename, ontopath_joined + "ui_trees/")
            log.info("copying ui tree: " + filename)
        for filename in os.listdir(ontopath_right + uitree_dir_left):
            shutil.copy(ontopath_right + uitree_dir_left + filename, ontopath_joined + "ui_trees/")
            log.info("copying ui tree: " + filename)

    if args.merge_sqldump:
        sql_merger = SqlMerger(sql_script_dir=sql_scriptdir)
        sql_merger.execute_merge()
