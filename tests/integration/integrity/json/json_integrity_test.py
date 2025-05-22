import json
import os

import jsonschema

from json_source_map import calculate

from os.path import basename
from pathlib import Path

from networkx.algorithms.bipartite.projection import project

from common.util.log.functions import get_logger

from jsonschema import RefResolver

logger = get_logger(__file__)

def validate_json_with_file(file: Path, schema: Path, schema_store: dict):
    logger.info(f"Validating {file} : with :{schema}")
    with open(file) as f:
        raw = f.read()
        json_file = json.loads(raw)
        pointer_map = calculate(raw)
    with open(schema) as f:
        json_schema = json.load(f)

    #registry = Registry(retrieve_from_filesystem)

    resolver = RefResolver.from_schema(json_schema, store=schema_store)

    try:
        jsonschema.validate(instance=json_file, schema=json_schema, resolver=resolver)
    except jsonschema.ValidationError as exc:
        pointer = "/" + "/".join(str(p) for p in exc.absolute_path)
        print(pointer_map.get(pointer))
        loc = pointer_map[pointer].to_dict().get("value")
        line = loc.get("line", 0) + 1  # json-source-map uses 0-based index
        column = loc.get("column", 0) + 1

        clickable = f"{file}:{line}:{column}"  # clickable in many IDEs/terminals
        print(clickable)

        clickable_pycharm = f'File "{clickable}", line {line}, in {exc.path}: mmm'

        logger.error(f"Validation for {basename(file)} failed because:  \n{exc.message} \n"
                     f"Path to error: {list(exc.path)} \n"
                     f"Absolute path to error: {list(exc.absolute_path)} \n"
                     f"{clickable_pycharm}")
        # logger.error(f"Error: {exc}")
        return False
    except jsonschema.SchemaError as exc:
        logger.error(f"Validation for {basename(schema)} failed because:  \n"
                     f"Path to error: {list(exc.path)} \n"
                     f"Absolute path to error: {list(exc.absolute_path)} \n"
                     f"{exc.message} \n")
    else:
        return True

def test_json_integrity_profile_tree(test_dir, project, schema_store):
    profile_tree_file = project.output /  "merged_ontology" / "profile_tree.json"
    profile_tree_schema_file = Path(os.path.join(test_dir,"schemata", "profile_tree_schema.json"))

    assert True == validate_json_with_file(file=profile_tree_file, schema=profile_tree_schema_file, schema_store=schema_store)

def test_json_integrity_term_code_info(test_dir, project, schema_store):
    term_code_info_folder = project.output / "merged_ontology" / "term-code-info"
    term_code_info_schema_file = Path(os.path.join(test_dir, "schemata", "term_code_info_schema.json"))

    for term_code_file in os.listdir(term_code_info_folder):
        term_code_file = term_code_info_folder / term_code_file
        assert True == validate_json_with_file(file=Path(term_code_file), schema=term_code_info_schema_file, schema_store=schema_store)

def test_json_integrity_ui_trees(test_dir, project, schema_store):
    ui_tree_folder = project.output / "merged_ontology" /"ui-trees"
    ui_tree_schema_file = Path(os.path.join(test_dir, "schemata", "ui_tree_schema.json"))

    for ui_tree_file in os.listdir(ui_tree_folder):
        ui_tree_file = ui_tree_folder / ui_tree_file
        assert True == validate_json_with_file(file=ui_tree_file, schema=ui_tree_schema_file, schema_store=schema_store)
