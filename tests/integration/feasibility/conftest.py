from pydantic import BaseModel

from common.util.log.functions import get_logger

_logger = get_logger(__name__)


class Status(BaseModel):
    disabled: bool = False
    reason: str | None = None


class CCDLTestdataEntry(BaseModel):
    query: str
    expected: int = 1
    status: Status = Status()