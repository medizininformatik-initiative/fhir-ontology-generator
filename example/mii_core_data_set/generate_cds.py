import argparse
import json
import os
from typing import List

from FHIRProfileConfiguration import *
from TerminologService.ValueSetResolver import get_term_entries_by_id
from helper import download_simplifier_packages, generate_snapshots, load_querying_meta_data, write_object_as_json
from main import generate_result_folder
from model.ResourceQueryingMetaData import ResourceQueryingMetaData
from model.UiDataModel import TermEntry, TermCode

core_data_sets = [MII_CONSENT, MII_DIAGNOSE, MII_LAB, MII_MEDICATION, MII_PERSON, MII_PROCEDURE, MII_SPECIMEN]


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
    module_code = TermCode("mii.fdpg.cds", module_name, module_name)
    return TermEntry([module_code], "Category", selectable=False, leaf=False)


def generate_ui_trees(differential_dir: str):
    """
    Generates the ui trees for all FHIR profiles in the differential directory
    :param differential_dir: path to the directory which contains the FHIR profiles
    :return: ui trees for all FHIR profiles in the differential directory
    """
    result: List[TermEntry] = []
    for folder in [folder for folder in os.scandir(differential_dir) if folder.is_dir()]:
        files = [file for file in os.scandir(f"{differential_dir}/{folder.name}/package") if file.is_file()
                 and file.name.endswith("snapshot.json")]
        result.append(generate_module_ui_tree("mii.fdpg.cds", folder.name, folder.name, files))
    return result


def write_ui_trees_to_files(ui_trees: List[TermEntry]):
    """
    Writes the ui trees to the ui-profiles folder
    :param ui_trees: ui trees to write
    """
    for ui_tree in ui_trees:
        write_object_as_json(ui_tree, f"ui-profiles/{ui_tree.display}.json")


# Todo: this should be an abstract method that has to be implemented for each use-case
# Todo: move this concrete implementation elsewhere
def get_query_meta_data(fhir_profile_snapshot: dict, context: TermCode) -> List[ResourceQueryingMetaData]:
    """
    Returns the query meta data for the given FHIR profile snapshot
    :param fhir_profile_snapshot: FHIR profile snapshot
    :param context: context of the FHIR profile snapshot
    :return: Query meta data
    """
    return [resource_querying_meta_data for resource_querying_meta_data
            in load_querying_meta_data("resources/QueryingMetaData") if
            resource_querying_meta_data.context == context and
            resource_querying_meta_data.resource_type == fhir_profile_snapshot["type"]]


def generate_ui_subtree(fhir_profile_snapshot: dict, context: TermCode = None) -> List[TermEntry]:
    """
    Generates the ui subtree for the given FHIR profile snapshot
    :param fhir_profile_snapshot: FHIR profile snapshot json representation
    :param context: of the parent node | None if this is the root node
    :return: root of the ui subtree
    """
    module_context = context if context else TermCode("mii.fdpg.cds", fhir_profile_snapshot["name"],
                                                      fhir_profile_snapshot["name"])
    applicable_querying_meta_data = get_query_meta_data(fhir_profile_snapshot, module_context)
    if not applicable_querying_meta_data:
        print(f"No querying meta data found for {fhir_profile_snapshot['name']}")
    return translate(fhir_profile_snapshot, applicable_querying_meta_data)


def translate(fhir_profile_snapshot: dict, applicable_querying_meta_data: List[ResourceQueryingMetaData]) \
        -> List[TermEntry]:
    """
    Translates the given FHIR profile snapshot into a ui tree
    :param fhir_profile_snapshot: FHIR profile snapshot json representation
    :param applicable_querying_meta_data: applicable querying meta data
    :return: root of the ui tree
    """
    result: List[TermEntry] = []
    for applicable_querying_meta_data in applicable_querying_meta_data:
        print(f"Translating {fhir_profile_snapshot['name']} with {applicable_querying_meta_data}")
        if applicable_querying_meta_data.term_code_defining_id:
            result += get_term_entries_by_id(applicable_querying_meta_data.term_code_defining_id, fhir_profile_snapshot)
        elif applicable_querying_meta_data.term_codes:
            result += [TermEntry(applicable_querying_meta_data.term_codes)]
    return result


def generate_module_ui_tree(module_system: str, module_code: str, module_display: str, files: List[str]) -> TermEntry:
    """
    Generates the ui tree for the given module
    :param module_system: system of the module
    :param module_code: code of the module if unsure use the same as module_name 
    :param module_display: name of the module
    :param files: FHIR profiles snapshot paths in the module
    :return: 
    """
    if len(files) == 1:
        with open(files[0], 'r') as snapshot:
            snapshot_json = json.load(snapshot)
            root = TermEntry([TermCode(module_system, snapshot_json.get("name"), snapshot_json.get("name"))],
                             "Category", selectable=False, leaf=False)
            root.children = generate_ui_subtree(snapshot_json)
            return root
    else:
        module_context = TermCode(module_system, module_code, module_display)
        root = TermEntry([module_context], "Category", selectable=False,
                         leaf=False)
        for snapshot_file in files:
            with open(snapshot_file) as snapshot:
                root.children += generate_ui_subtree(json.load(snapshot), module_context)
        return root


def write_cds_ui_profile(module_category_entry):
    """
    Writes the ui profile for the given module category entry to the ui-profiles folder
    :param module_category_entry: name of the module category entry
    """
    f = open("ui-profiles/" + module_category_entry.display + ".json", 'w', encoding="utf-8")
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
    arg_parser.add_argument('--generate_snapshot', action='store_true')
    arg_parser.add_argument('--generate_csv', action='store_true')
    return arg_parser


if __name__ == '__main__':
    parser = configure_args_parser()
    args = parser.parse_args()

    generate_result_folder()

    # ----Time consuming: Only execute initially or on changes----
    if args.generate_snapshot:
        download_simplifier_packages(core_data_sets)
        generate_snapshots("resources/core_data_sets")
        generate_snapshots("resources/fdpg_differential", core_data_sets)
    # -------------------------------------------------------------

    ui_trees = generate_ui_trees("resources/fdpg_differential")
    write_ui_trees_to_files(ui_trees)

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
