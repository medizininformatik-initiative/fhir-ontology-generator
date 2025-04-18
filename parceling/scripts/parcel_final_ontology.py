import argparse
import shutil

from common.util.log.functions import get_logger
from common.util.project import Project

logger = get_logger(__file__)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--project', type=str)
    args = parser.parse_args()

    project = Project(name=args.project)

    logger.info(f"Parceling the generated ontology for project '{project.name}'")

    ontology_dir = project.output("merged_ontology")
    temp_ontology_dir = project.output("merged_ontology", "temp")

    logger.info("Generating mapping archive")
    mapping_dir = ontology_dir / "mapping"
    temp_mapping_dir = project.output("merged_ontology", "temp", "mapping")

    shutil.copytree(mapping_dir, temp_mapping_dir, dirs_exist_ok=True)
    shutil.make_archive(str(mapping_dir), 'zip', temp_ontology_dir)
    shutil.rmtree(temp_mapping_dir)

    logger.info("Generating backend archive")
    temp_backend_dir = project.output("merged_ontology", "temp", "backend")

    shutil.copy(ontology_dir / 'profile_tree.json', temp_backend_dir / 'profile_tree.json')
    shutil.copy(project.output("terminology") / "terminology_systems.json",
                temp_backend_dir / 'terminology_systems.json')
    shutil.copy(ontology_dir / 'sql_scripts' / 'R__load_latest_dse_profiles.sql',
                temp_backend_dir / 'R__load_latest_dse_profiles.sql')
    shutil.copy(ontology_dir / 'sql_scripts' / 'R__Load_latest_ui_profile.sql',
                temp_backend_dir / 'R__Load_latest_ui_profile.sql')
    shutil.make_archive(str(ontology_dir / 'backend'), 'zip', temp_backend_dir)
    shutil.rmtree(temp_backend_dir)

    logger.info("Generating elastic archive")
    elastic_input_dir = project.input("elastic")
    elastic_output_dir = ontology_dir / 'elastic'
    temp_elastic_dir = project.output("merged_ontology", "temp", "elastic")

    shutil.copytree(elastic_output_dir, temp_elastic_dir, dirs_exist_ok=True)
    shutil.copy(elastic_input_dir / 'codeable_concept_index.json',
                temp_elastic_dir / 'codeable_concept_index.json')
    shutil.copy(elastic_input_dir / 'ontology_index.json',
                temp_elastic_dir / 'ontology_index.json')
    shutil.make_archive(str(elastic_output_dir), 'zip', temp_ontology_dir)
    shutil.rmtree(temp_elastic_dir)

    logger.info("Cleaning up output")
    shutil.rmtree(temp_ontology_dir)



