from collections.abc import Mapping

from pydantic import BaseModel

from dataportal_generator.common.model.terminology import TermCode


# Code system URL -> Code system version -> Code -> MappingEntry name
type TermCodeMapping = Mapping[str, Mapping[str, Mapping[str, str]]]


class QueryCriterionMappingEntry(BaseModel):
    context: TermCode
    keys: TermCodeMapping


type QueryCriterionMapping = list[QueryCriterionMappingEntry]