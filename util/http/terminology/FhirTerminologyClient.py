from typing import Mapping, Optional

from requests import Session
from requests.auth import AuthBase

from util.http.BaseClient import BaseClient
from util.http.exceptions.ClientError import ClientError
from util.http.url import merge_urls


class FhirTerminologyClient(BaseClient):
    __content_type_header: tuple[str, str] = ("Content-Type", "application/fhir+json")
    __accept_header: tuple[str, str] = ("Accept", "application/fhir+json")
    __headers = dict([__content_type_header, __accept_header])

    def __init__(self, base_url: str, auth: Optional[type[AuthBase]] = None, cert: Optional[tuple[str, str]] = None,
                 timeout: float = 60):
        super().__init__(base_url, auth, cert, timeout)

    def __del__(self):
        super().__del__()

    def search_value_set(self, url: str) -> list[Mapping[str, any]]:
        bundle = self.get(merge_urls(self._get_base_url(), "/ValueSet"),
                          headers=dict([self.__accept_header]), query_params={'url': url}).json()
        return [entry.get("resource") for entry in bundle.get("entry", []) if "resource" in entry]

    def get_value_set(self, id: str) -> Optional[Mapping[str, any]]:
        try:
            return self.get(merge_urls(self._get_base_url(), "/ValueSet/{id}"),
                            headers=dict([self.__accept_header]), path_params={'id': id}).json()
        except ClientError as err:
            if err.status_code == 404: return None # Not found
            else: raise

    def expand_value_set(self, url: str, version: Optional[str] = None) -> Optional[Mapping[str, any]]:
        return self.get(merge_urls(self._get_base_url(), "/ValueSet/$expand"),
                        headers=dict([self.__accept_header]), query_params={'url': url, 'version': version}).json()