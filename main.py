import errno
import json
import os
import shutil
from os import path

from jsonschema import validate

from FHIRProfileConfiguration import *
from database.DataBaseWriter import DataBaseWriter
from geccoToUIProfiles import create_terminology_definition_for, get_gecco_categories, IGNORE_CATEGORIES, \
    MAIN_CATEGORIES, resolve_terminology_entry_profile, profile_is_of_interest
from model.MappingDataModel import generate_map
from model.UiDataModel import TerminologyEntry, TermCode
from model.termCodeTree import to_term_code_node
from termEntryToExcel import to_csv


def mkdir_if_not_exists(directory):
    if not path.isdir(f"./{directory}"):
        try:
            os.mkdir(directory)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise


def download_core_data_set_mii():
    def add_observation_lab_from_mii_to_gecco():
        os.system(f"fhir install {MII_LAB} --here")
        # TODO not hardcoded
        shutil.copy(f"{MII_LAB}/package/"
                    "Profile-ObservationLab.json", f"{GECCO_DIRECTORY}/package/Profile-ObservationLab.json")

    mkdir_if_not_exists("resources/core_data_sets")
    for dataset in core_data_sets:
        mkdir_if_not_exists("resources/core_data_sets")
        saved_path = os.getcwd()
        os.chdir("resources/core_data_sets")
        os.system(f"fhir install {dataset} --here")
        if dataset == GECCO:
            add_observation_lab_from_mii_to_gecco()
        os.chdir(saved_path)


def generate_snapshots():
    data_set_folders = [f.path for f in os.scandir("resources/core_data_sets") if f.is_dir()]
    saved_path = os.getcwd()
    for folder in data_set_folders:
        os.chdir(f"{folder}\\package")
        os.system(f"fhir install hl7.fhir.r4.core")
        for file in [f for f in os.listdir('.') if
                     os.path.isfile(f) and is_structured_definition(f) and "-snapshot" not in f]:
            os.system(f"fhir push {file}")
            os.system(f"fhir snapshot")
            os.system(f"fhir save {file[:-5]}-snapshot.json")
        os.chdir(saved_path)


def is_structured_definition(file):
    with open(file, encoding="UTF-8") as json_file:
        json_data = json.load(json_file)
        if json_data.get("resourceType") == "StructureDefinition":
            return True
        return False


def generate_term_code_mapping(entries):
    map_entries = generate_map(entries)
    map_entries_file = open("mapping/" + "codex-term-code-mapping.json", 'w')
    map_entries_file.write(map_entries.to_json())
    map_entries_file.close()
    map_entries_file = open("mapping/" + "codex-term-code-mapping.json", 'r')
    # validate(instance=json.load(map_entries_file), schema=json.load(open(
    #     "resources/schema/term-code-mapping-schema.json")))


def generate_term_code_tree(entries):
    term_code_tree = to_term_code_node(entries)
    term_code_file = open("mapping/" + "codex-code-tree.json", 'w')
    term_code_file.write(term_code_tree.to_json())
    term_code_file.close()
    term_code_file = open("mapping/" + "codex-code-tree.json", 'r')
    validate(instance=json.load(term_code_file), schema=json.load(open("resources/schema/codex-code-tree-schema.json")))


def generate_ui_profiles(entries):
    gecco_term_code = [TermCode("num.codex", "GECCO", "GECCO")]
    gecco = TerminologyEntry(gecco_term_code, "CategoryEntry", leaf=False, selectable=False)
    gecco.display = "GECCO"
    for category in entries:
        if category in IGNORE_CATEGORIES:
            continue
        if category.display in MAIN_CATEGORIES:
            f = open("ui-profiles/" + category.display.replace("/ ", "") + ".json", 'w', encoding="utf-8")
            f.write(category.to_json())
            f.close()
            validate_ui_profile(category.display.replace("/ ", ""))
        else:
            gecco.children.append(category)
    f = open("ui-profiles/" + gecco.display + ".json", 'w', encoding="utf-8")
    f.write(gecco.to_json())
    f.close()
    validate_ui_profile(gecco.display)


def validate_ui_profile(profile_name):
    f = open("ui-profiles/" + profile_name + ".json", 'r')
    validate(instance=json.load(f), schema=json.load(open("resources/schema/ui-profile-schema.json")))


