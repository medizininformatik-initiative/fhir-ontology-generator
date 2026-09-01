import re
from operator import contains

from dataportal_generator.common.log.functions import get_logger
from dataportal_generator.feature_selection.model.profile_tree import ProfileTreeNode

logger = get_logger(__file__)


def extract_module_string(struct_def_url: str) -> str | None:
    """
    Extracts a module string from the given StructureDefinition URL

    :param struct_def_url: URL of the StructureDefinition
    :return: Extracted module string or `None` if no module string could be extracted
    """
    if struct_def_url.startswith("https://www.medizininformatik-initiative.de"):
        match = re.search(r"/(?P<module>modul-[^/]+)/", struct_def_url)
        if match:
            return match.group("module")
    elif struct_def_url.startswith("https://gematik.de/fhir/isik"):
        return "modul-isik-vitalparameter"
    return None


def is_profile_selectable(
    profile_sub_tree: ProfileTreeNode
) -> bool:
    """
    Determines the profile represented by the provided profile snapshot is selectable if
    :param profile_sub_tree: Profile tree subtree with the root being the node of the profile to determine
                             selectability for
    :return: Boolean indicating whether the profile is selectable
    """
    # FIXME: The logic should only rely on the value of the `abstract` element of a given StructureDefinition
    #        instance to determine whether it itself is selectable or not. Currently whether other profiles in the
    #        same module are derived from it is used to determine "abstractness"
    child_modules = {extract_module_string(c.url) for c in profile_sub_tree.children}
    profile_module = extract_module_string(profile_sub_tree.url)
    return not contains(child_modules, profile_module)