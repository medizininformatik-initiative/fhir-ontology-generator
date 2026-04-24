import json
from abc import ABC, abstractmethod
from typing import List, Dict, Optional

import cachetools
from pydantic import BaseModel, PrivateAttr

from cohort_selection_ontology.model.query_metadata import ResourceQueryingMetaData
from common.model.fhir.structure_definition import StructureDefinitionSnapshot
from common.util.log.functions import get_logger
from common.util.project import Project

_logger = get_logger(__name__)


class ResourceQueryingMetaDataResolver(BaseModel, ABC):
    """
    Abstract class for resolving querying metadata for a given fhir profile and context
    """

    @abstractmethod
    def get_query_meta_data(
        self,
        fhir_profile_snapshot: str | StructureDefinitionSnapshot,
        module_name: Optional[str] = None,
    ) -> List[ResourceQueryingMetaData]:
        """
        Returns the query metadata for the given FHIR profile snapshot in the specified context
        :param fhir_profile_snapshot: The FHIR profile snapshot. Either URL string or the structure definition itself
        :param module_name: (Optional) name of the module from which to retrieve the querying metadata
        :return: Query metadata
        """
        pass


class StandardDataSetQueryingMetaDataResolver(ResourceQueryingMetaDataResolver):
    __project: Project = PrivateAttr()

    def __init__(self, project: Project):
        """
        :project Project: The Project instance this resolver operates on.
        """
        super().__init__()
        self.__project = project
        self.__metadata_mapping_cache = dict()

    @cachetools.cachedmethod(
        lambda self: self.__metadata_mapping_cache, lambda _, module_name: module_name
    )
    def __load_profile_to_metadata_mapping(
        self, module_name: str
    ) -> Dict[str, List[str]]:
        """
        Loads the profile to metadata mapping from a JSON file.
        :param module_name: Name of the module to load mapping for
        :return: A dictionary mapping profile names to lists of metadata names.
        """
        mapping_file = (
            self.__project.input.cso.mkdirs("modules", module_name)
            / "profile_to_query_meta_data_resolver_mapping.json"
        )
        with open(mapping_file, mode="r", encoding="utf-8") as f:
            return json.load(f)

    def get_query_meta_data(
        self,
        fhir_profile_snapshot: str | StructureDefinitionSnapshot,
        module_name: Optional[str] = None,
    ) -> List[ResourceQueryingMetaData]:
        """
        Retrieves query metadata for a given FHIR profile snapshot.
        :param fhir_profile_snapshot: The FHIR profile snapshot. Either URL string or the structure definition itself
        :param module_name: (Optional) name of the module from which to retrieve the querying metadata
        :return: A list of ResourceQueryingMetaData objects.
        """
        result = []
        if isinstance(fhir_profile_snapshot, str):
            fhir_profile_snapshot = self.__project.package_manager.find_snapshot(fhir_profile_snapshot)
        profile_name = fhir_profile_snapshot.name
        module_paths = (
            [self.__project.input.cso / "modules" / module_name]
            if module_name
            else [
                m
                for m in (self.__project.input.cso / "modules").iterdir()
                if m.is_dir()
            ]
        )
        for mp in module_paths:
            profile_to_metadata_mapping = self.__load_profile_to_metadata_mapping(
                mp.name
            )
            if profile_name in profile_to_metadata_mapping:
                for metadata_name in profile_to_metadata_mapping[profile_name]:
                    metadata_file = (
                        self.__project.input.cso.mkdirs(
                            "modules", module_name, "QueryingMetaData"
                        )
                        / f"{metadata_name}QueryingMetaData.json"
                    )
                    with open(metadata_file, mode="r", encoding="utf-8") as file:
                        result.append(ResourceQueryingMetaData.from_json(file))
        if not result:
            _logger.warning(
                f"No query metadata mapping found for profile [name={repr(profile_name)}"
                + (f", module={repr(module_name)}]" if module_name else "]")
            )
        return result
