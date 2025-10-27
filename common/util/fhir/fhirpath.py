import re
from typing import Any, Optional, List, Tuple

from fhir.resources.R4B.element import Element
from fhir.resources.R4B.elementdefinition import (
    ElementDefinition,
    ElementDefinitionSlicingDiscriminator,
)
from fhir.resources.R4B.structuredefinition import StructureDefinition

from common.exceptions import NotFoundError, UnsupportedError
from common.util.fhir.package.manager import FhirPackageManager
from common.util.log.functions import get_logger
from common.util.structure_definition.functions import get_slice_owning_element_id

_logger = get_logger(__file__)


_REGEX_MATCH_TRAILING_WHERE_FUNC = re.compile(r"where\((.*)\)$")
_REGEX_MATCH_TRAILING_EXISTS_FUNC = re.compile(r"exists\((.*)\)$")


def find_polymorphic_value(data: Element, element_name: str) -> Optional[Any]:
    """
    Attempts to find the value of a polymorphic element by iterating over all possible data type-specific names

    :param data: FHIR structure to find the value of a contained polymorphic element in
    :param element_name: (Typeless) name of the polymorphic element in the structure
    :return: Value of the contained element or `None` if no such element exists/it has no value
    """
    for field_name in data.__class__.model_fields.keys():
        if field_name.startswith(element_name):
            v = getattr(data, field_name)
            if v:
                return v
    return None


def find_value_for_discriminator_pattern_or_value(
    elem: ElementDefinition,
) -> Optional[Tuple[str, Any]]:
    """
    Attempts to find the discriminator value of a slice-defining FHIR element definition for pattern or value
    discriminated slicings, e.g. looks for a values ib the `fixed[x]`, `pattern[x]`, or `binding` sub-element

    :param elem: `ElementDefinition` instance containing the discriminator value
    :return: Tuple of the sub-element name and its value ir `None` if no fitting sub-element could be found
    """
    if fixed := find_polymorphic_value(elem, "fixed"):
        return "fixed", fixed
    if pattern := find_polymorphic_value(elem, "pattern"):
        return "pattern", pattern
    if elem.binding:
        return "binding", elem.binding
    return None


def element_data_to_fhirpath_filter(key: str = "$this", data: Any = None) -> List[str]:
    """
    Recursively traverses a FHIR element data and depending on its basic structure (e.g. it being a simple value, list,
    or key-value-mapping) translates its content into a FHIRPath expression filter in the form of a 'where' function
    invocation. Used internally by the `_element_to_fhirpath_filter` function

    :param key: Name of the element in its parent structure
    :param data: FHIR element data to transform
    :return: FHIRPath filter string
    """
    exprs = []
    match data:
        case dict():
            sub_exprs = [
                e
                for k, v in data.items()
                for e in element_data_to_fhirpath_filter(k, v)
            ]
            match len(sub_exprs):
                case 0:
                    pass
                case 1:
                    expr = sub_exprs[0]
                    if key == "$this":
                        exprs.append(expr)
                    else:
                        if _REGEX_MATCH_TRAILING_EXISTS_FUNC.search(expr):
                            exprs.append(f"{key}.{expr}")
                        else:
                            exprs.append(f"{key}.exists({expr})")
                case _:
                    if key == "$this":
                        exprs.append(" and ".join(sub_exprs))
                    else:
                        exprs.append(f"{key}.exists({' and '.join(sub_exprs)})")
        case list():
            sub_exprs = [
                e for v in data for e in element_data_to_fhirpath_filter(data=v)
            ]
            match len(sub_exprs):
                case 0:
                    pass
                case 1:
                    expr = sub_exprs[0]
                    exprs.append(f"{key}.exists({expr})" if key != "$this" else expr)
                case _:
                    clause = " and ".join([f"exists({se})" for se in sub_exprs])
                    clause = f"{key}.exists({clause})" if key != "$this" else clause
                    exprs.append(clause)
        case _:
            # TODO: Add handling for other simple FHIR data types
            exprs.append(f"{key} = '{str(data)}'")
    return exprs


