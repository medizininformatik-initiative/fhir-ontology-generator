import argparse
import logging
import os, sys
import re
import json
import shutil
from pathlib import Path


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

def first_substring_index(strings, substring):
    return next(i for i, string in enumerate(strings) if substring in string)

def get_section_indeces(strings, substring, substring2):
    """
    Finds the indeces of the start and end of a section in a list of strings, defined by two substrings
    :param strings: list of strings
    :param substring: start of section
    :param substring2: end of section
    :return: tuple of integers, start and end of section
    """
    section_start = next(i for i, string in enumerate(strings) if substring in string)
    section_end = next(i for i, string in enumerate(strings[section_start+1:]) if substring2 in string)+section_start+1
    return section_start, section_end

def sql_copy_joiner(basefile, extension, section_start, section_end, id, context_shift=0, termcode_shift=0):
    """
    Modifies the basefile by adding the entries of the extension to the basefile copy expression, increasing the id by the last id in the basefile.
    In the case of the contextualized termcode table, the id is not increased, but the context_id and termcode_id are shifted by the context_shift and termcode_shift respectively.
    :param basefile: basefile to be modified
    :param extension: extension file to be added
    :param section_start: start of copy expression
    :param section_end: end of copy expression
    :param id: boolean, if true, the id field is increased by the last id in the basefile
    :param context_shift: integer, shift for the context_id
    :param termcode_shift: integer, shift for the termcode_id
    :return: Integer, the last id in the basefile if available, 0 otherwise
    """
    basefile_copy_start, basefile_copy_end = get_section_indeces(basefile, section_start, section_end)
    extension_copy_start, extension_copy_end = get_section_indeces(extension, section_start, section_end)

    if id:
        if len(basefile[basefile_copy_start+1:basefile_copy_end]) < 1:
            lastid = 0
        else:
            lastid = int(re.split("\t|\s+", basefile[basefile_copy_end-1])[0])
        extension_slice = extension[extension_copy_start+1:extension_copy_end]
        # Reverse the entries for easier insertion
        extension_slice.reverse()
        for entry in extension_slice:
            linesplit = re.split("\t|\s+", entry)
            newid = lastid + int(linesplit[0])
            newid_entry = entry.replace(linesplit[0], str(newid), 1)
            basefile.insert(basefile_copy_end, newid_entry)
        return lastid
    else:
        for entry in extension[extension_copy_start+1:extension_copy_end]:
            linesplit = re.split("\t+", entry)
            new_context_id = context_shift + int(linesplit[1])
            new_termcode_id = termcode_shift + int(linesplit[2])
            linesplit[1] = str(new_context_id)
            linesplit[2] = str(new_termcode_id)
            newid_entry = "	".join(linesplit)
            basefile.insert(basefile_copy_end, newid_entry)


def sql_select_joiner(basefile: list, extension: list, expression):
    """
    Modifies the basefile by adding the values of the extension select expression to the basefile counterpart
    :param basefile: basefile to be modified
    :param extension: extension file to be added
    :param expression: select statement to be joined
    :return: None
    """
    basefile_select_ind = first_substring_index(basefile, expression)
    extension_select_ind = first_substring_index(extension, expression)

    bf_split = basefile[basefile_select_ind].split(",")
    ext_split = extension[extension_select_ind].split(",")

    basefile_int = int(bf_split[1])
    extension_int = int(ext_split[1])

    basefile[basefile_select_ind] = f"{bf_split[0]}, {basefile_int+extension_int},{bf_split[2]}"
    log.info(bf_split)
    log.info(ext_split)

if __name__ == '__main__':

    parser = configure_args_parser()
    args = parser.parse_args()

    log_level = getattr(logging, args.loglevel)
    log = setup_logging(log_level)
    log.info(f"# Starting fhir ontology merger with logging level: {args.loglevel}")

    if "ONTOPATH_LEFT" in os.environ and "ONTOPATH_RIGHT" in os.environ and "ONTOPATH_JOINED" in os.environ:
        ontopath_left = os.environ.get("ONTOPATH_LEFT")
        ontopath_right = os.environ.get("ONTOPATH_RIGHT")
        ontopath_joined = os.environ.get("ONTOPATH_JOINED")
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
        ontopath_left_sql = path_for_file(ontopath_left, "R__Load_latest_ui_profile.sql")
        ontopath_right_sql = path_for_file(ontopath_right, "R__Load_latest_ui_profile.sql")
        with open(ontopath_left_sql, "r") as sql_left, open(ontopath_right_sql, "r") as sql_right:
            base_sql = sql_left.readlines()
            extend_sql = sql_right.readlines()

            joinable_copys_with_id = [
                "COPY public.mapping (id, name, type, content) FROM stdin",
                "COPY public.ui_profile (id, name, ui_profile) FROM stdin"

            ]

            for jc in joinable_copys_with_id:
                sql_copy_joiner(base_sql, extend_sql, jc, "\.", True)

            context_id_shift = sql_copy_joiner(base_sql, extend_sql, "COPY public.context (id, system, code, version, display) FROM stdin", "\.", True)
            termcode_id_shift = sql_copy_joiner(base_sql, extend_sql, "COPY public.termcode (id, system, code, version, display) FROM stdin", "\.", True)
            sql_copy_joiner(base_sql, extend_sql, "COPY public.contextualized_termcode (context_termcode_hash, context_id, termcode_id, mapping_id, ui_profile_id) FROM stdin", "\.", False, context_id_shift, termcode_id_shift)

            # Joining select statements, aka adding the values together
            joinable_selects = [
                "SELECT pg_catalog.setval('public.context_id_seq'",
                "SELECT pg_catalog.setval('public.termcode_id_seq'",
                "SELECT pg_catalog.setval('public.criteria_set_id_seq'",
                "SELECT pg_catalog.setval('public.mapping_id_seq'",
                "SELECT pg_catalog.setval('public.ui_profile_id_seq'"
            ]
            for js in joinable_selects:
                sql_select_joiner(base_sql, extend_sql, js)

            with open(ontopath_joined + "migration/" + "R__Load_latest_ui_profile.sql", "w+") as sql_out:
                for line in base_sql:
                    sql_out.write(f"{line}")