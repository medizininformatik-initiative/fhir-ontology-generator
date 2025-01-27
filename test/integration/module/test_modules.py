import logging

from model.ResourceQueryingMetaData import ResourceQueryingMetaData
from util.backend.FeasibilityBackendClient import FeasibilityBackendClient


logger = logging.getLogger(__name__)


def test_criterion(querying_metadata: ResourceQueryingMetaData, backend_client: FeasibilityBackendClient):
    logger.info(f"Testing criterion '{querying_metadata.module}-{querying_metadata.name}'")
