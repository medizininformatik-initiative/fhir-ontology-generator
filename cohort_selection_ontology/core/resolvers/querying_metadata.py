import json
from abc import ABC, abstractmethod
from typing import List, Dict

from model.ResourceQueryingMetaData import ResourceQueryingMetaData
from model.UiDataModel import TermCode
from common.util.log.functions import get_class_logger
from common.util.project import Project


class ResourceQueryingMetaDataResolver(ABC):
    """
    Abstract class for resolving querying metadata for a given fhir profile and context
    """

    @abstractmethod
    def get_query_meta_data(self, fhir_profile_snapshot: dict, module_name: str, _context=None) -> List[ResourceQueryingMetaData]:
        """
        Returns the query metadata for the given FHIR profile snapshot in the specified context
        :param fhir_profile_snapshot: FHIR profile snapshot
        :param module_name: Directory of the specific FHIR profile
        :return: Query metadata
        """
        pass


class StandardDataSetQueryingMetaDataResolver(ResourceQueryingMetaDataResolver):
    __logger = get_class_logger("StandardDataSetQueryingMetaDataResolver")

    __project: Project

    def __init__(self, project: Project):
        super().__init__()
        self.__project = project

    def __load_profile_to_metadata_mapping(self, module_name) -> Dict[str, List[str]]:
        """
        Loads the profile to metadata generators from a JSON file.
        :param module_name: Name of the module to load generators for
        :return: A dictionary generators profile names to lists of metadata names.
        """
        mapping_file = self.__project.input("modules", module_name) / "profile_to_query_meta_data_resolver_mapping.json"
        with open(mapping_file, mode="r", encoding="utf-8") as f:
            return json.load(f)

    def get_query_meta_data(
        self, fhir_profile_snapshot: dict, module_name, _context: TermCode = None
    ) -> List[ResourceQueryingMetaData]:
        """
        Retrieves query metadata for a given FHIR profile snapshot.
        :param fhir_profile_snapshot: The FHIR profile snapshot.
        :param module_name: Name of the module from which to retrieve the querying metadata
        :param _context: The context term code (unused in this implementation).
        :return: A list of ResourceQueryingMetaData objects.
        """
        result = []
        profile_name = fhir_profile_snapshot.get("name")
        profile_to_metadata_mapping = self.__load_profile_to_metadata_mapping(module_name)
        if profile_name in profile_to_metadata_mapping:
            for metadata_name in profile_to_metadata_mapping[profile_name]:
                metadata_file = (self.__project.input("modules", module_name, "QueryingMetaData") /
                                 f"{metadata_name}QueryingMetaData.json")
                with open(metadata_file, "r") as file:
                    result.append(ResourceQueryingMetaData.from_json(file))
        else:
            self.__logger.warning(f"No query metadata generators found for profile: {profile_name}")
        return result