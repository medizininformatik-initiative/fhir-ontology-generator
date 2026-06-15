from typing import Dict, List

from pydantic import BaseModel, Field


class ChildSpec(BaseModel):
    """
    Class used to describe the required structure of complex elements

    Attributes
    ----------
    id : str
        id of the child
    type : str
        type of the primitive child
        or "Polymorphic" if child is a polymorphic (see `Timing`)
        or the id of the complex child referred to. (See `Timing`)
    required_types_for_polymorphic_element : Optional[List[str]] = None
        if type == "Polymorphic" => possible types of child
    max_cardinality_multiple : bool = False
        True when cardinality max == "*"
        Note: In the current implementation max_cardinality_multiple has no effect on elements
        other than primitives, because all complex elements are rendered with ForEachOrNull anyway
    """

    id: str
    type: str
    required_types_for_polymorphic_element: List[str] = Field(default=[])
    max_cardinality_multiple: bool = False

class FlatteningConfig(BaseModel):
    required_children_per_element: Dict[str, list[ChildSpec]] = Field(default={})
    excluded_types: List[str] = Field(default=[])