def element_to_fhirpath_filter(key: str = "$this", elem: Any = None) -> str:
    """
    Recursively traverses a FHIR element and depending on its basic structure (e.g. it being a simple value, list, or
    key-value-mapping) translates its content into a FHIRPath expression filter in the form of a 'where' function
    invocation

    :param key: Name of the element in its parent structure
    :param elem: FHIR element to transform
    :return: FHIRPath filter string
    """
    if isinstance(elem, Element):
        elem_data = elem.model_dump(exclude_none=True, exclude_unset=True)
    else:
        elem_data = elem
    clause = " and ".join(element_data_to_fhirpath_filter(key, elem_data))
    return f"where({clause})"


def fhirpath_filter_from_profile_discriminated_elem(
    elem: ElementDefinition,
    discr: ElementDefinitionSlicingDiscriminator,
    snapshot: StructureDefinition,
    manager: FhirPackageManager,
) -> str:
    """
    Generates a FHIRPath filter based on the constraints of a profile discriminated slice. ATM, only elements of type
    `canonical`, `Reference`, or `Extension` are supported

    :param elem: `ElementDefinition` representing element targeted by discriminator
    :param discr: Slicing discriminator
    :param snapshot: Structure Definition snapshot containing the discriminated element
    :param manager: FHIR package manager providing access to package cache
    :return: FHIRPath expression
    """
    types = elem.type
    if len(types) > 1:
        raise ValueError(
            f"Profile discriminated element '{elem.id} in snapshot '{snapshot.url}' "
            f"supports more than one type"
        )
    t = types[0]
    match t.code:
        case "Reference" | "canonical":
            target_profile_urls = t.targetProfile
            clause = " or ".join(
                [
                    f"$this = '{url}'"
                    for target_profile_url in target_profile_urls
                    for url in [
                        target_profile_url,
                        *manager.dependents_of(target_profile_url),
                    ]
                ]
            )
            # Remove (possible) trailing resolve function call
            path = re.sub(r"\.?resolve\(\)$", "", discr.path)
            return f"where({path}.resolve().meta.profile.exists({clause}))"
        case "Extension":
            if len(t.profile) == 1:
                return f"extension('{t.profile[0]}')"
            clause = " or ".join([f"url = '{url}'" for url in t.profile])
            return f"where({clause})"
        case _:
            raise UnsupportedError(
                f"Type '{t.code}' is currently not supported in profile discriminated "
                f"elements [element_id='{elem.id}', snapshot_url='{snapshot.url}']"
            )


def get_filter_from_pattern_or_value_discriminated_elem(
    elem_def: ElementDefinition, discr_path: str, snapshot: StructureDefinition
) -> str:
    """
    Follows the discriminator path and at each node check for the discriminator value in the element at the current
    sub path. The discriminator value can be defined in any element definition whos path is a sub path of the
    discriminator path. For instance, given the discriminator defined on element with path 'a.b.c' and discriminator
    path `d.e.f`, we have to check elements 'a.b.c', `a.b.c.d`, ..., and `a.b.c.d.e.f`. If the path is not exhausted, we
    expect the value of an element to be complex and the rest of the path being represented in the structure of its
    value

    :param elem_def: `ElementDefinition` instance where a slice is defined
    :param discr_path: (Relative) path to the discriminator value
    :param snapshot: Snapshot containing the element definition
    :return: FHIRPath filter selecting elements matching the slice
    """

    def get_val(path: List[str], data: Any) -> Optional[Any]:
        try:
            v = data
            for name in path:
                v = getattr(data, name)
            return v
        except AttributeError:
            return None

    if discr_path != "$this":
        chain = discr_path.removeprefix("$this.").split(".")
        while len(chain) > 0:
            ret = find_value_for_discriminator_pattern_or_value(elem_def)
            if ret is not None:
                _, val = ret
                if get_val(chain, val) is not None:
                    break
            elem_def = snapshot.get_element_by_id(f"{elem_def.id}.{chain.pop(0)}")
    val_type, value = find_value_for_discriminator_pattern_or_value(elem_def)
    match val_type:
        case "binding":
            path = f"{discr_path}." if discr_path != "$this" else ""
            return f"where({path}memberOf('{value.valueSet}'))"
        case _:
            return element_to_fhirpath_filter(discr_path, value)


