import errno
import json
import os
import shutil
from os import path
from jsonschema import validate

from MappingDataModel import generate_map
from UiDataModel import TerminologyEntry, prune_terminology_tree, TermCode
from geccoToUIProfiles import create_terminology_definition_for, get_gecco_categories, IGNORE_CATEGORIES, \
    MAIN_CATEGORIES, IGNORE_LIST, \
    get_specimen, get_consent, resolve_terminology_entry_profile
from termCodeTree import to_term_code_node
from termEntryToExcel import to_csv

GECCO = "de.gecco 1.0.5"
GECCO_DIRECTORY = "de.gecco#1.0.5"
MII_CASE = "de.medizininformatikinitiative.kerndatensatz.fall 1.0.1"
MII_DIAGNOSE = "de.medizininformatikinitiative.kerndatensatz.diagnose 1.0.4"
MII_LAB = "de.medizininformatikinitiative.kerndatensatz.laborbefund 1.0.6"
MII_MEDICATION = "de.medizininformatikinitiative.kerndatensatz.medikation 1.0.10"
MII_PERSON = "de.medizininformatikinitiative.kerndatensatz.person 2.0.0-alpha2"
MII_PROCEDURE = "de.medizininformatikinitiative.kerndatensatz.prozedur 2.0.0-alpha1"
MII_SPECIMEN = "de.medizininformatikinitiative.kerndatensatz.biobank 0.9.0"
core_data_sets = [MII_DIAGNOSE, MII_LAB, MII_MEDICATION, MII_PERSON, MII_PROCEDURE, MII_SPECIMEN, GECCO]


# FIXME:
def mkdir_if_not_exists(directory):
    if not path.isdir(f"./{directory}"):
        try:
            os.system(f"mkdir {directory}")
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise


def download_core_data_set_mii():
    def add_observation_lab_from_mii_to_gecco():
        os.system(f"fhir install {MII_LAB} --here")
        # TODO not hardcoded
        shutil.copy(f"{MII_LAB}/package/"
                    "Profile-ObservationLab.json", f"{GECCO_DIRECTORY}/package/Profile-ObservationLab.json")

    mkdir_if_not_exists("core_data_sets")
    for dataset in core_data_sets:
        mkdir_if_not_exists("core_data_sets")
        saved_path = os.getcwd()
        os.chdir("core_data_sets")
        os.system(f"fhir install {dataset} --here")
        if dataset == GECCO:
            add_observation_lab_from_mii_to_gecco()
        os.chdir(saved_path)


def generate_snapshots():
    data_set_folders = [f.path for f in os.scandir("core_data_sets") if f.is_dir()]
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
    validate(instance=json.load(map_entries_file), schema=json.load(open("schema/term-code-mapping-schema.json")))


def generate_term_code_tree(entries):
    term_code_tree = to_term_code_node(entries)
    term_code_file = open("mapping/" + "codex-code-tree.json", 'w')
    term_code_file.write(term_code_tree.to_json())
    term_code_file.close()
    term_code_file = open("mapping/" + "codex-code-tree.json", 'r')
    validate(instance=json.load(term_code_file), schema=json.load(open("schema/codex-code-tree-schema.json")))


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
            f = open("ui-profiles/" + category.display.replace("/ ", "") + ".json", 'r')
            # validate(instance=json.load(f), schema=json.load(open("schema/ui-profile-schema.json")))
        else:
            gecco.children.append(category)
    f = open("ui-profiles/" + gecco.display + ".json", 'w', encoding="utf-8")
    f.write(gecco.to_json())
    f.close()
    f = open("ui-profiles/" + gecco.display + ".json", 'r')
    # validate(instance=json.load(f), schema=json.load(open("schema/ui-profile-schema.json")))


def generate_result_folder():
    mkdir_if_not_exists("mapping")
    mkdir_if_not_exists("csv")
    mkdir_if_not_exists("ui-profiles")


def remove_resource_name(name_with_resource_name):
    # order matters here!
    resource_names = ["ProfilePatient", "Profile", "LogicalModel", "Condition", "DiagnosticReport", "Observation",
                      "ServiceRequest", "Extension", "ResearchSubject", "Procedure"]
    for resource_name in resource_names:
        name_with_resource_name = name_with_resource_name.replace(resource_name, "")
    return name_with_resource_name


def generate_core_data_set():
    for data_set in core_data_sets:
        if data_set != GECCO:
            module_name = data_set.split(' ')[0].split(".")[-1].capitalize()
            module_code = TermCode("num.abide", module_name, module_name)
            module_category_entry = TerminologyEntry([module_code], "Category", selectable=False, leaf=False)
            data_set = data_set.replace(" ", "#")
            for snapshot in [f"core_data_sets\\{data_set}\\package\\{f.name}" for f in
                             os.scandir(f"core_data_sets\\{data_set}\\package") if
                             not f.is_dir() and "-snapshot" in f.name]:
                with open(snapshot, encoding="UTF-8") as json_file:
                    json_data = json.load(json_file)
                    # Care parentheses matter here!
                    if (kind := json_data.get("kind")) and (kind == "logical"):
                        continue
                    if resource_type := json_data.get("type"):
                        if resource_type == "Bundle":
                            continue
                        elif resource_type == "Extension":
                            continue
                    module_element_name = remove_resource_name(json_data.get("name"))
                    if module_element_name in IGNORE_LIST:
                        continue
                    print(module_element_name)
                    module_element_code = TermCode("num.abide", module_element_name, module_element_name)
                    module_element_entry = TerminologyEntry([module_element_code], "Category", selectable=False,
                                                            leaf=False)
                    resolve_terminology_entry_profile(module_element_entry, f"core_data_sets\\{data_set}\\package")
                    module_category_entry.children.append(module_element_entry)
            f = open("ui-profiles/" + module_category_entry.display + ".json", 'w', encoding="utf-8")
            f.write(module_category_entry.to_json())
            f.close()


if __name__ == '__main__':
    generate_result_folder()
    # ----Time consuming: Only execute initially or on changes----
    # download_core_data_set_mii()
    # generate_snapshots()
    # ------------------------------------------------------------D
    generate_core_data_set()
    category_entries = create_terminology_definition_for(get_gecco_categories())
    # TODO: ones the specimen and consent profiles are declared use them instead!
    category_entries.append(get_specimen())
    category_entries.append(get_consent())
    generate_term_code_mapping(category_entries)
    generate_term_code_tree(category_entries)
    # to_csv(category_entries)
    generate_ui_profiles(category_entries)
