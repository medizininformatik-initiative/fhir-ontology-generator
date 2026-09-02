from pydantic import BaseModel, Field, TypeAdapter, computed_field


class ProfileTreeNode(BaseModel):
    url: str
    selectable: bool = False
    children: list["ProfileTreeNode"] = Field(default_factory=list)

    @computed_field
    @property
    def is_leaf(self) -> bool:
        return len(self.children) == 0


ProfileTreeTA = TypeAdapter(list[ProfileTreeNode])
