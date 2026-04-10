import functools
from typing import Annotated, Optional, Mapping, Type, FrozenSet

from pydantic import AfterValidator

from common.util.fhir import get_resource_types, supported_fhir_versions, get_data_types

_supported_release_lookup: Mapping[str, str] = {
    v: r for r, v in supported_fhir_versions()
}


def validate_fhir_data_type_name_in_version(version: str, data_type: str) -> str:
    """
    Validator base function for FHIRDataTypeStr that checks if the provided string is the name of a resource type in
    the given FHIR version

    :param version: FHIR version string (release name, e.g. 'DSTU3', 'R5', etc.)
    :param data_type: Name of resource type to validate
    :return: Validated FHIR data type string
    """
    types = get_data_types(version)
    if not types:
        raise ValueError(f"Unsupported FHIR version '{version}'")
    if not data_type in types:
        raise ValueError(
            f"Invalid FHIR data type '{data_type}' for version '{version}'. Expected one of {sorted(types)}"
        )
    return data_type


def validate_fhir_resource_type_name_in_version(
    version: str, resource_type: str
) -> str:
    """
    Validator base function for FHIRResourceTypeStr that checks if the provided string is the name of a resource type in
    the given FHIR version

    :param version: FHIR version string (release name, e.g. 'DSTU3', 'R5', etc.)
    :param resource_type: Name of resource type to validate
    :return: Validated FHIR resource type string
    """
    types = get_resource_types(version)
    if not types:
        raise ValueError(f"Unsupported FHIR version '{version}'")
    if not resource_type in types:
        raise ValueError(
            f"Invalid FHIR resource type '{resource_type}' for version '{version}'. Expected one of {sorted(types)}"
        )
    return resource_type


@functools.cache
def all_fhir_data_types_any_version() -> FrozenSet[str]:
    """
    Returns a set of all FHIR data types supported by at least one FHIR version

    :return: Set of resource type strings
    """
    return frozenset(
        [
            resource_t
            for version, _ in supported_fhir_versions()
            for resource_t in get_data_types(version)
        ]
    )


@functools.cache
def all_fhir_resource_types_any_version() -> FrozenSet[str]:
    """
    Returns a set of all FHIR resource types supported by at least one FHIR version

    :return: Set of resource type strings
    """
    return frozenset(
        [
            resource_t
            for version, _ in supported_fhir_versions()
            for resource_t in get_resource_types(version)
        ]
    )


class FHIRDataTypeStr:
    """
    Type annotation for fields of type ``str`` that only allows FHIR data type names that may or may not be
    supported by any particular FHIR version or release

    Usage: ::

        field: FHIRDataTypeStr["version_or_release"]
    """

    def __new__(cls, *args, **kwargs):
        """
        Will always fail as this class is intended for type annotating

        :param args:
        :param kwargs:
        """
        raise TypeError("Type FHIRDataTypeStr cannot be instantiated.")

    def __class_getitem__(cls, version_or_release) -> Type:
        if version_or_release in _supported_release_lookup:
            release = _supported_release_lookup[version_or_release]
        else:
            release = version_or_release
        return cls.__get_type_annotation(release)

    @staticmethod
    def __get_type_annotation(release: Optional[str] = None) -> Type:
        if release:
            validator_func = lambda data_type: validate_fhir_data_type_name_in_version(
                release, data_type
            )
        else:
            validator_func = (
                lambda data_type: data_type in all_fhir_data_types_any_version()
            )
        return Annotated[str, AfterValidator(validator_func)]


class FHIRResourceTypeStr:
    """
    Type annotation for fields of type ``str`` that only allows FHIR resource type names that may or may not be
    supported by any particular FHIR version or release

    Usage: ::

        field: FHIRResourceTypeStr["version_or_release"]
    """

    def __new__(cls, *args, **kwargs):
        """
        Will always fail as this class is intended for type annotating

        :param args:
        :param kwargs:
        """
        raise TypeError("Type FHIRResourceTypeStr cannot be instantiated.")

    def __class_getitem__(cls, version_or_release) -> Type:
        if version_or_release in _supported_release_lookup:
            release = _supported_release_lookup[version_or_release]
        else:
            release = version_or_release
        return cls.__get_type_annotation(release)

    @staticmethod
    def __get_type_annotation(release: Optional[str] = None) -> Type:
        if release:
            validator_func = (
                lambda resource_type: validate_fhir_resource_type_name_in_version(
                    release, resource_type
                )
            )
        else:
            validator_func = (
                lambda resource_type: resource_type
                                      in all_fhir_resource_types_any_version()
            )
        return Annotated[str, AfterValidator(validator_func)]
