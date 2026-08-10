import argparse
import shutil

from common.util.log.functions import get_logger
from common.util.project import Project

_logger = get_logger(__file__)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--project", type=str)
    args = parser.parse_args()

    project = Project(name=args.project)

    _logger.info(f"Parceling the generated ontology for project '{project.name}'")

    ontology_dir = project.output / "merged_ontology"
    temp_ontology_dir = project.output.mkdirs("merged_ontology", "temp")

    _logger.info("Generating mapping archive")
    mapping_dir = ontology_dir / "mapping"
    temp_mapping_dir = project.output.mkdirs("merged_ontology", "temp", "mapping")

    shutil.copytree(mapping_dir, temp_mapping_dir, dirs_exist_ok=True)
    shutil.make_archive(str(mapping_dir), "zip", temp_ontology_dir)
    shutil.rmtree(temp_mapping_dir)

    _logger.info("Generating backend archive")
    temp_backend_dir = project.output.mkdirs("merged_ontology", "temp", "backend")

    shutil.copy(
        project.output.terminology / "terminology_systems.json",
        temp_backend_dir / "terminology_systems.json",
    )
    shutil.copy(
        ontology_dir / "sql_scripts" / "R__load_latest_dse_profiles.sql",
        temp_backend_dir / "R__load_latest_dse_profiles.sql",
    )
    shutil.copy(
        ontology_dir / "sql_scripts" / "R__Load_latest_ui_profile.sql",
        temp_backend_dir / "R__Load_latest_ui_profile.sql",
    )
    shutil.make_archive(str(ontology_dir / "backend"), "zip", temp_backend_dir)
    shutil.rmtree(temp_backend_dir)

    _logger.info("Generating elastic archive")
    elastic_input_dir = project.input.elastic
    elastic_output_dir = ontology_dir / "elastic"
    temp_elastic_dir = project.output.mkdirs("merged_ontology", "temp", "elastic")

    if elastic_output_dir.is_dir() and any(elastic_output_dir.iterdir()):
        content_dir = temp_elastic_dir / "content"
        content_dir.mkdir(parents=True, exist_ok=True)
        shutil.copytree(elastic_output_dir, content_dir, dirs_exist_ok=True)
    else:
        raise FileNotFoundError(f"Missing Elasticsearch index documents @ {repr(elastic_output_dir)}")

    input_index_dir = project.input.elastic / "index"
    if input_index_dir.is_dir() and any(input_index_dir.iterdir()):
        index_dir = temp_elastic_dir / "index"
        index_dir.mkdir(parents=True, exist_ok=True)
        shutil.copytree(input_index_dir, index_dir, dirs_exist_ok=True)
    else:
        _logger.warning("No Elasticsearch index definitions found. Make sure this is correct")

    input_pipeline_dir = project.input.elastic / "pipeline"
    if input_pipeline_dir.is_dir() and any(input_pipeline_dir.iterdir()):
        pipeline_dir = temp_elastic_dir / "pipeline"
        pipeline_dir.mkdir(parents=True, exist_ok=True)
        shutil.copytree(input_pipeline_dir, pipeline_dir, dirs_exist_ok=True)
    else:
        _logger.info("No Elasticsearch pipeline definitions found")

    shutil.make_archive(str(elastic_output_dir), "zip", temp_ontology_dir)
    shutil.rmtree(temp_elastic_dir)

    _logger.info("Cleaning up output")
    shutil.rmtree(temp_ontology_dir)
