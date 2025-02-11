from typing import Optional

from pydantic import conint

class ServerError(Exception):
    status_code: conint(ge=500)

    def __init__(self, status_code: conint(ge=500), reason: Optional[str] = None, text: Optional[str] = None):
        super().__init__(f"Request failed with status code {status_code}" +
                         f". Reason: {reason}" if reason is not None else "" +
                         f"\nAdditional:\n{text}" if text is not None else "")
        self.status_code = status_code