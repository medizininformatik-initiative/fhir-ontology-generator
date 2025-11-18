import json
import os
import fastjsonschema
import pytest
from json_source_map import calculate
from os.path import basename
from pathlib import Path
from cohort_selection_ontology.model.query_metadata import ResourceQueryingMetaData
from common.util.log.functions import get_logger

logger = get_logger(__file__)


def validate_json_with_file(file: Path, schema: Path, schema_store: dict):
    logger.info(f"Validating {file} with: {schema}")
    with open(file) as f:
        raw = f.read()
        json_file = json.loads(raw)
        pointer_map = calculate(raw)
    with open(schema) as f:
        json_schema = json.load(f)
    return validate_json_object(json_file, json_schema, schema_store, file, schema)


def validate_json_object(
    json_content: dict,
    json_schema: dict,
    schema_store: dict = None,
    json_file: Path | bool = 0,
    schema_file: Path = 0,
):
    def handler(uri: str):
        if uri in schema_store:
            return schema_store[uri]
        raise ValueError(f"Unknown schema reference: {uri}")

    validate = fastjsonschema.compile(json_schema, handlers={"https": handler})
    try:
        validate(json_content)
    except fastjsonschema.exceptions.JsonSchemaValueException as exc:
        filename_with_coords = "ProvidedJsonObj"
        # loading pointer_map for detailed output on console in case of an error
        if json_file != 0:
            with open(json_file) as f:
                raw = f.read()
                pointer_map = calculate(raw)
            pointer = "/" + "/".join(str(p) for p in exc.path)
            loc = pointer_map.get(
                pointer
            )  # clickable in many IDEs/terminals - id does not work in PyCharm

            if loc is not None:
                value_info = loc.to_dict().get("value", {})
                line = value_info.get("line", 0) + 1
                column = value_info.get("column", 0) + 1
                filename_with_coords = f"{json_file}:{line}:{column}"
            else:
                logger.debug(f"Pointer not found in pointer_map: {pointer}")
                filename_with_coords = f"{json_file}"
        pytest.fail(
            f"\n "
            f"\t\t ------------------------- {basename(json_file)} failed --------------------------- \n"
            f"\t\t | Reason:        {exc.message} \n"
            f"\t\t | Content:       {exc.value} \n"
            f"\t\t | Broken rule:   {exc.rule} \n"
            f"\t\t | Path to error: {list(exc.path)} \n"
            f"\t\t | File:          {filename_with_coords} \n"
            f"\t\t | Schema id:     {json_schema.get('$id')} \n"
            f"\t\t ---------------------------------------------------------------------------------- \n",
            pytrace=False,
        )
        return False
    else:
        return True


def test_criterion_definition_validity(
    querying_metadata: ResourceQueryingMetaData, querying_metadata_schema: dict
):
    assert validate_json_object(
        json.loads(querying_metadata.to_json()), querying_metadata_schema
    )


def test_json_integrity_profile_tree(test_dir, project, schema_store):
    profile_tree_file = project.output / "merged_ontology" / "profile_tree.json"
    profile_tree_schema_file = Path(test_dir, "schemata", "profile_tree_schema.json")
    assert validate_json_with_file(
        file=profile_tree_file,
        schema=profile_tree_schema_file,
        schema_store=schema_store,
    )


def test_json_integrity_term_code_info(test_dir, project, schema_store):
    term_code_info_folder = project.output / "merged_ontology" / "term-code-info"
    term_code_info_schema_file = Path(
        test_dir, "schemata", "term_code_info_schema.json"
    )

    for term_code_file in os.listdir(term_code_info_folder):
        term_code_file = term_code_info_folder / term_code_file
        assert validate_json_with_file(
            file=Path(term_code_file),
            schema=term_code_info_schema_file,
            schema_store=schema_store,
        )


def test_json_integrity_ui_trees(test_dir, project, schema_store):
    ui_tree_folder = project.output / "merged_ontology" / "ui-trees"
    ui_tree_schema_file = Path(test_dir, "schemata", "ui_tree_schema.json")

    for ui_tree_file in os.listdir(ui_tree_folder):
        ui_tree_file = ui_tree_folder / ui_tree_file
        assert validate_json_with_file(
            file=ui_tree_file, schema=ui_tree_schema_file, schema_store=schema_store
        )


