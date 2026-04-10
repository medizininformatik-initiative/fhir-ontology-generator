import functools
import importlib
import inspect
import pkgutil

import fhir.resources
from typing_extensions import Tuple, FrozenSet

from common.util.collections.functions import head


@functools.cache
def get_resource_types(version: str = None) -> FrozenSet[str]:
    """
    Get all resource types supported by the given FHIR version

    :param version: FHIR release name (e.g. `R4B` instead of `4.3.0`)
    :return: Set of names of supported FHIR resource types
    """
    mod_path = f"fhir.resources.{version}" if version else "fhir.resources"
    try:
        pkg = importlib.import_module(mod_path)
        # Use version module specific Resource abstract class to filter out backbone classes, etc.
        _, res_class = head(
            inspect.getmembers(
                importlib.import_module(f"{mod_path}.resource"), inspect.isclass
            )
        )
    except ImportError as err:
        raise ValueError(f"Unknown FHIR version '{version}'") from err

    resource_types = []
    for _, module_name, _ in pkgutil.iter_modules(pkg.__path__):
        try:
            mod = importlib.import_module(f"{mod_path}.{module_name}")
            for name, obj in inspect.getmembers(mod, inspect.isclass):
                if (
                    issubclass(obj, res_class)
                    and obj.__module__ == mod.__name__  # Defined here, not imported
                    and name[0].isupper()  # Skip base/private classes
                ):
                    resource_types.append(name)
        except ImportError:
            continue

    return frozenset(resource_types)


@functools.cache
def get_primitive_data_types() -> FrozenSet[str]:
    """
    Gets all primitive data type

    :return: Set of names of supported primitive data types
    """
    fhirtypes = importlib.import_module(f"fhir_core.types")
    return frozenset([
        t[0].lower() + t[1:-4]
        for t in getattr(fhirtypes, "__all__")
        if t[0].isupper() and t.endswith("Type")
    ])


@functools.cache
def get_complex_data_types(version: str = None) -> FrozenSet[str]:
    """
    Get all complex resource types supported by the given FHIR version

    :param version: FHIR release name (e.g. `R4B` instead of `4.3.0`)
    :return: Set of name of complex data types supported by the release version
    """

    mod_path = f"fhir.resources.{version}" if version else "fhir.resources"
    try:
        pkg = importlib.import_module(mod_path)
        # Use version module specific Element abstract class as a base
        _, elem_class = head(
            inspect.getmembers(
                importlib.import_module(f"{mod_path}.element"), inspect.isclass
            )
        )
    except ImportError as err:
        raise Exception(
            f"Failed to import submodule 'element' of module '{mod_path}'"
        ) from err
    try:
        # Use version module specific BackboneElement abstract class to filter out it and its subclasses
        _, bb_class = head(
            inspect.getmembers(
                importlib.import_module(f"{mod_path}.backboneelement"), inspect.isclass
            )
        )
    except ImportError as err:
        raise Exception(
            f"Failed to import submodule 'backboneelement' of module '{mod_path}'"
        ) from err

    # Complex data types
    complex_data_types = []
    for _, module_name, _ in pkgutil.iter_modules(pkg.__path__):
        try:
            mod = importlib.import_module(f"{mod_path}.{module_name}")
            for name, obj in inspect.getmembers(mod, inspect.isclass):
                if (
                    issubclass(obj, elem_class)
                    and not issubclass(obj, bb_class)
                    and obj.__module__ == mod.__name__  # Defined here, not imported
                    and name[0].isupper()  # Skip base/private classes
                ):
                    complex_data_types.append(name)
        except ImportError as err:
            raise Exception(
                f"Failed to import submodule '{module_name}' of module '{mod_path}'"
            ) from err

    return frozenset(complex_data_types)


def get_data_types(version: str = None) -> FrozenSet[str]:
    """
    Gets all data types supported by the given FHIR version

    :param version: FHIR release name (e.g. `R4B` instead of `4.3.0`)
    :return: Set of names of all supported data types
    """
    return get_primitive_data_types().union(get_complex_data_types(version))


@functools.cache
def supported_fhir_versions() -> FrozenSet[Tuple[str, str]]:
    """
    Returns a set of versions supported by the fhir.resources package

    :return: Set of tuples of supported versions of structure (`release-name`, `semantic-version`)
    """
    # FIXME: This breaks if the default version of fhir.resources is updated
    versions = [("R5", fhir.resources.__fhir_version__)]
    for _, name, is_pkg in pkgutil.iter_modules(fhir.resources.__path__):
        if not is_pkg:
            continue
        try:
            mod = importlib.import_module(f"fhir.resources.{name}")
            if hasattr(mod, "__fhir_version__"):
                versions.append((name, mod.__fhir_version__))
        except ImportError:
            continue
    return frozenset(versions)
