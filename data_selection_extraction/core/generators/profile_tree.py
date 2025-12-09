import uuid
import re
import os
import json
import shutil
from os.path import basename
from pathlib import Path

import pydantic
from fhir.resources.R4B.elementdefinition import ElementDefinition
from fhir.resources.R4B.structuredefinition import StructureDefinition

from cohort_selection_ontology.model.ui_data import (
    BulkTranslationDisplayElement,
    BulkTranslation,
    TranslationDisplayElement,
    Translation,
)
from common.model.fhir.structure_definition import IndexedStructureDefinition
from common.model.structure_definition import StructureDefinitionSnapshot
from common.util.fhir.enums import FhirPrimitiveDataType, FhirComplexDataType
from common.util.log.functions import get_class_logger

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


_EXT_ELEM_PATTERN = re.compile(
    r".*extension(:(?P<slice_name>[a-zA-Z0-9\/\\\-_\[\]\@]+))?"
)


class SnapshotPackageScope(str, Enum):
    MII = "mii"
    DEFAULT = "default"


def get_value_for_lang_code(data: ElementDefinition, lang_code: str) -> Optional[str]:
    if data is None:
        return None
    for ext in data.extension:
        if any(e.url == "lang" and e.valueCode == lang_code for e in ext.extension):
            return next(e.valueString for e in ext.extension if e.url == "content")
    return None


