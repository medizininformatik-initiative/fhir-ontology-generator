from collections.abc import Mapping
from typing import Any, List

from common.model.structure_definition import StructureDefinitionSnapshot
from common.util.log.functions import get_logger


logger = get_logger(__file__)


def is_profile_selectable(snapshot: StructureDefinitionSnapshot, profiles: Mapping[str, Mapping[str, Any]]) -> bool:
    """
    Determines the profile represented by the provided profile snapshot is selectable
    :param snapshot: Profile snapshot for which to determine whether it can be selected
    :param profiles: Mapping if profile URLs to profile entries
    :return: Boolean indicating whether the profile is selectable
    """
    # FIXME: The logic should only rely on the value of the `abstract` element of a given StructureDefinition
    #        instance to determine whether it itself is selectable or not. Currently whether other profiles in the
    #        same module are derived from it is used to determine "abstractness"
    if snapshot is None:
        return False
    children = filter(
        lambda t: t[1].baseDefinition == profile_url,
        map(
            lambda p: (p.get("module"), p.get("structureDefinition", {})),
            profiles.values(),
        ),
    )

    profile_url = snapshot.url
    if profile_url in profiles:
        module = profiles.get(profile_url).get('module')
        if not snapshot.abstract:
            return all(m != module for m, _ in children)
    else:
        # TODO: Decide on right log level since this matches every time the FHIR base resource profiles are
        #       encountered
        # If the URL does not match any profile in any scope it might be missing
        logger.debug(f"Provided profile URL '{profile_url}' is not present and cannot be analyzed further. Consider "
                     f"including it via dependencies if this is not intended.")
    return False