from pathlib import Path
from typing import Annotated, Any

from dataportal_generator.common.config.project import register_config_module
from pydantic import BaseModel, BeforeValidator

from dataportal_generator.feature_selection.config.fields import FieldsConfig


def _fields_config_from_file(v: Any) -> Any:
    if isinstance(v, Path) and v.is_file():
        with v.open(mode="r", encoding="utf-8") as fd:
            return FieldsConfig.model_validate_json(fd.read())
    # Leave it to pydantic type coercion
    return v


class FeatureSelectionConfig(BaseModel):
    fields: Annotated[FieldsConfig, BeforeValidator(_fields_config_from_file)]