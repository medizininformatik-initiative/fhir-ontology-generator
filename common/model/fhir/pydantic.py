from typing import TypeVar, Type, Callable, Any, Mapping, Dict

import cachetools
from fhir_core.types import FhirBase
from pydantic import BaseModel, TypeAdapter
from pydantic.fields import FieldInfo

from common.model.pydantic import validate_subset
from common.typing.functions import resolve_type

T = TypeVar("T", bound=BaseModel)


def construct_model(model_cls: Type[T] | Callable[[Any], Type[T]], **data) -> T:
    """
    Recursively construct instance of provided `pydantic` model class without validating the input data even for nested
    models

    :param model_cls: Model class to construct instance of or function determining the model class from the input data
    :param data: Data to construct instance with
    :return: Unvalidated model class instance
    """
    # NOTE: This might break with major version updates to `pydantic`/`fhir.resources`
    if not isinstance(model_cls, type):
        model_cls = model_cls(data)
    fields = model_cls.model_fields
    for name, field in fields.items():
        try:
            if name.endswith("__ext"):
                # Match model field names resulting from `fhir.resources` implementation of extensions fields for
                # primitive FHIR data types to corresponding field names in the serialized model
                name = "_" + name[:-5]
            if value := data.get(name):
                annotation_t, repeatable = resolve_type(field.annotation)
                if isinstance(value, dict) or isinstance(value, list):
                    if issubclass(annotation_t, FhirBase):
                        annotation_t = annotation_t.get_model_klass()
                    if issubclass(annotation_t, BaseModel):
                        if repeatable:
                            data[name] = [
                                construct_model(annotation_t, **v) for v in value
                            ]
                        else:
                            data[name] = construct_model(annotation_t, **value)
        except Exception as exc:
            raise Exception(
                f"Failed to construct field '{name}' of model class {model_cls}"
            ) from exc
    return model_cls.model_construct(**data)


def validate_partial_model(model_cls: Type[T], data: Mapping[str, Any]) -> T:
    """
    Validates and constructs a partial model instance from the input data representing a subset of fields required
    by the model class

    :param model_cls: Model class to validate against and construct instance of
    :param data: Data to validate and construct with
    :return: Partially validated and constructed model class instance
    """
    validate_subset(model_cls, data)
    return construct_model(model_cls, **data)
