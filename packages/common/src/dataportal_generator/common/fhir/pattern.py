from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fhir.resources.R4B.element import Element
from pydantic import BaseModel

FhirInstance = Element | BaseModel | Any
FhirPattern = dict | list | Any


def _to_comparable(value: Any) -> Any:
    """
    Converts a value into a plain, JSON-native representation (`dict`/`list`/`str`/`int`/`float`/`bool`/`None`) that
    can be structurally compared against a parsed `pattern[x]` JSON value

    :param value: Value to convert
    :return: JSON-native representation of the value
    """
    if isinstance(value, BaseModel):
        # Covers `fhir.resources` `Element`/`Resource` instances (i.e. all complex FHIR data types), recursively
        # converting any nested model instances as well
        return value.model_dump(mode="json", by_alias=True, exclude_none=True)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, list):
        return [_to_comparable(item) for item in value]
    return value


def _matches(instance: Any, pattern: Any) -> bool:
    """
    Recursively matches an already JSON-native instance value against a JSON-native pattern value, following the
    matching rules described in the FHIR specification for `ElementDefinition.pattern[x]`:

    - Primitives match if and only if they are equal to the pattern value
    - Every property present in a pattern object must also be present in the instance object and (recursively) match
      the corresponding pattern value; the instance object may contain additional properties not present in the
      pattern
    - Every element of a pattern array must (recursively) match at least one element of the instance array; the
      instance array may contain additional elements not "claimed" by the pattern, and a single instance element may
      satisfy more than one pattern element

    :param instance: JSON-native instance value (as produced by `_to_comparable`)
    :param pattern: JSON-native pattern value (i.e. `pattern[x]` itself, or a sub value thereof), a `dict`, `list`, or
                     primitive value (e.g. `str`, `int`, `float`, `bool`, `None`)
    :return: `True` if the pattern matches the instance value, `False` otherwise
    """
    match pattern:
        case dict():
            return isinstance(instance, dict) and all(
                key in instance and _matches(instance[key], sub_pattern)
                for key, sub_pattern in pattern.items()
            )
        case list():
            return isinstance(instance, list) and all(
                any(_matches(item, sub_pattern) for item in instance)
                for sub_pattern in pattern
            )
        case _:
            return instance == pattern


def matches_pattern(data: FhirInstance | list[FhirInstance], pattern: FhirPattern) -> bool:
    """
    Determines whether the given FHIR data type instance(s) matches the given pattern, applying the same matching
    rules `ElementDefinition.pattern[x]` follows in the FHIR specification (see
    https://hl7.org/fhir/elementdefinition.html#pattern):

    - When matching a primitive, the pattern value must equal the instance value exactly
    - When matching a complex object, every property present in the pattern must also be present in the instance and
      its value must (recursively) match; the instance may contain additional properties not present in the pattern
    - When matching an array, every element of the pattern array must (recursively) match at least one element of the
      instance array; the instance array may contain additional elements not "claimed" by the pattern
    - If the constrained element is repeating, i.e. `data` is a list of instances and `pattern` is itself not a list
      (`pattern[x]` is never array-valued), the pattern applies to every repetition, i.e. every instance in the list
      must match the pattern individually. As a consequence, an empty list vacuously matches any pattern
    - If `pattern` is a list, `data` (be it a single instance or a list) is matched directly against it using the
      array matching rule above instead of the repeating-element rule. This is what allows an array-typed sub value
      (e.g. `CodeableConcept.coding`) to be matched on its own, without having to wrap it back into its parent object

    :param data: FHIR data type instance to match the pattern against (e.g. a `fhir.resources` `Element`/`Resource`
                 instance, or a plain Python primitive), or a list of such instances if the constrained element has a
                 repeating (i.e. max cardinality > 1) cardinality
    :param pattern: Pattern to match against, i.e. the (sub) value resulting from parsing the JSON representation of
                     `ElementDefinition.pattern[x]`. Can be a `dict` (complex type), a `list` (array-valued element),
                     or a primitive value (e.g. `str`, `int`, `float`, `bool`, `None`)
    :return: `True` if the pattern matches, `False` otherwise
    """
    if not isinstance(pattern, list) and isinstance(data, list):
        return all(_matches(_to_comparable(item), pattern) for item in data)
    return _matches(_to_comparable(data), pattern)
