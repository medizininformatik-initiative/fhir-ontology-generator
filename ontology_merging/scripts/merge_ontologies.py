import argparse
import json
import os
import shutil

from fhir.resources.R4B.codesystem import CodeSystem

from cohort_selection_ontology.model.ui_data import (
    TranslationDisplayElement,
    Translation,
)
from common.util.http.terminology.client import FhirTerminologyClient
from common.util.log.functions import get_logger
from common.util.project import Project
from common.util.sql.merging import SqlMerger


logger = get_logger(__file__)


def configure_args_parser():
    arg_parser = argparse.ArgumentParser(description='Generate the UI-Profile of the core data set for the MII-FDPG')
    arg_parser.add_argument('--merge_mappings', action='store_true')
    arg_parser.add_argument('--merge_uitrees', action='store_true')
    arg_parser.add_argument('--merge_sqldump', action='store_true')
    arg_parser.add_argument('--merge_dse', action='store_true')
    arg_parser.add_argument(
        '-dp', '--project',
        required=True,  # Makes this argument required
        help="Project to merge ontology files for"
    )
    return arg_parser


def path_for_file(base, file_name):
    for root, dir, files in os.walk(base):
        if file_name in files:
            return os.path.join(root, file_name)
    logger.error(f"No file {file_name} in {base}")
    quit()


def load_ontology_file(onto_dir, file_name):
    file_path = path_for_file(onto_dir, file_name)
    with open(file_path, mode="r", encoding="utf-8") as file:
        return json.load(file)


def write_json_to_file(filepath, object):
    with open(filepath, mode="w+", encoding="utf-8") as file:
        json.dump(object, file)


def add_system_urls_to_systems_json(project: Project, system_urls):

    with open(
        project.input.mkdirs("terminology") / "terminology_systems.json",
        mode="r",
        encoding="utf-8",
    ) as systems_file:
        terminology_systems = json.load(systems_file)

        for term_system in terminology_systems:
            if term_system.get("url") in system_urls:
                system_urls.remove(term_system.get("url"))

        client = FhirTerminologyClient.from_project(project)

        for key in system_urls:
            cs: CodeSystem = max(
                client.search_code_system(url=key).entry,
                key=lambda e: e.resource.version,
            ).resource

            cs_display = TranslationDisplayElement(
                original=(cs.name if cs.name else cs.title),
                translations=[
                    Translation(
                        language="en", value=(cs.name if cs.name else cs.title)
                    ),
                    Translation(
                        language="de", value=(cs.name if cs.name else cs.title)
                    ),
                ],
            )

            terminology_systems.append(
                {"url": key, "display": cs_display.model_dump()}
            )

        terminology_systems = sorted(terminology_systems, key=lambda x: x["url"])

        with open(
            project.output.mkdirs("terminology") / os.path.basename(systems_file.name),
            mode="w",
            encoding="utf-8",
        ) as output_file:
            json.dump(terminology_systems, output_file)


def collect_all_terminology_systems(merged_ontology_dir):
    system_urls = set()

    cur_ui_termcode_info_dir = os.path.join(merged_ontology_dir, "term-code-info")
    for file_name in os.listdir(cur_ui_termcode_info_dir):
        with open(os.path.join(cur_ui_termcode_info_dir, file_name), mode="r", encoding="utf-8") as termcode_info_file:
            termcode_infos = json.load(termcode_info_file)

            for termcode_info in termcode_infos:
                system_url = termcode_info["term_code"]["system"]
                system_urls.add(system_url)

    cur_ui_value_set_dir = os.path.join(merged_ontology_dir, "value-sets")
    for file_name in os.listdir(cur_ui_value_set_dir):

        if not file_name.endswith(".json"):
            continue

        with open(os.path.join(cur_ui_value_set_dir, file_name), mode="r", encoding="utf-8") as value_set_file:

            value_set = json.load(value_set_file)

            if "contains" not in value_set["expansion"]:
                continue

            for termcode in value_set["expansion"]["contains"]:
                system_url = termcode["system"]
                system_urls.add(system_url)

    return system_urls