def generate_result_folder():
    mkdir_if_not_exists("mapping")
    mkdir_if_not_exists("csv")
    mkdir_if_not_exists("ui-profiles")


def remove_resource_name(name_with_resource_name):
    # order matters here!
    resource_names = ["ProfilePatient", "Profile", "LogicalModel", "Condition", "DiagnosticReport", "Observation",
                      "ServiceRequest", "Extension", "ResearchSubject", "Procedure", "_MII_"]
    for resource_name in resource_names:
        name_with_resource_name = name_with_resource_name.replace(resource_name, "")
    return name_with_resource_name


def get_data_set_snapshots(data_set):
    return [f"resources/core_data_sets/{data_set}/package/{f.name}" for f in
            os.scandir(f"resources/core_data_sets/{data_set}/package") if
            not f.is_dir() and "-snapshot" in f.name]


def get_module_category_entry_from_module_name(module_name):
    module_code = TermCode("mii.abide", module_name, module_name)
    return TerminologyEntry([module_code], "Category", selectable=False, leaf=False)


def generate_core_data_set():
    core_data_set_modules = []
    for data_set in [core_data_set for core_data_set in core_data_sets if core_data_set != GECCO]:
        module_name = data_set.split(' ')[0].split(".")[-1].capitalize()
        module_category_entry = get_module_category_entry_from_module_name(module_name)
        data_set = data_set.replace(" ", "#")
        for snapshot in get_data_set_snapshots(data_set):
            with open(snapshot, encoding="UTF-8") as json_file:
                json_data = json.load(json_file)
                module_element_name = remove_resource_name(json_data.get("name"))
                if not profile_is_of_interest(json_data, module_element_name):
                    continue
                module_element_code = TermCode("mii.abide", module_element_name, module_element_name)
                module_element_entry = TerminologyEntry([module_element_code], "Category", selectable=False,
                                                        leaf=False)
                resolve_terminology_entry_profile(module_element_entry,
                                                  data_set=f"resources/core_data_sets/{data_set}/package")
                if module_category_entry.display == module_element_entry.display:
                    # Resolves issue like : -- Prozedure                 --Prozedure
                    #                           -- Prozedure     --->      -- BILDGEBENDE DIAGNOSTIK
                    #                              -- BILDGEBENDE DIAGNOSTIK
                    module_category_entry.children += module_element_entry.children
                else:
                    module_category_entry.children.append(module_element_entry)
        move_back_other(module_category_entry.children)
        f = open("ui-profiles/" + module_category_entry.display + ".json", 'w', encoding="utf-8")
        if len(module_category_entry.children) == 1:
            f.write(module_category_entry.children[0].to_json())
        else:
            f.write(module_category_entry.to_json())
        f.close()
        validate_ui_profile(module_category_entry.display)
        core_data_set_modules.append(module_category_entry)
    return core_data_set_modules


def move_back_other(entries):
    entries_copy = entries.copy()
    for entry in entries_copy:
        for other_naming in ["Sonstige", "sonstige", "andere", "Andere", "Weitere", "Other"]:
            if entry.termCode.display.startswith(other_naming):
                entries.remove(entry)
                entries.append(entry)
        if entry.children:
            move_back_other(entry.children)


if __name__ == '__main__':
    generate_result_folder()
    # ----Time consuming: Only execute initially or on changes----
    # download_core_data_set_mii()
    # generate_snapshots()
    # -------------------------------------------------------------

    core_data_category_entries = generate_core_data_set()

    category_entries = []
    if GECCO in core_data_sets:
        category_entries = create_terminology_definition_for(get_gecco_categories())
    # TODO: ones the consent profiles are declared use them instead!
    move_back_other(category_entries)
    generate_ui_profiles(category_entries)

    category_entries += core_data_category_entries
    dbw = DataBaseWriter()
    dbw.add_ui_profiles_to_db(category_entries)
    generate_term_code_mapping(category_entries)
    generate_term_code_tree(category_entries)
    # to_csv(category_entries)

    # dump data from db with
    # docker exec -t 7ac5bfb77395 pg_dump --dbname="codex_ui" --username=codex-postgres
    # --table=UI_PROFILE_TABLE > ui_profile_dump_230822
