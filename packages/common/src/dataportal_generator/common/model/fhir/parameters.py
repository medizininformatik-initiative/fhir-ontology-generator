import abc
from collections.abc import Iterable
from typing import Any

from fhir.resources.R4B.parameters import Parameters, ParametersParameter
from pydantic import Field

ParameterKey = str | tuple[str, ...]


def _normalize_key(key: ParameterKey) -> tuple[str, ...]:
    if isinstance(key, str):
        return (key,)
    if isinstance(key, tuple) and key and all(isinstance(k, str) for k in key):
        return key
    raise TypeError(
        f"Parameter key must be a non-empty string or tuple of strings but was {key!r}"
    )


def find_parameters(
    parameters: Iterable[ParametersParameter] | None, key: ParameterKey
) -> list[ParametersParameter]:
    """
    Finds all parameters matching the provided key. A key is either a parameter name or a tuple of names describing a
    path through nested `part` elements, e.g. `("match", "concept")` matches all `concept` parts of all `match`
    parameters

    :param parameters: Parameters (or parts) to search in
    :param key: Name or path of names to search with
    :return: List of matching parameters in document order
    """
    matches = list(parameters or [])
    for i, name in enumerate(_normalize_key(key)):
        candidates = matches if i == 0 else [p for m in matches for p in (m.part or [])]
        matches = [p for p in candidates if p.name == name]
    return matches


def get_parameter_value(parameter: ParametersParameter) -> Any | None:
    """
    Retrieves the value of the `value[x]` element of a parameter

    :param parameter: Parameter to retrieve value from
    :return: Value of the parameter or `None` if it has no value
    """
    for field in parameter.get_one_of_many_fields()["value"]:
        if (value := getattr(parameter, field, None)) is not None:
            return value
    return None


class _KeyedAccessMixin(abc.ABC):
    """
    Provides key and property based access to the (nested) parameters of a model. A key is either a parameter name or a
    tuple of names describing a path through nested `part` elements. Since parameter names are not required to be
    unique, lookups return all matches unless stated otherwise.

    Property based access resolves attribute names not matching a model field or attribute to parameter names. If no
    parameter matches the attribute name exactly, underscores are replaced with hyphens, e.g. `used_codesystem` matches
    parameters named `used-codesystem`. Parameters whose names collide with model fields or attributes (e.g. `name` or
    `resource`) or that are not valid identifiers have to be accessed via keys instead
    """

    @abc.abstractmethod
    def _keyed_children(self) -> list[ParametersParameter] | None:
        pass

    def __getattr__(self, item: str) -> Any:
        try:
            return super().__getattr__(item)
        except AttributeError:
            if item.startswith("_"):
                raise
            children = self._keyed_children()
            for name in dict.fromkeys([item, item.replace("_", "-")]):
                if matches := find_parameters(children, name):
                    return matches
            raise

    def __getitem__(self, key: ParameterKey) -> list[ParametersParameter]:
        """
        :param key: Name or path of names to search with
        :return: List of matching parameters
        :raises KeyError: If no parameter matches the key
        """
        if not (matches := find_parameters(self._keyed_children(), key)):
            raise KeyError(key)
        return matches

    def __contains__(self, key: object) -> bool:
        try:
            return len(find_parameters(self._keyed_children(), key)) > 0
        except TypeError:
            return False

    def keys(self) -> list[str]:
        """
        :return: Unique names of all direct child parameters in document order
        """
        return list(dict.fromkeys(p.name for p in (self._keyed_children() or [])))

    def get_all(self, key: ParameterKey) -> list[ParametersParameter]:
        """
        Finds all parameters matching the key

        :param key: Name or path of names to search with
        :return: List of matching parameters (empty if there is no match)
        """
        return find_parameters(self._keyed_children(), key)

    def get(
        self, key: ParameterKey, default: ParametersParameter | None = None
    ) -> ParametersParameter | None:
        """
        Finds the first parameter matching the key

        :param key: Name or path of names to search with
        :param default: Value to return if there is no match
        :return: First matching parameter or `default`
        """
        matches = find_parameters(self._keyed_children(), key)
        return matches[0] if matches else default

    def get_value(self, key: ParameterKey, default: Any = None) -> Any:
        """
        Retrieves the `value[x]` element value of the first parameter matching the key

        :param key: Name or path of names to search with
        :param default: Value to return if there is no match or the matching parameter has no value
        :return: Value of the first matching parameter or `default`
        """
        if (param := self.get(key)) is not None and (
            value := get_parameter_value(param)
        ) is not None:
            return value
        return default

    def get_values(self, key: ParameterKey) -> list[Any]:
        """
        Retrieves the `value[x]` element values of all parameters matching the key. Parameters without values are skipped

        :param key: Name or path of names to search with
        :return: List of values
        """
        return [
            v
            for p in find_parameters(self._keyed_children(), key)
            if (v := get_parameter_value(p)) is not None
        ]


class KeyedParametersParameter(_KeyedAccessMixin, ParametersParameter):
    """
    Adapted `ParametersParameter` model providing key and property based access to its parts
    """

    part: list["KeyedParametersParameter"] | None = Field(
        default=None,
        alias="part",
        title="Named part of a multi-part parameter",
        description="A named part of a multi-part parameter.",
        json_schema_extra={
            "element_property": True,
            "summary_element_property": True,
        },
    )

    def _keyed_children(self) -> list[ParametersParameter] | None:
        return self.part

    @property
    def value(self) -> Any | None:
        """
        :return: Value of the `value[x]` element or `None` if the parameter has no value
        """
        return get_parameter_value(self)


class KeyedParameters(_KeyedAccessMixin, Parameters):
    """
    Adapted `Parameters` model providing key and property based access to its parameters, e.g.
    `params.match[0].concept[0].value` or `params["match", "concept"]`
    """

    parameter: list[KeyedParametersParameter] | None = Field(
        default=None,
        alias="parameter",
        title="Operation Parameter",
        description="A parameter passed to or received from the operation.",
        json_schema_extra={
            "element_property": True,
            "summary_element_property": True,
        },
    )

    def _keyed_children(self) -> list[ParametersParameter] | None:
        return self.parameter
