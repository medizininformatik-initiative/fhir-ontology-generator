import json
import os
import shutil
from typing import List

from jsonschema import validate

from FHIRProfileConfiguration import *
from helper import mkdir_if_not_exists


def add_observation_lab_from_mii_to_gecco():
    os.system(f"fhir install {MII_LAB} --here")
    # TODO not hardcoded
    shutil.copy(f"{MII_LAB}/package/"
                "Profile-ObservationLab.json", f"{GECCO_DIRECTORY}/package/Profile-ObservationLab.json")


def download_simplifier_packages_with_GECCO(package_names: List[str]):
    """
    Downloads the core data set from the MII and saves the profiles in the resources/core_data_sets folder
    """

    mkdir_if_not_exists("resources/core_data_sets")
    for dataset in package_names:
        saved_path = os.getcwd()
        os.chdir("resources/core_data_sets")
        os.system(f"fhir install {dataset} --here")
        if dataset == GECCO:
            add_observation_lab_from_mii_to_gecco()
        os.chdir(saved_path)


def validate_ui_profile(profile_name: str):
    """
    Validates the ui profile with the given name against the ui profile schema
    :param profile_name: name of the ui profile
    :raises: jsonschema.exceptions.ValidationError if the ui profile is not valid
             jsonschema.exceptions.SchemaError if the ui profile schema is not valid
    """
    f = open("ui-profiles/" + profile_name + ".json", 'r')
    validate(instance=json.load(f), schema=json.load(open("resources/schema/ui-profile-schema.json")))


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


