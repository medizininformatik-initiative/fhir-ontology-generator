import errno
import json
import os
import shutil
from os import path
from jsonschema import validate

from MappingDataModel import generate_map
from UiDataModel import TerminologyEntry, prune_terminology_tree, TermCode
from geccoToUIProfiles import create_terminology_definition_for, get_categories, IGNORE_CATEGORIES, MAIN_CATEGORIES, \
    get_specimen, get_consent
from termCodeTree import to_term_code_node
from termEntryToExcel import to_csv


GECCO_VERSION = "de.gecco 1.0.4"
GECCO_DIRECTORY = "de.gecco#1.0.4"
MII_LAB_VERSION = "de.medizininformatikinitiative.kerndatensatz.laborbefund 1.0.2"


def mkdir_if_not_exists(directory):
    if not path.isdir(f"./{directory}"):
        try:
            os.system(f"mkdir {directory}")
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise


def download_gecco_profile():
    def add_observation_lab_from_mii_to_gecco():
        os.system(f"fhir install {MII_LAB_VERSION} --here")
        # TODO not hardcoded
        shutil.copy(f"{GECCO_DIRECTORY}/package/Profile-ObservationLab.json",
                    "de.medizininformatikinitiative.kerndatensatz.laborbefund#1.0.2/package/"
                    "Profile-ObservationLab.json")

    mkdir_if_not_exists("geccoDataSet")
    mkdir_if_not_exists("mapping")
    mkdir_if_not_exists("csv")
    mkdir_if_not_exists("ui-profiles")
    saved_path = os.getcwd()
    os.chdir("geccoDataSet")
    os.system(f"fhir install {GECCO_VERSION} --here")
    add_observation_lab_from_mii_to_gecco()
    os.chdir(saved_path)


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
    others_term_code = [TermCode("num.codex", "Andere", "Andere")]
    others = TerminologyEntry(others_term_code, "CategoryEntry", selectable=False)
    others.display = "Andere"
    for category in entries:
        if category in IGNORE_CATEGORIES:
            continue
        if category.display in MAIN_CATEGORIES:
            f = open("ui-profiles/" + category.display.replace("/ ", "") + ".json", 'w', encoding="utf-8")
            f.write(category.to_json())
            f.close()
            f = open("ui-profiles/" + category.display.replace("/ ", "") + ".json", 'r')
            validate(instance=json.load(f), schema=json.load(open("schema/ui-profile-schema.json")))
        else:
            others.children.append(category)
    f = open("ui-profiles/" + others.display + ".json", 'w', encoding="utf-8")
    f.write(others.to_json())
    f.close()
    f = open("ui-profiles/" + others.display + ".json", 'r')
    validate(instance=json.load(f), schema=json.load(open("schema/ui-profile-schema.json")))


if __name__ == '__main__':
    download_gecco_profile()
    category_entries = create_terminology_definition_for(get_categories())
    # TODO: ones the specimen and consent profiles are declared use them instead!
    category_entries.append(get_specimen())
    category_entries.append(get_consent())
    generate_term_code_mapping(category_entries)
    generate_term_code_tree(category_entries)
    for entry in category_entries:
        prune_terminology_tree(entry, 2)
    to_csv(category_entries)
    generate_ui_profiles(category_entries)
