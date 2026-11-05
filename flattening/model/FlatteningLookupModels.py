from typing import Annotated, Dict, List, Optional, Any

from pydantic import Field, TypeAdapter, field_validator, model_validator

from versiondiff import Category, DiffModel, DiffRule, Identity, Unordered, Change, Kind


class ViewDefinitionColumn(DiffModel):
    name: Annotated[str, Identity()] = Field(alias="name", default=None)
    path: Annotated[str, DiffRule(on_change=Category.BREAKING)] = Field(alias="path", default=None)
    type: Annotated[Optional[str], DiffRule(on_change=Category.BREAKING)] = Field(alias="type", default=None)

    model_config = {"populate_by_name": True}


class ViewDefinitionSelect(DiffModel):
    column: List[ViewDefinitionColumn] = Field(alias="column", default=list)

    model_config = {"populate_by_name": True}


class ViewDefinitionSnippet(DiffModel):
    for_each_or_null: Annotated[
        Optional[str], DiffRule(on_change=Category.BREAKING, on_add=Category.BREAKING)
    ] = Field(alias="forEachOrNull", default=None)
    select: List[ViewDefinitionSelect] = Field(alias="select", default=None)
    column: List[ViewDefinitionColumn] = Field(alias="column", default=None)

    model_config = {"populate_by_name": True}

    @model_validator(mode="after")
    def validate(self):
        if self.select is not None == self.column is not None:
            raise ValueError(
                "Exactly one of 'select' or 'column' must be defined, but not both"
            )
        return self


class FlatteningLookupElement(DiffModel):
    parent: Annotated[Optional[str], DiffRule(on_change=Category.INFORMATIONAL)] = Field(
        default=None, deprecated="Should be determined via `children` field"
    )
    view_definition: Optional[ViewDefinitionSnippet] = Field(
        alias="viewDefinition", default=None
    )
    children: Annotated[Optional[List[str]], Unordered()] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class FlatteningLookup(DiffModel):
    url: Annotated[str, Identity()]
    resource_type: str = Field(alias="resourceType")
    elements: Dict[str, FlatteningLookupElement] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}

    @field_validator('elements')
    @classmethod
    def validate(cls, lookup:Dict[str, FlatteningLookupElement]):
        """Checking for duplicate column names"""
        visited_columns = set()
        for _, element in lookup.items():
            for col in (element.view_definition.column if element.view_definition.column else []):
                if col.name in visited_columns:
                    raise ValueError(f"Duplicate column name: {col.name}")
                visited_columns.add(col.name)

            for sel in (element.view_definition.select if element.view_definition.select else []):
                for col in sel.column:
                    if col.name in visited_columns:
                        raise ValueError(f"Duplicate column name: {col.name}")
                    visited_columns.add(col.name)
        return lookup

    @classmethod
    def _all_colum_names(cls, instance: dict[str, Any]) -> set[str]:
        columns = set()
        for element in instance.get("elements", {}).values():
            if view_def := element.get("viewDefinition"):
                for select in view_def.get("select") or []:
                    columns.update(col["name"] for col in select.get("column") or [])
                columns.update(col["name"] for col in view_def.get("column") or [])
        return columns

    @classmethod
    def diff(cls, prev: dict[str, Any], curr: dict[str, Any], path: str) -> list[Change]:
        changes = super().diff(prev, curr, path)
        # Check columns
        prev_columns = cls._all_colum_names(prev)
        curr_columns = cls._all_colum_names(curr)
        for removed in prev_columns - curr_columns:
            changes.append(Change(
                path=f"{path}/elements/**/column={removed}",
                kind=Kind.REMOVED,
                category=Category.BREAKING,
                note="Column removed",
            ))
        for added in curr_columns - prev_columns:
            changes.append(Change(
                path=f"{path}/elements/**/column={added}",
                kind=Kind.ADDED,
                category=Category.INFORMATIONAL,
                note="Column added",
            ))
        return changes


FlatteningLookupListTA = TypeAdapter(list[FlatteningLookup])