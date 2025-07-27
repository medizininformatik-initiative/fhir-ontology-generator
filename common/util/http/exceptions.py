import abc
from typing import Optional

import requests
from pydantic import conint
from requests import Response, Request, request


class HttpError(Exception, abc.ABC):
    status_code: conint(ge=400, lt=600)
    request: Request
    response: Response
    reason: Optional[str]
    text: Optional[str]

    def __init__(
        self,
        status_code: conint(ge=400, lt=600),
        request: requests.Request,
        response: requests.Response,
        reason: Optional[str] = None,
        text: Optional[str] = None,
    ):
        super().__init__(
            f"Request failed with status code {status_code}"
            + (f". Reason: {reason}" if reason is not None else "")
            + (f". Details: {text}" if text is not None else "")
        )
        self.status_code = status_code
        self.request = request
        self.response = response
        self.reason = reason
        self.text = text


class ClientError(HttpError):
    status_code: conint(ge=400, lt=500)

    def __init__(
        self,
        status_code: conint(ge=400, lt=500),
        request: requests.Request,
        response: requests.Response,
        reason: Optional[str] = None,
        text: Optional[str] = None,
    ):
        super().__init__(status_code, request, response, reason, text)


class ServerError(HttpError):
    status_code: conint(ge=500, lt=600)

    def __init__(
        self,
        status_code: conint(ge=500, lt=600),
        request: requests.Request,
        response: requests.Response,
        reason: Optional[str] = None,
        text: Optional[str] = None,
    ):
        super().__init__(status_code, request, response, reason, text)


def raise_appropriate_exception(request: Request, response: Response) -> None:
    try:
        text = response.text
    except:
        text = None

    if 400 <= response.status_code < 500:
        raise ClientError(
            response.status_code, request, response, response.reason, text
        )
    elif 500 <= response.status_code < 600:
        raise ServerError(
            response.status_code, request, response, response.reason, text
        )
