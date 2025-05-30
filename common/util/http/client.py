from typing import Mapping, Optional

from requests import Session, Response
from requests.auth import AuthBase

from common.util.http.exceptions import raise_appropriate_exception
from common.util.http.url import insert_path_params, format_query_params, merge_urls


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

    def __determine_url(self, context_path: Optional[str] = None, full_url: Optional[str] = None,
                        path_params: Optional[Mapping[str, str]] = None) -> str:
        url = full_url if full_url is not None else merge_urls(self.__base_url, context_path)
        return insert_path_params(url, **(path_params if path_params else {}))

    def get(self, context_path: Optional[str] = None, full_url: Optional[str] = None, headers: Mapping[str, str] = None,
            path_params: Mapping[str, str] = None, query_params: Mapping[str, str | list[str]] = None) -> Response:
        request_url = self.__determine_url(context_path, full_url, path_params)
        response = self.__session.get(request_url, params=format_query_params(query_params), headers=headers,
                                      timeout=self.__timeout)
        if response.ok: return response
        else: raise_appropriate_exception(response)

    def post(self, context_path: Optional[str] = None, full_url: Optional[str] = None, body: str = None,
             headers: Mapping[str, str] = None, path_params: Mapping[str, str] = None,
             query_params: Mapping[str, str | list[str]] = None) -> Response:
        if not body:
            raise ValueError("Body of a POST request cannot be empty")
        request_url = self.__determine_url(context_path, full_url, path_params)
        response = self.__session.post(request_url, data=body.encode('utf-8'), params=format_query_params(query_params),
                                       headers=headers, timeout=self.__timeout)
        if response.ok: return response
        else: raise_appropriate_exception(response)

    def delete(self, context_path: Optional[str] = None, full_url: Optional[str] = None,
               headers: Mapping[str, str] = None, path_params: Mapping[str, str] = Response,
               query_params: Mapping[str, str | list[str]] = None) -> Response:
        request_url = self.__determine_url(context_path, full_url, path_params)
        response = self.__session.delete(request_url, params=query_params, headers=headers, timeout=self.__timeout)
        if response.ok: return response
        else: raise_appropriate_exception(response)