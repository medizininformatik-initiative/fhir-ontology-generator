from typing import Optional

from pydantic import conint
from requests import Response
from requests.exceptions import RetryError


class ClientError(Exception):
    status_code: conint(ge=400, lt=500)

    def __init__(
        self,
        status_code: conint(ge=400, lt=500),
        reason: Optional[str] = None,
        text: Optional[str] = None,
    ):
        super().__init__(
            f"Request failed with status code {status_code}"
            + (f". Reason: {reason}" if reason is not None else "")
            + (f"\nAdditional:\n{text}" if text is not None else "")
        )
        self.status_code = status_code


class ServerError(Exception):
    status_code: conint(ge=500)

    def __init__(
        self,
        status_code: conint(ge=500),
        reason: Optional[str] = None,
        text: Optional[str] = None,
    ):
        super().__init__(
            f"Request failed with status code {status_code}" + f". Reason: {reason}"
            if reason is not None
            else "" + f"\nAdditional:\n{text}" if text is not None else ""
        )
        self.status_code = status_code


def raise_appropriate_exception(response: Response) -> None:
    try:
        text = response.content
    except:
        try:
            text = response.text
        except:
            text = None

    if 400 <= response.status_code < 500:
        raise ClientError(response.status_code, response.reason, text)
    elif 500 <= response.status_code < 600:
        raise ServerError(response.status_code, response.reason, text)