def fhirpath_filter_for_slice(
    slice_def_elem_def: ElementDefinition,
    snapshot: StructureDefinition,
    manager: FhirPackageManager,
) -> Optional[str]:
    """
    Appends a slice-based filter part to the given FHIRPath expression

    :param slice_def_elem_def: Slice-defining `ElementDefinition`
    :param snapshot: Structure definition snapshot contain the sliced element
    :param manager: FHIR package manager
    :return: Extended version of the given FHIRPath expression
    """
    parent_elem: ElementDefinition = snapshot.get_element_by_id(
        get_slice_owning_element_id(slice_def_elem_def.id)
    )
    discriminators = s.discriminator if (s := parent_elem.slicing) else []
    if len(discriminators) == 0:
        raise Exception(
            f"Cannot get filter for element '{slice_def_elem_def.id}'. Parent element '{parent_elem.id}' defines no "
            f"discriminator"
        )
    for discr in discriminators:
        discr_path = discr.path.replace("$this.", "")
        match discr.type:
            case "value" | "pattern":
                # FIXME: The value discriminator type is pretty much treated like the pattern discriminator type,
                #        though this might not be accurate
                # Both discriminator types support all of these options
                t = slice_def_elem_def.type[0]
                if t.code == "Extension":
                    # NOTE: There are potentially other ways by which an extension could be discriminated
                    if discr_path != "url":
                        raise ValueError(
                            f"Only pattern or value discriminators targeting an extensions 'url' element are supported "
                            f"to discriminate Extension typed elements "
                            f"[element_id='{slice_def_elem_def.id}', snapshot_url='{snapshot.url}']"
                        )
                    if t.profile:
                        checks = []
                        if len(t.profile) == 1:
                            return f"extension('{t.profile[0]}')"
                        for url in t.profile:
                            index_pattern = {"url": url}
                            ext_snapshot = manager.find(index_pattern)
                            url_elem_def = ext_snapshot.get_element_by_id(
                                "Extension.url"
                            )
                            checks.append(f"url = '{url_elem_def.fixedUri}'")
                        return f"where({' or '.join(checks)})"
                    else:
                        where_filter = (
                            get_filter_from_pattern_or_value_discriminated_elem(
                                slice_def_elem_def, discr_path, snapshot
                            )
                        )
                        matches = re.findall(r"\'(\S+)\'", where_filter)
                        if len(matches) == 1:
                            return f"where('{matches[0]}')"
                        return where_filter
                return get_filter_from_pattern_or_value_discriminated_elem(
                    slice_def_elem_def, discr_path, snapshot
                )
            case "exists":
                return f"where({discr_path}.exists())"
            case "type":
                if len(slice_def_elem_def.type) == 1:
                    expr = f"ofType({slice_def_elem_def.type[0].code})"
                    type_expr = (
                        expr if discr_path == "$this" else f"{discr.path}.{expr}"
                    )
                    return type_expr
                else:
                    clause = " or ".join(
                        [f"$this is {t.code}" for t in slice_def_elem_def.type]
                    )
                    type_expr = (
                        clause
                        if discr_path == "$this"
                        else f"{discr.path}.exists({clause})"
                    )
                    return f"where({type_expr})"
            case "profile":
                if discr_path == "$this":
                    target_elem = slice_def_elem_def
                else:
                    # Make path relative to discriminated element (apparently absolute resource paths are allowed as
                    # discriminator paths)
                    path = discr_path.removeprefix(f"{slice_def_elem_def.path}.")
                    # Remove (possible) leading $this selector
                    path = path.removeprefix("$this.")
                    # Remove (possible) trailing resolve function call
                    path = re.sub(r"\.?resolve\(\)$", "", path)
                    target_elem = snapshot.get_element_by_id(
                        f"{slice_def_elem_def.id}.{path}"
                    )
                if not target_elem:
                    raise NotFoundError(
                        f"Could not find element definition '{slice_def_elem_def.id}.{discr_path}' in snapshot "
                        f"'{snapshot.url}' representing profile discriminated element"
                    )
                return fhirpath_filter_from_profile_discriminated_elem(
                    target_elem, discr, snapshot, manager
                )
            case _ as t:
                raise Exception(
                    f"Unknown discriminator type '{t}' in slicing definition"
                )
