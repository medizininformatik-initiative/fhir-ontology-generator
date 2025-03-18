import abc
from typing import Optional, List

from pydantic.dataclasses import dataclass

from model.UiDataModel import TranslationElementDisplay


@dataclass
class Filter:
    type: str
    name: str
    ui_type: str
    valueSetUrls: List[str]


class Details(abc.ABC):
    display: TranslationElementDisplay
    description: Optional[TranslationElementDisplay]
    filters: List[Filter]



@dataclass
class ProfileDetails:
