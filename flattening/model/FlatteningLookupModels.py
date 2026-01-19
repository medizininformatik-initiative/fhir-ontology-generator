from typing import Optional, List, Dict

from pydantic import BaseModel, Field, model_validator, field_validator


class ViewDefinitionColumn(BaseModel):
    name: str = Field(alias="name", default=None)
    path: str = Field(alias="path", default=None)
    type: Optional[str] = Field(alias="type", default=None)

    model_config = {"populate_by_name": True}


class ViewDefinitionSelect(BaseModel):
    column: List[ViewDefinitionColumn] = Field(alias="column", default=list)

    model_config = {"populate_by_name": True}


class ViewDefinitionSnippet(BaseModel):
    for_each_or_null: str = Field(alias="forEachOrNull", default=None)
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


class FlatteningLookupElement(BaseModel):
    parent: Optional[str] = None
    view_definition: Optional[ViewDefinitionSnippet] = Field(
        alias="viewDefinition", default=None
    )
    children: Optional[List[str]] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class FlatteningLookup(BaseModel):
    url: str
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
