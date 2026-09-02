from pydantic import BaseModel

from dataportal_generator.common.model.localization import TranslationDisplayElement


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

    def to_dict(self):
        if isinstance(self.display, str):
            return {
                "system": self.system,
                "code": self.code,
                "display": self.display,
                "version": self.version,
            }
        if isinstance(self.display, TranslationDisplayElement):
            return {
                "system": self.system,
                "code": self.code,
                "display": self.display.model_dump_json(),
                "version": self.version,
            }
        return None