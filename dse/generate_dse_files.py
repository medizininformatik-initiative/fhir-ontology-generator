import argparse
import os
import json
import requests
from urllib.parse import urlparse

from core.ProfileDetailGenerator import ProfileDetailGenerator
from core.ProfileTreeGenerator import ProfileTreeGenerator
from TerminologService.TermServerConstants import TERMINOLOGY_SERVER_ADDRESS, SERVER_CERTIFICATE, PRIVATE_KEY

def configure_args_parser():

    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('--download_packages', action='store_true')
    arg_parser.add_argument('--generate_profile_details', action='store_true')
    arg_parser.add_argument('--download_value_sets', action='store_true')
    return arg_parser

def download_simplifier_packages(package_names):

    os.chdir("dse-packages")

    for package in package_names:
        os.system(f"fhir install {package} --here")

def download_and_save_value_set(value_set_url, session):
    value_set_folder = 'generated/value-sets'

    onto_server_value_set_url = f'{TERMINOLOGY_SERVER_ADDRESS}ValueSet/$expand?url={value_set_url}'

    response = session.get(onto_server_value_set_url, cert=(SERVER_CERTIFICATE, PRIVATE_KEY))

    if response.status_code == 200:
        value_set_data = response.json()
        value_set_name = value_set_data.get('name', urlparse(value_set_data.get('url')).path.split('/ValueSet/', 1)[-1].replace('/', ''))

        with open(f"{value_set_folder}/{value_set_name}.json", "w+") as value_set_file:
            json.dump(value_set_data, value_set_file)

def download_all_value_sets(profile_details):

    session = requests.Session()

    value_set_urls = set()

    for detail in profile_details:
        for filter in (filter for filter in detail['filters'] if filter['ui_type'] == 'code'):
            for value_set_url in filter['valueSetUrls']:
                value_set_urls.add(value_set_url)

    for value_set_url in list(value_set_urls):
        download_and_save_value_set(value_set_url, session)

def generate_r_load_sql(profile_details):

    with open("generated/R__load_latest_dse_profiles.sql", "w+") as sql_file:
        sql_file.write("DELETE FROM dse_profile;\n")
        sql_file.write("ALTER SEQUENCE public.dse_profile_id_seq RESTART WITH 1;\n")
        sql_file.write("INSERT INTO dse_profile(id, url, entry) VALUES \n")

        for index, profile_detail in enumerate(profile_details):

            profile_detaildb = json.dumps(profile_detail).replace("'", "''")
            value_line = f"({index + 1},'{profile_detail['url']}','{profile_detaildb}')"
            sql_file.write(value_line)
            if index < len(profile_details) - 1:
                sql_file.write(",\n")
            else:
                sql_file.write(";")


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

    module_order = ["Diagnose", "Prozedur", "Person", "Labor", "Medikation", "Fall", "Biobank", "Consent"]

    tree_generator = ProfileTreeGenerator(packages_dir, exclude_dirs, module_order)
    tree_generator.get_profiles()



    profile_tree_translations = {}
    with open("profile_tree_translations.json", "r") as f:
        translations_list = json.load(f)
        for translated_profile in translations_list:
            profile_tree_translations[translated_profile["url"]] = translated_profile

    profile_tree = tree_generator.generate_profiles_tree(profile_tree_translations)

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

    if args.generate_profile_details:

        profiles = tree_generator.profiles
        fields_to_exclude = [".meta", ".id", ".subject"]
        profile_detail_generator = ProfileDetailGenerator(profiles, mapping_type_code, blacklistedValueSets, fields_to_exclude)
        profile_details = []

        with open("profile_details_all_translations.json", "r") as f:
            translated_profiles = json.load(f)

        for profile in profiles:

            profile_detail = profile_detail_generator.generate_detail_for_profile(profiles[profile])
            profile_detail = profile_detail_generator.translate_detail_for_profile(profile_detail, translated_profiles)

            if profile_detail:
                profile_details.append(profile_detail)

        with open("generated/profile_details_all.json", "w+") as p_details_f:
            json.dump(profile_details, p_details_f)

        generate_r_load_sql(profile_details)

        if args.download_value_sets:
            download_all_value_sets(profile_details)
