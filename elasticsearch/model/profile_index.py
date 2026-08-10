import json
from typing import Dict

from pydantic import BaseModel, Field, ConfigDict
from importlib.resources import files

import cohort_selection_ontology.model.ui_data
from data_selection_extraction.model.profile_tree import ProfileTreeNode

_RESOURCE_TYPE_LOCALIZATIONS = json.loads(
    files("elasticsearch.model.resources")
    .joinpath("resource_type_localizations.json")
    .read_text(encoding="utf-8")
)


# TODO: Apply this new translation data model throughout the entire repository
class TranslationDisplayElement(BaseModel):
    original: str
    localization: Dict[str, str] = Field(default_factory=dict)

    def update_translations(self, **kwargs: tuple[str, str | None]):
        """
        Updates the associated value for each provided lang code. If a tuples value is ``None`` then no update is done
        """
        for lang, value in kwargs:
            if value:
                self.localization[lang] = value

    @classmethod
    def from_ui_model(
        cls, obj: cohort_selection_ontology.model.ui_data.TranslationDisplayElement
    ) -> "TranslationDisplayElement":
        return TranslationDisplayElement(
            original=obj.original,
            localization={t.language: t.value for t in obj.translations if t.value},
        )

    @classmethod
    def from_ui_bulk_model(
        cls, obj: cohort_selection_ontology.model.ui_data.BulkTranslationDisplayElement
    ) -> list["TranslationDisplayElement"]:
        result = []
        for v in obj.original:
            result.append(TranslationDisplayElement(original=v))
        for bulk_trans in obj.translations:
            lang = bulk_trans.language
            for idx, v in enumerate(bulk_trans.value):
                if v:
                    elem = result[idx]
                    elem.localization[lang] = v
        return result


class ProfileIndexDocumentField(BaseModel):
    display: TranslationDisplayElement
    description: TranslationDisplayElement | None


class ProfileIndexDocumentRef(BaseModel):
    display: TranslationDisplayElement
    url: str
    selectable: bool


class ProfileIndexDocument(BaseModel):
    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    name: str
    display: TranslationDisplayElement
    url: str
    module: TranslationDisplayElement
    selectable: bool = Field(default=True)
    resource_type: TranslationDisplayElement = Field(alias="resourceType")
    categories: list[TranslationDisplayElement] = Field(default_factory=list)
    description: list[TranslationDisplayElement] = Field(default_factory=list)
    availability: int = Field(default=0)
    fields: list[ProfileIndexDocumentField] = Field(default_factory=list)
    parents: list[ProfileIndexDocumentRef] = Field(default_factory=list)
    children: list[ProfileIndexDocumentRef] = Field(default_factory=list)

    def to_ref(self) -> ProfileIndexDocumentRef:
        return ProfileIndexDocumentRef(
            display=self.display.model_copy(deep=True),
            url=self.url,
            selectable=self.selectable,
        )

    @classmethod
    def from_profile_tree_node(cls, node: ProfileTreeNode) -> "ProfileIndexDocument":
        resource_type = TranslationDisplayElement(original=node.resource_type)
        if resource_type_localization := _RESOURCE_TYPE_LOCALIZATIONS.get(
            node.resource_type
        ):
            resource_type.localization = resource_type_localization.copy()
        return ProfileIndexDocument(
            name=node.name,
            display=TranslationDisplayElement.from_ui_model(node.display),
            url=node.url,
            module=TranslationDisplayElement.from_ui_model(node.module),
            selectable=node.selectable,
            resource_type=resource_type,
            description=(
                [TranslationDisplayElement.from_ui_model(node.description)]
                if node.description
                else []
            ),
            availability=0,
            fields=[
                ProfileIndexDocumentField(
                    display=TranslationDisplayElement.from_ui_model(field[0]),
                    description=(
                        TranslationDisplayElement.from_ui_model(field[1])
                        if field[1]
                        else None
                    ),
                )
                for field in node.fields
            ],
            children=[
                ProfileIndexDocumentRef(
                    display=TranslationDisplayElement.from_ui_model(child.display),
                    url=child.url,
                    selectable=child.selectable,
                )
                for child in node.children
            ],
        )
