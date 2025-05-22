import json
import os
from pathlib import Path

import pytest

def __test_dir() -> Path:
    return Path(os.path.dirname(os.path.realpath(__file__))).resolve()

@pytest.fixture(scope="session")
def test_dir() -> Path:
    return __test_dir()

@pytest.fixture(scope="session")
def schema_store(test_dir) -> dict:
    store = {}
    base_path = os.path.join(test_dir,"schemata","common")
    print(base_path)

    print(os.listdir(base_path))

    for schema in os.listdir(base_path):
        # schemas = os.path.join(base_path, schemas)
        if schema.endswith(".json"):
            with open(os.path.join(base_path, schema), 'r', encoding="UTF-8") as f:
                schema = json.load(f)
                if "$id" in schema:
                    store[schema["$id"]] = schema

    return store
