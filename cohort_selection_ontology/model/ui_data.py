from typing import Annotated

from pydantic import BaseModel, Field
from typing_extensions import deprecated

from versiondiff import DiffModel, DiffRule, Identity


def del_none(dictionary):
    import cohort_selection_ontology.model.ui_profile

    """
    Delete keys with the value ``None`` in a dictionary, recursively.

    This alters the input so you may wish to ``copy`` the dict first.
    """
    for key, value in list(dictionary.items()):
        if value is None:
            del dictionary[key]
        elif isinstance(value, cohort_selection_ontology.model.ui_profile.UIProfile):
            ui_profile = value.__dict__.copy()
            del ui_profile["name"]
            dictionary.update(del_none(ui_profile))
            del dictionary[key]
        elif isinstance(value, dict):
            del_none(value)
        elif isinstance(value, list):
            if not value:
                del dictionary[key]
            for element in value:
                if not isinstance(element, str):
                    del_none(element.__dict__)
    return dictionary


class Module(DiffModel):
    code: Annotated[str, Identity()]
    display: Annotated[str, DiffRule(ignore=True)]

    def to_dict(self):
        return {"code": self.code, "display": self.display}


class RelationalTermcode(BaseModel):
    contextualized_termcode_hash: str
    display: str | dict
    terminology: str
    term_code: str
    selectable: bool

    @deprecated("Use ``RelationalTermcode.model_dump()`` instead")
    def to_dict(self):
        return self.model_dump()


class Translation(BaseModel):
    language: str
    value: str | None = Field(default=None)


class BulkTranslation(BaseModel):
    language: str
    value: list[str | None] = Field(default_factory=list)


class TranslationDisplayElement(BaseModel):
    original: str
    translations: list[Translation] = Field(default_factory=list)


class BulkTranslationDisplayElement(BaseModel):
    original: list[str] = Field(default_factory=list)
    translations: list[BulkTranslation] = Field(default_factory=list)


class TermCode(BaseModel):
    """
    A TermCode represents a concept from a terminology system.::

        :system: the terminology system
        :code: the code for the concept
        :display: the display for the concept
        :version: the version of the terminology system
    """

    system: str
    code: str
    display: str | TranslationDisplayElement
    version: str | None = None

    def __eq__(self, other):
        if isinstance(other, TermCode):
            return self.system == other.system and self.code == other.code
        return False

    def __hash__(self):
        return hash(self.system + self.code)

    def __lt__(self, other):
        if isinstance(other, TermCode):
            this_display = (
                self.display.original
                if isinstance(self.display, TranslationDisplayElement)
                else self.display
            )
            other_display = (
                other.display.original
                if isinstance(other.display, TranslationDisplayElement)
                else other.display
            )

            return this_display.casefold() < other_display.casefold()
        return NotImplemented

    def __repr__(self):
        return (
            self.system + " " + self.code + " " + self.version if self.version else ""
        )

    @deprecated("Use ``TermCode.model_dump()`` instead")
    def to_dict(self) -> dict:
        return self.model_dump()


class Unit(BaseModel):
    # TODO: is this still in use? else mark as deprecated
    """
    Defines a unit from the UCUM code system
    :param display: the display name of the unit
    :param code: the UCUM code of the unit
    """
    display: str
    code: str
