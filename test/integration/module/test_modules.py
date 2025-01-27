import json
import logging
from typing import Mapping

import jsonschema
import pytest

from model.ResourceQueryingMetaData import ResourceQueryingMetaData


logger = logging.getLogger(__name__)


def test_valid_criterion_definition(querying_metadata: ResourceQueryingMetaData,
                                    querying_metadata_schema: Mapping[str, any]):
    # Validate Querying Metadata against schema
    try:
        jsonschema.validate(instance=json.loads(querying_metadata.to_json()), schema=querying_metadata_schema)
    except jsonschema.exceptions.ValidationError as exc:
        pytest.fail(f"JSON schema validation failed. Reason: {exc.cause}")


#def test_