from pydantic import BaseModel
from typing_extensions import deprecated


class Module(BaseModel):
    code: str
    display: str

    def to_dict(self):
        return {"code": self.code, "display": self.display}


class RelationalTermcode(BaseModel):
    contextualized_termcode_hash: str
    display: str | dict
    terminology: str
    term_code: str
    selectable: bool

    @deprecated("Use ``model_dump()``")
    def to_dict(self, **kwargs):
        return self.model_dump(**kwargs)