class ProfileTreeGenerator:
    __logger = get_class_logger("ProfileTreeGenerator")

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
            self.__logger.info(
                f"Excluding: {element['id']} as having references to patients"
            )
            return True

        # attributes_true_level_two = ["mustSupport", "isModifier"]

        if len(element.id.split(".")) > 2 and all(
            t.code in FhirPrimitiveDataType
            for t in get_types_supported_by_element(element)
        ):
            self.__logger.debug(
                f"Excluding: {element.id} as primitively-typed on level > 2"
            )
            return True

        # if any(
        #    element.id.endswith(field) or f"{field}." in element.id
        #    for field in self.fields_to_exclude
        # ):
        #    self.__logger.debug(f"Excluding: {element.id} as excluded field")
        #    return True

        # if any(f"{field}" in element.id for field in self.field_trees_to_exclude):
        #    self.__logger.debug(f"Excluding: {element.id} as part of field tree")
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
            self.__logger.debug(
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

    def get_field_names_for_profile(
        self, struct_def: StructureDefinitionSnapshot
    ) -> BulkTranslationDisplayElement:
        names_original = []
        names_en = []
        names_de = []

        for element in struct_def.snapshot.element:
            element: ElementDefinition
            if self.filter_element(element, struct_def):
                continue

            elem_name_de = get_value_for_lang_code(element.short__ext, "de-DE")
            elem_name_en = get_value_for_lang_code(element.short__ext, "en-US")

            names_original.append(self.get_name_from_id(element.id))

            # if elem_name_de == "":
            #    continue

            names_de.append(elem_name_de)
            names_en.append(elem_name_en)

        return BulkTranslationDisplayElement(
            original=names_original,
            translations=[
                BulkTranslation(language="de-DE", value=names_de),
                BulkTranslation(language="en-US", value=names_en),
            ],
        )

    def build_profile_path(self, path, profile, profiles) -> List[ProfileTreeNode]:
        profile_struct: StructureDefinitionSnapshot = profile["structureDefinition"]
        parent_profile_url = profile_struct.baseDefinition

        try:
            profile_field_names = self.get_field_names_for_profile(profile_struct)
        except KeyError as err:
            raise err

        path.insert(
            0,
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
                fields=profile_field_names,
                module=profile["module"],
                url=profile["url"],
            ),
        )

        if parent_profile_url in profiles:
            parent_profile = profiles[parent_profile_url]
            self.build_profile_path(path, parent_profile, profiles)

        return path

    def get_profile_in_node(self, node: ProfileTreeNode, name: str):
        children = node.children
        for index in range(0, len(children)):
            child = children[index]
            if child.name == name:
                return index
        return -1

    def insert_path_to_tree(self, tree: ProfileTreeNode, path: List[ProfileTreeNode]):
        cur_node = tree
        for index in range(0, len(path)):
            profile = path[index]

            profile_child_index = self.get_profile_in_node(cur_node, profile.name)

            snapshot = self.__all_profiles.get(profile.url, {}).get(
                "structureDefinition"
            )
            profile.selectable = is_profile_selectable(snapshot, self.__all_profiles)

            if profile_child_index == -1:
                cur_node.children.append(profile)
                profile_child_index = self.get_profile_in_node(cur_node, profile.name)
                cur_node = cur_node.children[profile_child_index]
            else:
                cur_node = cur_node.children[profile_child_index]

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
            self.__logger.warning(
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
                            self.__logger.info(
                                f"Copying snapshot file for further processing: {file_path} -> "
                                f"{destination}"
                            )
                            shutil.copy(file_path, destination)
                except UnicodeDecodeError:
                    self.__logger.warning(
                        f"File {file_path} is not a text file or cannot be read as text."
                    )
                except Exception as exc:
                    self.__logger.error(
                        f"Failed to copy file '{file_path}'", exc_info=exc
                    )

    def get_profile_snapshots(self):
        for root, dirs, files in os.walk(self.snapshots_dir):
            dirs[:] = [d for d in dirs if os.path.abspath(os.path.join(root, d))]

            for file in (file for file in files if file.endswith(".json")):
                file_path = os.path.join(root, file)
                scope = SnapshotPackageScope(file_path.split(os.sep)[-2]).value

                try:
                    with open(file_path, mode="r", encoding="utf-8") as f:
                        try:
                            content = StructureDefinitionSnapshot.model_validate_json(
                                f.read()
                            )
                        except pydantic.ValidationError as e:
                            error_list = ""
                            for err in e.errors():
                                loc = err["loc"]
                                error_list = (
                                    f"\n\t\t\t{ '.'.join(map(str, loc))}: {err['msg']}"
                                )
                            self.__logger.error(
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

                            self.__logger.info(
                                f"Adding profile snapshot to tree: {file_path}"
                            )

                        else:
                            self.__logger.debug(
                                f"Profile did not match criteria for inclusion: {file_path}"
                            )

                except UnicodeDecodeError:
                    self.__logger.warning(
                        f"File {file_path} is not a text file or cannot be read as text => Skipping"
                    )
                except Exception as exc:
                    self.__logger.warning(
                        f"File {file_path} could not be processed. Reason: {exc}",
                        exc_info=exc,
                    )

        self.__all_profiles = self.__get_profiles()

    @staticmethod
    def custom_sort(item, order):
        name = item.name
        if name in order:
            return 0, order.index(name)
        else:
            return 1, name

    def get_suitable_mii_profiles(self) -> Mapping[str, Mapping[str, any]]:
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

    def generate_profiles_tree(self, condense=True):
        """
        Generates a profile tree from the profiles in scope
        :param condense: If set to `True` the tree will be condensed according to
                `ProfileTreeGenerator::__condense_profile_tree`
        :return: Generated profile tree
        """
        self.__logger.info("Generating profile tree")

        # tree = {"name": "Root", "module": "no-module", "url": "no-url", "children": [], "selectable": False}
        tree = ProfileTreeNode(id="root", name="Root")

        for profile in self.get_suitable_mii_profiles().values():
            # The Patient resource is selected by default due to its special status and thus there is no need to have
            # profiles constraining this resource type in the profile tree
            struct_def = profile.get("structureDefinition", {})
            if struct_def.type == "Patient":
                self.__logger.info(
                    f"Profile '{struct_def.id}' will not be present in the profile tree as the "
                    f"Patient resource is selected by default => Skipping"
                )
                continue

            self.__logger.info(f"Processing profile {profile.get('name')}")
            try:
                path = self.build_profile_path(
                    [], profile, self.__get_profiles(SnapshotPackageScope.MII)
                )
                module = profile["module"]
                path.insert(
                    0,
                    ProfileTreeNode(
                        id=str(uuid.uuid4()),
                        name=module,
                        display=TranslationDisplayElement(
                            original=self.module_translation["de-DE"].get(
                                module, module
                            ),
                            translations=[
                                Translation(
                                    language="de-DE",
                                    value=self.module_translation["de-DE"].get(
                                        module, module
                                    ),
                                ),
                                Translation(
                                    language="en-US",
                                    value=self.module_translation["en-US"].get(
                                        module, module
                                    ),
                                ),
                            ],
                        ),
                        url=module,
                        module=module,
                        selectable=False,
                        fields=BulkTranslationDisplayElement(
                            original=[],
                            translations=[
                                BulkTranslation(language="de-DE", value=[]),
                                BulkTranslation(language="en-US", value=[]),
                            ],
                        ),
                    ),
                )
                self.insert_path_to_tree(tree, path)
            except Exception as exc:
                self.__logger.error(profile.get("name"))
                raise exc

        if condense:
            self.__logger.info("Condensing profile tree")
            tree = self.__condense_profile_tree(tree)

        sorted_tree = tree
        sorted_tree.children = sorted(
            tree.children, key=lambda item: self.custom_sort(item, self.module_order)
        )

        return sorted_tree

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

    @classmethod
    def __condense_profile_tree(
        cls, profile_tree: ProfileTreeNode, distance_from_root: int = 0
    ) -> ProfileTreeNode:
        """
        Condenses a given profile tree by removing intermediate nodes that are not selectable and do not have multiple
        children
        :param profile_tree: `ProfileTreeNode` instance representing the root of a profile tree to condense
        :param distance_from_root: distance from root node to the current `ProfileTreeNode`. For internal use only. Providing a value is discouraged
        :return: Condensed profile tree
        """
        if (
            len(profile_tree.children) > 1
            or profile_tree.selectable
            or profile_tree.leaf
            or distance_from_root == 1
        ):
            tree = profile_tree.model_copy()
        else:
            # Exactly one child element should exist at this point since the node has neither more than one child nor is
            # a leaf node
            child_names = [f"'{n.name}'" for n in profile_tree.children]
            cls.__logger.info(
                f"Removing node [id='{profile_tree.id}', name='{profile_tree.name}'] from tree "
                f"[children={child_names}]"
            )
            tree = profile_tree.children[0].model_copy()
        tree.children = [
            ProfileTreeGenerator.__condense_profile_tree(n, distance_from_root + 1)
            for n in tree.children
        ]
        return tree
