from typing import Any

from pydantic import BaseModel, Field, field_serializer, model_serializer
from pydantic_core.core_schema import FieldSerializationInfo
from typing_extensions import deprecated

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


class TermEntryNode(BaseModel):
    __SER_AS_UI_TREE_ENTRY__ = "as_ui_tree_entry"

    term_code: TermCode
    parents: list[str] = Field(default_factory=list)
    children: list[str] = Field(default_factory=list)

    def __hash__(self) -> int:
        return hash(self.term_code)

    @classmethod
    @field_serializer("term_code", mode="plain")
    def _serialize_term_code(cls, value: TermCode, info: FieldSerializationInfo) -> str | dict[str, Any]:
        if (ctxt := info.context) and (ctxt.get(cls.__SER_AS_UI_TREE_ENTRY__)):
            return value.code
        # TODO: Verify the context info actually gets passed along this way
        return value.model_dump(**info.__dict__)

    @deprecated("Use ``TreeMap.model_dump(context={\"as_ui_tree_entry\": True})`` directly")
    def to_ui_tree_entry(self):
        return self.model_dump(context={self.__SER_AS_UI_TREE_ENTRY__: True})


class TreeMap(BaseModel):
    entries: dict[str, TermEntryNode] = Field(default_factory=dict)
    context: TermCode | None = None
    system: str
    version: str | None = None

    @classmethod
    @field_serializer("entries", mode="plain")
    def _serialize_entries(cls, value: dict[str, TermEntryNode]) -> list[dict[str, Any]]:
        return [entry.model_dump(context={"as_ui_tree_entry": True}) for entry in value.values()]

    @deprecated("Use ``TreeMap.model_dump_json(exclude_none=True)`` directly")
    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)


class TreeMapList(BaseModel):
    entries: list[TreeMap] = Field(default_factory=list)
    # For naming the files
    module_name: str | None = None

    @model_serializer(mode="plain")
    def _serialize_as_list(self) -> list[dict[str, Any]]:
        return [entry.model_dump() for entry in self.entries]

    @deprecated("Use ``TreeMapList.model_dump_json()`` directly")
    def to_json(self) -> str:
        return self.model_dump_json()
