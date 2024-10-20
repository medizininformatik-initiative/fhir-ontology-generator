from abc import ABC, abstractmethod
from typing import List

from model.ResourceQueryingMetaData import ResourceQueryingMetaData


class ResourceQueryingMetaDataResolver(ABC):
    """
    Abstract class for resolving querying meta data for a given fhir profile and context
    """

    @abstractmethod
    def get_query_meta_data(self, fhir_profile_snapshot: dict, module_name: str, _context=None) -> List[ResourceQueryingMetaData]:
        """
        Returns the query meta data for the given FHIR profile snapshot in the specified context
        :param fhir_profile_snapshot: FHIR profile snapshot
        :param module_name: Directory of the specific FHIR profile
        :return: Query meta data
        """
        pass
