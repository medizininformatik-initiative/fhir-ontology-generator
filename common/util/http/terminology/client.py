from datetime import datetime
from pathlib import Path
from typing import Mapping, Optional, List, Literal

from fhir.resources.R4B.bundle import Bundle, BundleEntry, BundleEntryRequest
from fhir.resources.R4B.codesystem import CodeSystem
from fhir.resources.R4B.conceptmap import ConceptMap
from fhir.resources.R4B.parameters import Parameters
from fhir.resources.R4B.valueset import ValueSet
from requests.auth import AuthBase

from common.config.project import HTTPConfig
from common.util.fhir.bundle import BundleType
from common.util.http.client import BaseClient
from common.util.http.exceptions import ClientError
from common.util.project import Project


class FhirTerminologyClient(BaseClient):
    __content_type_header: tuple[str, str] = ("Content-Type", "application/fhir+json")
    __accept_header: tuple[str, str] = ("Accept", "application/fhir+json")
    __headers = dict([__content_type_header, __accept_header])

    def __init__(
        self,
        base_url: str,
        auth: Optional[type[AuthBase]] = None,
        cert: Optional[tuple[str, str]] = None,
        timeout: float = 60,
        http_config: HTTPConfig = None,
    ):
        super().__init__(base_url=base_url, auth=auth, cert=cert, timeout=timeout, http_config=http_config)

    @staticmethod
    def from_project(
        project: Project, auth: Optional[type[AuthBase]] = None, timeout: float = 60
    ):
        if "ONTOLOGY_SERVER_ADDRESS" in project.env:
            base_url = project.env["ONTOLOGY_SERVER_ADDRESS"]
        else:
            raise ValueError(
                "Server base URL has to be provided either explicitly through the `base_url` parameter"
                "or implicitly via environment variable `ONTOLOGY_SERVER_ADDRESS`"
            )
        if "SERVER_CERTIFICATE" in project.env and "PRIVATE_KEY" in project.env:
            cert = (
                Path(project.env["SERVER_CERTIFICATE"]),
                Path(project.env["PRIVATE_KEY"]),
            )
        else:
            cert = None
        return FhirTerminologyClient(base_url, auth, cert, timeout, project.config.http)

    @classmethod
    def __build_bundle(
        cls, bundle_type: BundleType, bundle_entries: List[BundleEntry]
    ) -> Bundle:
        return Bundle(
            type=bundle_type.value,
            timestamp=datetime.now(),
            total=len(bundle_entries),
            entry=bundle_entries,
        )

    def search_value_set(self, url: str) -> list[ValueSet]:
        bundle = self.get(
            "/ValueSet", headers=dict([self.__accept_header]), query_params={"url": url}
        ).json()
        return [
            ValueSet.model_validate(entry["resource"])
            for entry in bundle.get("entry", [])
            if "resource" in entry
        ]

    def get_value_set(self, id: str) -> Optional[ValueSet]:
        try:
            response = self.get(
                "/ValueSet/{id}",
                headers=dict([self.__accept_header]),
                path_params={"id": id},
            )
            return ValueSet.model_validate_json(response.text)
        except ClientError as err:
            if err.status_code == 404:
                return None  # Not found
            else:
                raise

    def expand_value_set(
        self, url: str, version: Optional[str] = None
    ) -> Optional[Mapping[str, any]]:
        return self.get(
            "/ValueSet/$expand",
            headers=dict([self.__accept_header]),
            query_params={"url": url, "version": version},
        ).json()

    def search_code_system(self, **search_params) -> Bundle:
        bundle = self.get(
            "/CodeSystem",
            headers=dict([self.__accept_header]),
            query_params=search_params,
        ).json()
        return Bundle(**bundle)

    def get_code_system(self, id: str) -> Optional[CodeSystem]:
        try:
            response = self.get(
                "/CodeSystem/{id}",
                headers=dict([self.__accept_header]),
                path_params={"id": id},
            )
            return CodeSystem.model_validate_json(response.text)
        except ClientError as err:
            if err.status_code == 404:
                return None  # Not found
            else:
                raise

    def code_system_lookup(
        self,
        system: str,
        code: str,
        version: Optional[str] = None,
        properties: Optional[List[str]] = None,
    ) -> Parameters:
        response = self.get(
            "/CodeSystem/$lookup",
            headers=self.__headers,
            query_params={
                "system": system,
                "code": code,
                "version": version,
                "property": properties,
            },
        )
        return Parameters.model_validate_json(response.text)

    def closure(self, parameters: Parameters) -> ConceptMap:
        response = self.post(
            "/$closure",
            headers=dict([self.__content_type_header]),
            body=parameters.model_dump_json(),
        )
        return ConceptMap(**response.json())

    def bulk_lookup(
        self,
        parameters: List[Parameters],
        mode: Literal[
            BundleType.BATCH, BundleType.TRANSACTION
        ] = BundleType.TRANSACTION,
    ) -> Bundle:
        entries = [
            BundleEntry(
                resource=p,
                request=BundleEntryRequest(method="POST", url="CodeSystem/$lookup"),
            )
            for p in parameters
        ]
        bundle = self.__build_bundle(mode, entries)
        response = self.post(
            headers=dict([self.__content_type_header]), body=bundle.model_dump_json()
        )
        return Bundle(**response.json())