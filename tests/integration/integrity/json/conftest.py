import json
import os
import pytest

@pytest.fixture(scope="session")
def schema_store() -> dict:
    store = {}
    base_path = os.path.abspath("schemata/common")

    print(os.listdir(base_path))

    for schema in os.listdir(base_path):
        # schemas = os.path.join(base_path, schemas)
        if schema.endswith(".json"):
            with open(os.path.join(base_path, schema), 'r', encoding="UTF-8") as f:
                schema = json.load(f)
                if "$id" in schema:
                    store[schema["$id"]] = schema

    return store