def test_json_integrity_criteria_sets(test_dir, project, schema_store):
    criteria_sets = project.output / "merged_ontology" / "criteria-sets"
    criteria_sets_schema_file = Path(test_dir, "schemata", "criteria-sets_schema.json")

    for ui_tree_file in os.listdir(criteria_sets):
        ui_tree_file = criteria_sets / ui_tree_file
        assert validate_json_with_file(
            file=ui_tree_file,
            schema=criteria_sets_schema_file,
            schema_store=schema_store,
        )


def test_json_integrity_mapping_cql(test_dir, project, schema_store):
    mapping_cql = (
        project.output / "merged_ontology" / "mapping" / "cql" / "mapping_cql.json"
    )
    mapping_cql_schema_file = Path(test_dir, "schemata", "mapping_cql_schema.json")
    assert validate_json_with_file(
        file=mapping_cql, schema=mapping_cql_schema_file, schema_store=schema_store
    )


def test_json_integrity_mapping_fhir(test_dir, project, schema_store):
    mapping_fhir = (
        project.output / "merged_ontology" / "mapping" / "fhir" / "mapping_fhir.json"
    )
    mapping_fhir_schema_file = Path(test_dir, "schemata", "mapping_fhir_schema.json")
    assert validate_json_with_file(
        file=mapping_fhir, schema=mapping_fhir_schema_file, schema_store=schema_store
    )


def test_json_integrity_mapping_tree(test_dir, project, schema_store):
    mapping_tree = project.output / "merged_ontology" / "mapping" / "mapping_tree.json"
    mapping_tree_schema_file = Path(test_dir, "schemata", "mapping_tree_schema.json")
    assert validate_json_with_file(
        file=mapping_tree, schema=mapping_tree_schema_file, schema_store=schema_store
    )


def test_json_integrity_mapping_tree_dse(test_dir, project, schema_store):
    mapping_tree_dse = (
        project.output / "merged_ontology" / "mapping" / "dse_mapping_tree.json"
    )
    mapping_tree_dse_schema_file = Path(
        test_dir, "schemata", "mapping_tree_dse_schema.json"
    )
    assert validate_json_with_file(
        file=mapping_tree_dse,
        schema=mapping_tree_dse_schema_file,
        schema_store=schema_store,
    )

def test_terminology_systems_output(test_dir, project, schema_store):
    terminology_systems = project.output / "terminology" / "terminology_systems.json"
    terminology_systems_schema_file = Path(test_dir, "schemata", "terminology_systems_schema.json")
    assert validate_json_with_file(file=terminology_systems, schema=terminology_systems_schema_file, schema_store=schema_store)


def test_json_integrity_elastic_file(json_file, test_dir, schema_store):
    elastic_ontology_index_schema_file = Path(
        test_dir, "schemata", "elastic_ontology_index_schema.json"
    )
    with open(elastic_ontology_index_schema_file, "r", encoding="UTF-8") as f:
        elastic_ontology_index_schema_file = json.load(f)

    elastic_ontology_content_schema_file = Path(
        os.path.join(test_dir, "schemata", "elastic_ontology_content_schema.json")
    )
    with open(elastic_ontology_content_schema_file, "r", encoding="UTF-8") as f:
        elastic_ontology_content_schema_file = json.load(f)

    def handler(uri: str):
        if uri in schema_store:
            return schema_store[uri]
        raise ValueError(f"Unknown schema reference: {uri}")

    validate_content = fastjsonschema.compile(
        elastic_ontology_content_schema_file, handlers={"https": handler}
    )
    validate_index = fastjsonschema.compile(
        elastic_ontology_index_schema_file, handlers={"https": handler}
    )

    logger.info(f"Currently testing: {json_file}")
    line_number = 0
    with open(json_file) as f:
        while True:
            elastic_ontology_index_line = f.readline()
            if not elastic_ontology_index_line:
                break  # eof

            elastic_ontology_content_line = f.readline()
            if not elastic_ontology_content_line:
                break  # eof

            elastic_ontology_index_line = json.loads(elastic_ontology_index_line)
            elastic_ontology_content_line = json.loads(elastic_ontology_content_line)

            line_number += 2

            try:
                assert validate_index(elastic_ontology_index_line)
                assert validate_content(elastic_ontology_content_line)

            except fastjsonschema.exceptions.JsonSchemaValueException as exc:
                logger.error(
                    f"Validation for {basename(json_file)} failed because:  \n{exc.message} \n"
                    f"Path to error: {list(exc.path)} \n"
                    f"Absolute path to error: {list(exc.name)} \n"
                )
            except Exception as e:
                logger.error(f"LineNumber: {line_number}")
