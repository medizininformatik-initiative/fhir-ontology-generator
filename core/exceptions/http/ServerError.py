from typing import Optional

from pydantic import conint

class ServerError(Exception):
    status_code: conint(ge=400, lt=500)

    def __init__(self, status_code: conint(ge=500, lt=600), reason: Optional[str]):
        super().__init__(f"Request failed with status code {status_code}" +
                         f". Reason: {reason}" if reason is not None else "" )
        self.status_code = status_code