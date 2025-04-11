import argparse
import shutil

from util.log.functions import get_logger
from util.project import Project

logger = get_logger(__file__)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--project', type=str)
    args = parser.parse_args()

    project = Project(name=args.project)

    logger.info(f"Parceling the generated ontology for project '{project.name}'")

    ontology_dir = project.output("merged_ontology")
    mapping_dir = ontology_dir / "mapping"

    logger.info("Generating mapping archive")
    temp_ontology_dir = project.output("merged_ontology", "temp") / "mapping"

    shutil.copytree(mapping_dir, temp_ontology_dir)
    shutil.make_archive(str(mapping_dir), 'zip', temp_ontology_dir)
    shutil.rmtree(temp_ontology_dir)

    logger.info("Generating backend archive")
    temp_ontology_dir = project.output("merged_ontology", "temp", "backend")

    shutil.copy(ontology_dir / 'profile_tree.json', temp_ontology_dir / 'profile_tree.json')
    shutil.copy(project.output("terminology") / "terminology_systems.json",
                temp_ontology_dir / 'terminology_systems.json')
    shutil.copy(ontology_dir / 'sql_scripts' / 'R__load_latest_dse_profiles.sql',
                temp_ontology_dir / 'R__load_latest_dse_profiles.sql')
    shutil.copy(ontology_dir / 'sql_scripts' / 'R__Load_latest_ui_profile.sql',
                temp_ontology_dir / 'R__Load_latest_ui_profile.sql')
    shutil.make_archive(str(ontology_dir / 'backend'), 'zip', temp_ontology_dir)
    shutil.rmtree(temp_ontology_dir)

    logger.info("Generating elastic archive")
    temp_ontology_dir = project.output("merged_ontology", "temp") / "elastic"

    shutil.copytree(ontology_dir / 'elastic', temp_ontology_dir)
    shutil.copy(project.input() / 'elastic' / 'codeable_concept_index.json',
                temp_ontology_dir / 'codeable_concept_index.json')
    shutil.copy(project.input() / 'elastic' / 'ontology_index.json',
                temp_ontology_dir / 'ontology_index.json')
    shutil.make_archive(str(ontology_dir / 'elastic'), 'zip', temp_ontology_dir)
    shutil.rmtree(temp_ontology_dir)

    shutil.rmtree(project.output("merged_ontology", "temp"))



