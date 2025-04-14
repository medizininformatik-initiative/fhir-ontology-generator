from typing import Mapping, Optional

from requests import Session, Response
from requests.auth import AuthBase

from common.util import raise_appropriate_exception
from common.util.http.url import insert_path_params, format_query_params


class BaseClient:
    __session: Session
    __base_url: str
    __timeout: float

    def __init__(self, base_url: str, auth: Optional[type[AuthBase]] = None, cert: Optional[tuple[str, str]] = None,
                 timeout: float = 60):
        self.__session = Session()
        self.__session.auth = auth
        self.__session.cert = cert
        self.__base_url = base_url
        self.__timeout = timeout


    def _get_session(self) -> Session:
        return self.__session

    def _get_base_url(self) -> str:
        return self.__base_url

    def _get_timeout(self) -> float:
        return self.__timeout

    def __del__(self):
        self.__session.close()

    def get(self, url, headers: Mapping[str, str] = None, path_params: Mapping[str, str] = None,
            query_params: Mapping[str, str | list[str]] = None) -> Response:
        request_url = insert_path_params(url, **path_params) if path_params is not None else url
        response = self.__session.get(request_url, params=format_query_params(query_params), headers=headers,
                                      timeout=self.__timeout)
        if response.ok: return response
        else: raise_appropriate_exception(response)

    def post(self, url, body: str, headers: Mapping[str, str] = None, path_params: Mapping[str, str] = None,
             query_params: Mapping[str, str | list[str]] = None) -> Response:
        request_url = insert_path_params(url, **path_params) if path_params is not None else url
        response = self.__session.post(request_url, data=body, params=format_query_params(query_params),
                                       headers=headers, timeout=self.__timeout)
        if response.ok: return response
        else: raise_appropriate_exception(response)

    def delete(self, url, headers: Mapping[str, str] = None, path_params: Mapping[str, str] = Response,
               query_params: Mapping[str, str | list[str]] = None) -> Response:
        request_url = insert_path_params(url, **path_params) if path_params is not None else url
        response = self.__session.delete(request_url, params=query_params, headers=headers, timeout=self.__timeout)
        if response.ok:
            return response
        else:
            raise_appropriate_exception(response)