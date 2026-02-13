import typing
from itertools import takewhile
from typing import Optional, Set, List

from fhir.resources.R4B import get_fhir_model_class
from fhir.resources.R4B.fhirresourcemodel import FHIRResourceModel
from pydantic.fields import FieldInfo


def get_reference_fields(
    resource_cls, ref_types: Optional[Set[str]] = None
) -> List[FieldInfo]:
    """
    Retrieves all (first-level) Reference-typed fields of the given FHIR model class. An optional set of types can be
    provided tom return only those fields that support references to at least on of them

    :param resource_cls: FHIR model class
    :param ref_types: (Optional) set of FHIR resource type names to filter by
    :return: List of reference-supporting fields
    """
    ref_fields = []
    for field_name, model_field in resource_cls.model_fields.items():
        field_type = model_field.annotation
        # Retrieve possible origin type, e.g. enclosing Union, List types etc.
        origin = typing.get_origin(field_type)
        # Retrieve possible type args (T1, ..., TN), e.g. List[T1] -> (T1), Union[T1, T2] -> (T1, T2), etc.
        args = [getattr(a, "__name__", a) for a in typing.get_args(field_type)]

        if getattr(field_type, "__name__", None) == "ReferenceType":
            ref_fields.append(model_field)
        elif origin is not None and "ReferenceType" in args:  # Handle enclosing types
            ref_fields.append(model_field)

    if ref_types:
        # Resolve base types on which the provided types are based (e.g. abstract types such as Resource etc.). They are
        # used to indicate that a reference supports any Resource type
        expanded_ref_types = {
            m_cls.get_resource_type()
            for t in ref_types
            for m_cls in takewhile(
                lambda cls: cls != FHIRResourceModel, get_fhir_model_class(t).__mro__
            )
        }
        ref_fields = [
            *filter(
                lambda fi: not expanded_ref_types.isdisjoint(
                    fi.json_schema_extra.get("enum_reference_types")
                ),
                ref_fields,
            )
        ]
    return ref_fields
