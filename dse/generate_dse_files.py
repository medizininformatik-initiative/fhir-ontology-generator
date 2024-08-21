import argparse
import os
import json

from core.ProfileDetailGenerator import ProfileDetailGenerator
from core.ProfileTreeGenerator import ProfileTreeGenerator


def configure_args_parser():

    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('--download_packages', action='store_true')

    return arg_parser

def download_simplifier_packages(package_names):

    os.chdir("dse-packages")

    for package in package_names:
        os.system(f"fhir install {package} --here")

def generate_r_load_sql(profile_details):

    with open("generated/R__load_latest_dse_profiles.sql", "w+") as sql_file:
        sql_file.write("DELETE FROM dse_profile;\n")
        sql_file.write("ALTER SEQUENCE public.dse_profile_id_seq RESTART WITH 1;\n")
        sql_file.write("INSERT INTO dse_profile(id, url, entry) VALUES \n")
        index = 1

        for profile_detail in profile_details:
            value_line = f"({index},'{profile_detail['url']}','{json.dumps(profile_detail)}')\n"
            sql_file.write(value_line)
            index = index + 1


if __name__ == '__main__':

    parser = configure_args_parser()
    args = parser.parse_args()

    if args.download_packages:
        with open("required-packages.json", "r") as f:
            required_packages = json.load(f)

        download_simplifier_packages(required_packages)

    with open("exclude-dirs.json", "r") as f:
        exclude_dirs = json.load(f)

    packages_dir = f"{os.getcwd()}/dse-packages/dependencies"

    tree_generator = ProfileTreeGenerator(packages_dir, exclude_dirs)
    tree_generator.get_profiles()
    profile_tree = tree_generator.generate_profiles_tree()

    with open("generated/profile_tree.json", "w") as f:
        json.dump(profile_tree, f)


    mapping_type_code = {"Observation": "code",
                         "Condition": "code",
                         "Consent": "provision.provision.code",
                         "Procedure": "code",
                         "MedicationAdministration": "medication.code",
                         "Specimen": "type"
                         }

    blacklistedValueSets = ['http://hl7.org/fhir/ValueSet/observation-codes']

    profiles = tree_generator.profiles
    profile_detail_generator = ProfileDetailGenerator(profiles, mapping_type_code, blacklistedValueSets)
    profile_details = []

    for profile in profiles:

        profile_detail = profile_detail_generator.generate_detail_for_profile(profiles[profile])
        if profile_detail:
            profile_details.append(profile_detail)

    with open("generated/profile_details_all.json", "w+") as p_details_f:
        json.dump(profile_details, p_details_f)

    generate_r_load_sql(profile_details)