if __name__ == '__main__':
    parser = configure_args_parser()
    args = parser.parse_args()

    logger.info("Running FHIR Ontology Merger")
    logger.info(f"Merging ontologies for project '{args.project}'")

    project = Project(args.project)
    modules_dir = project.output.cso.mkdirs("modules")
    module_dirs = list(map(lambda d: d.path, filter(lambda e: e.is_dir(), os.scandir(modules_dir))))
    output_dir = project.output.mkdirs("merged_ontology")

    if args.merge_mappings:
        logger.info("Merging CCDL mappings")
        mapping_cql = []
        mapping_fhir = []
        mapping_tree = []

        for module in module_dirs:
            mapping_cql = mapping_cql + load_ontology_file(module, "mapping_cql.json")
            mapping_fhir = mapping_fhir + load_ontology_file(module, "mapping_fhir.json")

            cur_ui_tree_dir = modules_dir / module / "ui-trees"
            for filename in os.listdir(cur_ui_tree_dir):
                cur_mapping_tree = load_ontology_file(cur_ui_tree_dir, filename)
                mapping_tree.extend(cur_mapping_tree)

        cql_dir = output_dir / "mapping" / "cql"
        fhir_dir = output_dir / "mapping" / "fhir"
        os.makedirs(cql_dir, exist_ok=True)
        os.makedirs(fhir_dir, exist_ok=True)

        write_json_to_file(cql_dir / "mapping_cql.json", mapping_cql)
        write_json_to_file(fhir_dir / "mapping_fhir.json", mapping_fhir)
        write_json_to_file(output_dir / "mapping" / "mapping_tree.json", mapping_tree)

    if args.merge_uitrees:
        logger.info("Merging UI trees")
        output_ui_tree_dir = output_dir / "ui-trees"
        os.makedirs(output_ui_tree_dir, exist_ok=True)

        output_ui_termcode_info_dir = output_dir / "term-code-info"
        os.makedirs(output_ui_termcode_info_dir, exist_ok=True)

        output_crit_set_dir = output_dir / "criteria-sets"
        os.makedirs(output_crit_set_dir, exist_ok=True)

        output_value_set_dir = output_dir / "value-sets"
        os.makedirs(output_value_set_dir, exist_ok=True)

        for module in module_dirs:
            cur_ui_tree_dir = modules_dir / module / "ui-trees"
            for filename in os.listdir(cur_ui_tree_dir):
                shutil.copy(cur_ui_tree_dir / filename, output_ui_tree_dir / filename)

            cur_ui_termcode_info_dir = modules_dir / module / "term-code-info"
            for filename in os.listdir(cur_ui_termcode_info_dir):
                shutil.copy(cur_ui_termcode_info_dir / filename,
                            output_ui_termcode_info_dir / filename)

            cur_crit_set_dir = modules_dir / module / "criteria-sets"
            for filename in os.listdir(cur_crit_set_dir):
                shutil.copy(cur_crit_set_dir / filename, output_crit_set_dir / filename)

            cur_value_set_dir = modules_dir / module / "value-sets"
            for filename in os.listdir(cur_value_set_dir):
                shutil.copy(cur_value_set_dir / filename, output_value_set_dir / filename)

    if args.merge_sqldump:
        logger.info("Merging SQL dumps")
        output_sql_script_dir = output_dir / "sql_scripts"
        sql_script_index = 0
        os.makedirs(output_sql_script_dir, exist_ok=True)

        for module in module_dirs:
            shutil.copy(modules_dir / module / "R__Load_latest_ui_profile.sql",
                        output_sql_script_dir / f"R__Load_latest_ui_profile_{str(sql_script_index)}.sql")

            sql_script_index += 1

        sql_merger = SqlMerger(sql_script_dir=output_sql_script_dir)
        sql_merger.execute_merge()
        sql_merger.shutdown()

    if args.merge_dse:
        logger.info("Merging DSE content")
        dse_output_dir = project.output.dse

        dse_value_set_dir = dse_output_dir / "value-sets"
        output_value_set_dir = output_dir / "value-sets"
        os.makedirs(output_value_set_dir, exist_ok=True)
        for filename in os.listdir(dse_value_set_dir):
            shutil.copy(dse_value_set_dir / filename, output_value_set_dir / filename)

        output_sql_script_dir = output_dir / "sql_scripts"
        os.makedirs(output_sql_script_dir, exist_ok=True)
        shutil.copy(dse_output_dir / "R__load_latest_dse_profiles.sql",
                    output_sql_script_dir / "R__load_latest_dse_profiles.sql")

        shutil.copy(dse_output_dir / "profile_tree.json",
                    output_dir / "profile_tree.json")

        shutil.copy(dse_output_dir / "dse_mapping_tree.json",
                    output_dir / "mapping" / "dse_mapping_tree.json")

    system_urls = collect_all_terminology_systems(output_dir)

    add_system_urls_to_systems_json(project, system_urls)
