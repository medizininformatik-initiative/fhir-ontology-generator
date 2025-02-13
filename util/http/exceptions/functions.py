from requests import Response

from util.http.exceptions.ClientError import ClientError
from util.http.exceptions.ServerError import ServerError


def raise_appropriate_exception(response: Response) -> None:
    try: text = response.text
    except: text = None

    if 400 <= response.status_code < 500:
        raise ClientError(response.status_code, response.reason, text)
    elif 500 <= response.status_code < 600:
        raise ServerError(response.status_code, response.reason, text)