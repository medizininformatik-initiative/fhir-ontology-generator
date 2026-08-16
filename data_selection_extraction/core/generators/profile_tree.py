import uuid
import re
import os
import json
import shutil
from os.path import basename
from pathlib import Path

import cachetools
import pydantic
from fhir.resources.R4B.elementdefinition import ElementDefinition
from fhir.resources.R4B.structuredefinition import StructureDefinition

from cohort_selection_ontology.model.ui_data import (
    TranslationDisplayElement,
    Translation,
)
from common.model.fhir.pydantic import construct_model
from common.model.fhir.structure_definition import (
    IndexedStructureDefinition,
    idx_struct_def_discriminator,
)
from common.model.fhir.structure_definition import StructureDefinitionSnapshot
from common.util.fhir.enums import FhirPrimitiveDataType, FhirComplexDataType
from common.util.log.functions import get_logger

from enum import Enum
from typing import Mapping, Optional, Any, List

from common.util.project import Project
from common.util.structure_definition.functions import (
    supports_type,
    get_types_supported_by_element,
)
from data_selection_extraction.config.profile_detail import FieldsConfig
from data_selection_extraction.model.profile_tree import ProfileTreeNode
from data_selection_extraction.util.fhir.profile import is_profile_selectable

_logger = get_logger(__file__)


_EXT_ELEM_PATTERN = re.compile(
    r".*extension(:(?P<slice_name>[a-zA-Z0-9\/\\\-_\[\]\@]+))?"
)


class SnapshotPackageScope(str, Enum):
    MII = "mii"
    DEFAULT = "default"


def get_value_for_lang_code(data: ElementDefinition, lang_code: str) -> Optional[str]:
    if data and (extensions := data.extension):
        for transl_ext in filter(
            lambda ext: ext.url
            == "http://hl7.org/fhir/StructureDefinition/translation",
            extensions,
        ):
            if any(
                e.url == "lang" and e.valueCode == lang_code
                for e in transl_ext.extension
            ):
                return next(
                    (e.valueString for e in transl_ext.extension if e.url == "content"),
                    None,
                )
    return None


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
        or profile_tree.leaf
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
        _logger.info(f"Removing node {profile_tree.name!r} from the tree")
        return _condense_profile_tree(profile_tree.children[0], distance_from_root + 1)


