import argparse
import importlib.resources
import os
import shutil
import resources.terminology

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--ontology_dir', type=str)
    args = parser.parse_args()

    # create mapping.zip
    temp_ontology_dir = f'{args.ontology_dir}/ontology'
    os.makedirs(temp_ontology_dir, exist_ok=True)

    shutil.copytree(f'{args.ontology_dir}/mapping', f'{temp_ontology_dir}/mapping')
    shutil.make_archive(f'{args.ontology_dir}/mapping', 'zip', temp_ontology_dir)
    shutil.rmtree(f'{temp_ontology_dir}/mapping')

    # create backend.zip
    temp_ontology_dir = f'{args.ontology_dir}/ontology/backend'
    os.makedirs(temp_ontology_dir, exist_ok=True)
    shutil.copy(f'{args.ontology_dir}/profile_tree.json', f'{temp_ontology_dir}/profile_tree.json')
    with importlib.resources.path(resources.terminology, 'terminology_systems.json') as file:
        shutil.copy(file, f'{temp_ontology_dir}/terminology_systems.json')
    shutil.copy(f'{args.ontology_dir}/sql_scripts/R__load_latest_dse_profiles.sql', f'{temp_ontology_dir}/R__load_latest_dse_profiles.sql')
    shutil.copy(f'{args.ontology_dir}/sql_scripts/R__Load_latest_ui_profile.sql', f'{temp_ontology_dir}/R__Load_latest_ui_profile.sql')
    shutil.make_archive(f'{args.ontology_dir}/backend', 'zip', f'{args.ontology_dir}/ontology/backend')
    shutil.rmtree(f'{temp_ontology_dir}')

    # create elastic.zip
    temp_ontology_dir = f'{args.ontology_dir}/ontology'
    os.makedirs(temp_ontology_dir, exist_ok=True)
    shutil.copytree(f'{args.ontology_dir}/elastic', f'{temp_ontology_dir}/elastic')
    shutil.copy(f'{args.ontology_dir}/elastic-additional-files/codeable_concept_index.json',
                f'{temp_ontology_dir}/elastic/codeable_concept_index.json')
    shutil.copy(f'{args.ontology_dir}/elastic-additional-files/ontology_index.json',
                f'{temp_ontology_dir}/elastic/ontology_index.json')
    shutil.make_archive(f'{args.ontology_dir}/elastic', 'zip', temp_ontology_dir)
    shutil.rmtree(f'{temp_ontology_dir}/elastic')

    shutil.rmtree(f'{args.ontology_dir}/ontology')



