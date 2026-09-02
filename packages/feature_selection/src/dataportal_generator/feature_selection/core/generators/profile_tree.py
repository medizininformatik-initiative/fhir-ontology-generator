from collections.abc import Iterator

from common.model.fhir.nav_structure_definition import NavStructureDefinition
from dataportal_generator.common.log.functions import get_logger
from dataportal_generator.common.model.project import Project
from dataportal_generator.feature_selection.core.exceptions import (
    ProfileTreeNodeGenerationException,
)
from dataportal_generator.feature_selection.model.profile_tree import ProfileTreeNode
from dataportal_generator.feature_selection.util.fhir.profile import (
    is_profile_selectable,
)

_logger = get_logger(__file__)


def _condense_profile_tree(
    profile_tree: ProfileTreeNode, distance_from_root: int = 0
) -> ProfileTreeNode:
    """
    Condenses a given profile tree by removing intermediate nodes that are not selectable and do not have multiple
    children
    :param profile_tree: `ProfileTreeNode` instance representing the root of a profile tree to condense
    :param distance_from_root: distance from root node to the current `ProfileTreeNode`. For internal use only.
                               Providing a value is discouraged
    :return: Condensed profile tree
    """
    if (
        len(profile_tree.children) > 1
        or profile_tree.selectable
        or profile_tree.is_leaf
        or distance_from_root == 1
    ):
        profile_tree.children = [
            _condense_profile_tree(c, distance_from_root + 1)
            for c in profile_tree.children
        ]
        return profile_tree
    else:
        # Exactly one child element should exist at this point since the node has neither more than one child nor is
        # a leaf node
        _logger.debug(f"Removing node {profile_tree.url!r} from the tree")
        return _condense_profile_tree(profile_tree.children[0], distance_from_root + 1)


def _update_selectability_for_tree(profile_tree: ProfileTreeNode):
    """
    Recursively updates availability of the nodes in a profile (sub) tree

    :param profile_tree: ``ProfileTreeNode`` object representing the root of a profile (sub) tree
    """
    if profile_tree.selectable and profile_tree.children:
        profile_tree.selectable = is_profile_selectable(profile_tree)
        for child in profile_tree.children:
            _update_selectability_for_tree(child)


def _update_selectability(profile_trees: list[ProfileTreeNode]):
    """
    Update ``ProfileTreeNode.selectable`` for all nodes in the given profile trees. Update candidates are nodes that
    are currently selectable and have children. If they only have children from the same module then the profile is
    considered abstract and thus not selectable. Note, that this is a heuristic and a workaround since the attribute
    is not properly set in many MII FHIR profiles ATM.

    :param profile_trees: List of ``ProfileTreeNode`` objects representing the roots of profile trees to update
    """
    for tree in profile_trees:
        _update_selectability_for_tree(tree)


class ProfileTreeGenerator:
    """
    Generates a list of trees where each node represents a FHIR profile and its children profiles using it as their
    base definition. The tree also holds information on whether a node should be selectable, e.g. whether its
    corresponding profile details should be selectable by the user as a feature in the data portal.
    """

    def __init__(
        self,
        project: Project,
    ):
        """
        :param project: Project for which the profile tree should be generated
        """
        self.__project = project
        self.__package_manager = project.package_manager

    def get_suitable_profiles(self) -> Iterator[NavStructureDefinition]:
        """
        Returns only those profiles which are snapshots that apply to FHIR resource types excluding Extension and are
        part of the Medical Informatics Initiative (MII)
        """
        for struct_def in self.__project.included_profiles(latest_only=True):
            if (
                struct_def.type != "Extension"
                and struct_def.kind == "resource"
                and struct_def.snapshot is not None
            ):
                yield struct_def

    def __insert_into_tree(
        self, node: ProfileTreeNode, deps: set[str], tree: list[ProfileTreeNode]
    ):
        """
        Inserts a node into the given profile (sub)tree using its dependency chain as a path in the tree. Tree nodes
        have to be inserted in order of their number of dependencies

        :param node: ``ProfileTreeNode`` object to insert into the tree
        :param deps: Set of canonical URLs making up the dependency chain, i.e. the structure definitions this profile
                     represented by node is (transitively) derived from
        :param tree: List of ``ProfileTreeNode`` objects representing the tree
        """
        if deps:
            for tree_node in tree:
                if tree_node.url in deps:
                    deps.remove(tree_node.url)
                    if len(deps) == 0:
                        tree_node.children.append(node)
                    else:
                        self.__insert_into_tree(node, deps, tree_node.children)
                    return
        tree.append(node)

    def __build_tree(self, nodes: list[ProfileTreeNode]) -> list[ProfileTreeNode]:
        """
        Constructs the profile tree from the list of all nodes it should contain. ``ProfileTreeNode.children`` will be
        filled as the tree is constructed

        :param nodes: List of ``ProfileTreeNode`` objects that will be part of the tree
        :return: List of ``ProfileTreeNode`` objects representing the first level of the tree (e.g. the immediate
                 subtrees with nodes as roots whose profiles do not have any dependency in the tree)
        """
        canonicals = {node.url for node in nodes}
        nodes_and_deps = []
        for node in nodes:
            struct_def = self.__package_manager.find_struct_def(node.url)
            deps = {
                dep.url
                for dep in self.__package_manager.dependencies_of(
                    struct_def, latest_only=False
                )
            }
            deps_in_tree = deps.intersection(canonicals)
            entry = (
                node,
                deps_in_tree,
            )
            nodes_and_deps.append(entry)
        tree = []
        for node, deps in sorted(nodes_and_deps, key=lambda t: len(t[1])):
            self.__insert_into_tree(node, deps, tree)
        return tree

    def generate_profile_tree(self, condense=True) -> list[ProfileTreeNode]:
        """
        Generates a profile tree from the profiles in scope
        :param condense: If set to `True` the tree will be condensed according to
                `ProfileTreeGenerator::__condense_profile_tree`
        :return: Generated profile tree
        """
        nodes = []
        for struct_def in self.get_suitable_profiles():
            # The Patient resource is selected by default due to its special status and thus there is no need to have
            # profiles constraining this resource type in the profile tree
            if struct_def.type == "Patient":
                _logger.info(
                    f"Profile '{struct_def.id}' will not be present in the profile tree as the "
                    f"Patient resource is selected by default => Skipping"
                )
                continue

            _logger.debug(f"Processing profile '{struct_def.name}'")
            try:
                nodes.append(
                    ProfileTreeNode(
                        url=struct_def.url,
                        selectable=(not struct_def.abstract) if struct_def.abstract else True
                    )
                )
            except Exception as exc:
                raise ProfileTreeNodeGenerationException(
                    f"Failed to generate profile tree node for structure definition '{struct_def.name}' "
                    f"({struct_def.url}{('|' + struct_def.version) if struct_def.version else ''})"
                ) from exc

        _logger.info("Building profile tree")
        tree = self.__build_tree(nodes)

        if condense:
            _logger.info("Condensing profile tree")
            tree = [_condense_profile_tree(tree_node) for tree_node in tree]

        # TODO: Remove once abstract element is properly set and enforced
        _update_selectability(tree)

        return tree