class ProfileTreeGenerator:

    def __init__(
        self,
        packages_dir: Path | str,
        snapshots_dir: Path | str,
        excluded_dirs,
        excluded_profiles,
        module_order,
        module_translation,
        fields_config: FieldsConfig,
        profiles_to_process,
        project: Project,
    ):
        """
        :param packages_dir: dependencies folder
        :param snapshots_dir: snapshots folder
        :param excluded_dirs: folders to exclude from the packages_dir
        :param excluded_profiles: list profile urls to exclude
        :param module_order: order in which the modules should be computed
        :param module_translation: mapping containing translation of module names
        :param fields_config: `FieldsConfig` object describing what fields
        :param profiles_to_process: list of profiles to process - if empty, process all
        :param project: project for which the details should be generated
        """
        self.profiles = {scope: {} for scope in SnapshotPackageScope}
        self.packages_dir = Path(packages_dir).resolve()
        os.makedirs(self.packages_dir, exist_ok=True)

        self.snapshots_dir = Path(snapshots_dir).resolve()
        os.makedirs(self.snapshots_dir, exist_ok=True)

        self.exclude_dirs = excluded_dirs
        self.excluded_profiles = excluded_profiles
        self.module_order = module_order
        self.module_translation = module_translation
        self.fields_config = fields_config
        self.profiles_to_process = profiles_to_process
        self.__project = project
        self.__package_manager = project.package_manager

    @cachetools.cachedmethod(
        cache=lambda self: self.__is_included_cache,
        key=lambda _, ed, pr: pr.url + "#" + ed.id,
    )
    def is_field_included(
        self, elem_def: ElementDefinition, profile: IndexedStructureDefinition
    ) -> bool:
        if profile.get_aggregated_max_cardinality(elem_def.id) == 0:
            return False
        is_included = self.fields_config.is_included(
            elem_def, profile, self.__project.package_manager
        )
        if is_included is None:
            return not self.filter_element(elem_def, profile)
        else:
            return is_included

    def __get_profiles(
        self, scope: Optional[str] = None
    ) -> Mapping[str, Mapping[str, Any | StructureDefinitionSnapshot]]:
        """
        Returns all profile entries in a certain scope or all if none is provided
        :param scope: Scope from which to return the profile entries
        :return: All profile entries matching the provided scope
        """
        if scope:
            return self.profiles.get(scope, {})
        else:
            return {k: v for d in self.profiles.values() for k, v in d.items()}

    @staticmethod
    def get_name_from_id(id):
        name = id.split(".")[-1]
        name = name.split(":")[-1]
        name = name.replace("[x]", "")
        return name

    def filter_element(
        self, element: ElementDefinition, profile: IndexedStructureDefinition
    ) -> bool:
        # TODO: This is a temporary workaround to allow both the postal code and the country information to be selected
        #       during data selection. To preserve context, selecting elements with simple data types which are not on
        #       the top level of a resource is disabled (e.g. to forbid selecting just Coding.code without
        #       Coding.system etc.).
        #       In the future we should switch to a more dynamic solution were the selectable elements can be defined in
        #       externalized config files using a well-defined syntax to prevent such hard-coded solutions.
        element_id: str = element.id
        if element_id in {
            "Patient.address:Strassenanschrift.postalCode",
            "Patient.address:Strassenanschrift.country",
        }:
            return False

        if (
            getattr(element, "subject", None) is not None
            or getattr(element, "patient", None) is not None
        ):
            _logger.info(f"Excluding: {element['id']} as having references to patients")
            return True

        # attributes_true_level_two = ["mustSupport", "isModifier"]

        if len(element.id.split(".")) > 2 and all(
            t.code in FhirPrimitiveDataType
            for t in get_types_supported_by_element(element)
        ):
            _logger.debug(f"Excluding: {element.id} as primitively-typed on level > 2")
            return True

        # if any(
        #    element.id.endswith(field) or f"{field}." in element.id
        #    for field in self.fields_to_exclude
        # ):
        #    _logger.debug(f"Excluding: {element.id} as excluded field")
        #    return True

        # if any(f"{field}" in element.id for field in self.field_trees_to_exclude):
        #    _logger.debug(f"Excluding: {element.id} as part of field tree")
        #    return True

        parent_elem = profile.get_element_by_id(element_id.rsplit(".", maxsplit=1)[0])
        # Exclude all sub-elements of primitive FHIR data types
        if not supports_type(element, FhirComplexDataType.EXTENSION) and (
            types := get_types_supported_by_element(parent_elem)
        ):
            if all(map(lambda t: t.code in FhirPrimitiveDataType, types)):
                return True

        if matches := [*_EXT_ELEM_PATTERN.finditer(element.id)]:
            # If the element is itself or a child of an unsliced 'extension' element it will be excluded
            for m in matches:
                if not m.group("slice_name"):
                    return True
            # All but the sliced extension element itself will be excluded
            return (m := matches[-1]).group("slice_name") and m.end("slice_name") < len(
                element.id
            )

        if (
            element.base.path.split(".")[0] in {"Resource", "DomainResource"}
            and element.mustSupport is not None
        ):
            _logger.debug(
                f"Excluding: {element.id} as base is Resource or DomainResource and not mustSupport"
            )
            return True

        # Do not allow sub elements (that are not a reference) of BackboneElement typed elements to be selected
        elem_id_split = element.id.rsplit(".", maxsplit=1)
        if len(elem_id_split) == 1:
            return False
        parent_elem = profile.get_element_by_id(elem_id_split[0])
        elem = profile.get_element_by_id(element.id)
        while parent_elem is not None:
            if supports_type(
                parent_elem, FhirComplexDataType.BACKBONE_ELEMENT
            ) and not supports_type(elem, FhirComplexDataType.REFERENCE):
                return True
            elem_id_split = parent_elem.id.rsplit(".", maxsplit=1)
            if len(elem_id_split) == 1:
                return False
            parent_elem = profile.get_element_by_id(elem_id_split[0])

        return False

    def is_field_included(
        self,
        elem_def: ElementDefinition,
        profile: StructureDefinition,
    ) -> bool:
        is_included = self.fields_config.is_included(
            elem_def, profile, self.__project.package_manager
        )
        if is_included is None:
            return not self.filter_element(elem_def, profile)
        else:
            return is_included

    def get_fields_for_profile(
        self, struct_def: StructureDefinitionSnapshot
    ) -> list[tuple[TranslationDisplayElement, TranslationDisplayElement | None]]:
        fields = []

        for element in struct_def.snapshot.element:
            element: ElementDefinition
            if not self.is_field_included(element, struct_def):
                continue

            fields.append(
                (
                    TranslationDisplayElement(
                        original=self.get_name_from_id(element.id),
                        translations=[
                            Translation(
                                language="de-DE",
                                value=get_value_for_lang_code(
                                    element.short__ext, "de-DE"
                                ),
                            ),
                            Translation(
                                language="en-US",
                                value=get_value_for_lang_code(
                                    element.short__ext, "en-US"
                                ),
                            ),
                        ],
                    ),
                    (
                        TranslationDisplayElement(
                            original=element.definition,
                            translations=[
                                Translation(
                                    language="de-DE",
                                    value=get_value_for_lang_code(
                                        element.definition__ext, "de-DE"
                                    ),
                                ),
                                Translation(
                                    language="en-US",
                                    value=get_value_for_lang_code(
                                        element.definition__ext, "en-US"
                                    ),
                                ),
                            ],
                        )
                        if element.definition
                        else None
                    ),
                )
            )

        return fields

    def get_profile_in_node(self, node: ProfileTreeNode, name: str):
        children = node.children
        for index in range(0, len(children)):
            child = children[index]
            if child.name == name:
                return index
        return -1

    def module_name_to_display(self, profile_name):
        parts = profile_name.split("-")
        if len(parts) > 1:
            return parts[1].capitalize()
        return profile_name

    def extract_module_string(self, path):
        if path.startswith("https://www.medizininformatik-initiative.de"):
            match = re.search(r"/(?P<module>modul-[^/]+)/", path)
            if match:
                return match.group("module")
        elif path.startswith("https://gematik.de/fhir/isik"):
            return "modul-isik-vitalparameter"
        return None

    def copy_profile_snapshots(self):
        # exclude_dirs = set(os.path.abspath(os.path.join(self.packages_dir, d)) for d in self.exclude_dirs)
        # print(exclude_dirs)
        if not any(self.packages_dir.iterdir()):
            _logger.warning(
                f"Package directory @ '{self.packages_dir}' is empty => No snapshots can be copied"
            )

        package_dirs = [
            os.path.join(self.packages_dir, i)
            for i in os.listdir(self.packages_dir)
            if os.path.isdir(os.path.join(self.packages_dir, i))
            and i not in self.exclude_dirs
        ]
        os.makedirs(os.path.join(self.snapshots_dir, "mii"), exist_ok=True)
        os.makedirs(os.path.join(self.snapshots_dir, "default"), exist_ok=True)

        for package_dir in package_dirs:
            manifest_file_path = os.path.join(package_dir, "package", "package.json")
            snapshot_scope = self.determine_snapshot_scope_for_package(
                manifest_file_path
            )

            for file_path in Path(package_dir, "package").resolve().rglob("*.json"):
                try:
                    with open(file_path, mode="r", encoding="utf-8-sig") as f:
                        content = json.load(f)
                        if (
                            # "https://www.medizininformatik-initiative.de" in content["url"]
                            # and
                            "snapshot" in content
                            and "resourceType" in content
                            and content["resourceType"] == "StructureDefinition"
                            # and content["baseDefinition"]
                            # not in ["http://hl7.org/fhir/StructureDefinition/Extension"]
                            # and content["status"] == "active"
                            and content["kind"] == "resource"
                            or content.get("type") == "Extension"
                            and content["url"] not in self.excluded_profiles
                        ):
                            destination = os.path.join(
                                os.path.join(self.snapshots_dir, snapshot_scope),
                                os.path.basename(file_path),
                            )
                            _logger.info(
                                f"Copying snapshot file for further processing: {file_path} -> "
                                f"{destination}"
                            )
                            shutil.copy(file_path, destination)
                except UnicodeDecodeError:
                    _logger.warning(
                        f"File {file_path} is not a text file or cannot be read as text."
                    )
                except Exception as exc:
                    _logger.error(f"Failed to copy file '{file_path}'", exc_info=exc)

    def get_profile_snapshots(self):
        for root, dirs, files in os.walk(self.snapshots_dir):
            dirs[:] = [d for d in dirs if os.path.abspath(os.path.join(root, d))]

            for file in (file for file in files if file.endswith(".json")):
                file_path = os.path.join(root, file)
                scope = SnapshotPackageScope(file_path.split(os.sep)[-2]).value

                try:
                    with open(file_path, mode="r", encoding="utf-8") as f:
                        try:
                            content = construct_model(
                                idx_struct_def_discriminator, **json.load(f)
                            )
                        except pydantic.ValidationError as e:
                            error_list = ""
                            for err in e.errors():
                                loc = err["loc"]
                                error_list = (
                                    f"\n\t\t\t{ '.'.join(map(str, loc))}: {err['msg']}"
                                )
                            _logger.error(
                                f"Failed to parse snapshot {basename(file_path)} at {error_list}"
                            )

                        if (
                            self.profiles_to_process
                            and content.url not in self.profiles_to_process
                        ):
                            continue

                        if (
                            content.get_resource_type() is not None
                            and content.get_resource_type() == "StructureDefinition"
                            # and content["status"] == "active"
                            and (
                                content.kind == "resource"
                                or content.type == "Extension"
                            )
                            and content.snapshot
                        ):
                            module_extract = self.extract_module_string(content.url)
                            module = content.url

                            if module_extract:
                                module = module_extract

                            self.profiles[scope][content.url] = {
                                "structureDefinition": content,
                                "name": content.name,
                                "module": module,
                                "url": content.url,
                            }

                            _logger.info(
                                f"Adding profile snapshot to tree: {file_path}"
                            )

                        else:
                            _logger.debug(
                                f"Profile did not match criteria for inclusion: {file_path}"
                            )

                except UnicodeDecodeError:
                    _logger.warning(
                        f"File {file_path} is not a text file or cannot be read as text => Skipping"
                    )
                except Exception as exc:
                    _logger.warning(
                        f"File {file_path} could not be processed. Reason: {exc}",
                        exc_info=exc,
                    )

        self.__all_profiles = self.__get_profiles()

    def get_suitable_mii_profiles(self) -> Mapping[str, Mapping[str, Any]]:
        """
        Returns only those profiles which are snapshots that apply to FHIR resource types excluding Extension and are
        part of the Medical Informatics Initiative (MII)
        """
        profiles = {}
        mii_profiles = self.profiles.get("mii", {})
        for url, profile in mii_profiles.items():
            snapshot: StructureDefinitionSnapshot = profile.get("structureDefinition")
            if (
                snapshot.type != "Extension"
                and snapshot.kind == "resource"
                and snapshot.snapshot is not None
            ):
                profiles[url] = profile
        return profiles

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
                 subtrees with nodes as roots whos profiles do not have any dependency in the tree)
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

    def generate_profiles_tree(self, condense=True) -> list[ProfileTreeNode]:
        """
        Generates a profile tree from the profiles in scope
        :param condense: If set to `True` the tree will be condensed according to
                `ProfileTreeGenerator::__condense_profile_tree`
        :return: Generated profile tree
        """
        _logger.info("Generating profile tree nodes")
        nodes = []
        for profile in self.get_suitable_mii_profiles().values():
            # The Patient resource is selected by default due to its special status and thus there is no need to have
            # profiles constraining this resource type in the profile tree
            struct_def = profile.get("structureDefinition", {})
            if struct_def.type == "Patient":
                _logger.info(
                    f"Profile '{struct_def.id}' will not be present in the profile tree as the "
                    f"Patient resource is selected by default => Skipping"
                )
                continue

            _logger.debug(f"Processing profile {profile.get('name')!r}")
            try:
                profile_struct: StructureDefinitionSnapshot = profile[
                    "structureDefinition"
                ]

                try:
                    profile_field_names = self.get_fields_for_profile(profile_struct)
                except KeyError as err:
                    raise err

                profile_module = profile["module"]
                nodes.append(
                    ProfileTreeNode(
                        id=str(uuid.uuid4()),
                        name=profile["name"],
                        display=TranslationDisplayElement(
                            original=(
                                profile_struct.title
                                if profile_struct.title is not None
                                else profile_struct.name
                            ),
                            translations=[
                                Translation(
                                    language="de-DE",
                                    value=get_value_for_lang_code(
                                        profile_struct.title__ext, "de-DE"
                                    ),
                                ),
                                Translation(
                                    language="en-US",
                                    value=get_value_for_lang_code(
                                        profile_struct.title__ext, "en-US"
                                    ),
                                ),
                            ],
                        ),
                        description=TranslationDisplayElement(
                            original=str(profile_struct.description),
                            translations=[
                                Translation(
                                    language="de-DE",
                                    value=get_value_for_lang_code(
                                        profile_struct.description__ext, "de-DE"
                                    ),
                                ),
                                Translation(
                                    language="en-US",
                                    value=get_value_for_lang_code(
                                        profile_struct.description__ext, "en-US"
                                    ),
                                ),
                            ],
                        ),
                        fields=profile_field_names,
                        module=TranslationDisplayElement(
                            original=profile_module,
                            translations=[
                                Translation(
                                    language="de-DE",
                                    value=self.module_translation["de-DE"].get(
                                        profile_module, profile_module
                                    ),
                                ),
                                Translation(
                                    language="en-US",
                                    value=self.module_translation["en-US"].get(
                                        profile_module, profile_module
                                    ),
                                ),
                            ],
                        ),
                        url=profile["url"],
                        resource_type=profile_struct.type,
                        selectable=is_profile_selectable(
                            profile_struct, self.__all_profiles
                        ),
                    )
                )
            except Exception as exc:
                _logger.error(profile.get("name"))
                raise exc

        _logger.info("Building profile tree")
        tree = self.__build_tree(nodes)

        if condense:
            _logger.info("Condensing profile tree")
            tree = [_condense_profile_tree(tree_node) for tree_node in tree]

        return tree

    @staticmethod
    def determine_snapshot_scope_for_package(
        manifest_file_path: Path | str,
    ) -> SnapshotPackageScope:
        with open(manifest_file_path, encoding="utf8", mode="r") as manifest_file:
            manifest = json.load(manifest_file)
            package_name = manifest.get("name", None)
            if not package_name:
                return SnapshotPackageScope.DEFAULT
            # FIXME: Temporary fix to include ISIK profile in scope. Should be replaced to inclusion based on
            #        CapabilityStatements in MII packages
            elif package_name.startswith(
                "de.medizininformatikinitiative"
            ) or package_name.startswith("de.gematik.isik"):
                return SnapshotPackageScope.MII
            else:
                return SnapshotPackageScope.DEFAULT
