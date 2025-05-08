import uuid
import re
import os
import json
import shutil
from pathlib import Path

from cohort_selection_ontology.model.ui_data import BulkTranslationDisplayElement, \
    BulkTranslation
from common.util.fhir.enums import FhirPrimitiveDataType
from common.util.log.functions import get_class_logger

from enum import Enum
from typing import Mapping, Optional, Any


class SnapshotPackageScope(str, Enum):
    MII = "mii"
    DEFAULT = "default"


def get_value_for_lang_code(data: Mapping[str, Any], lang_code: str) -> Optional[str]:
    for ext in data.get('extension', []):
        if any(e.get('url') == 'lang' and e.get('valueCode') == lang_code for e in ext.get('extension', [])):
            return next(e['valueString'] for e in ext['extension'] if e.get('url') == 'content')
    return None


class ProfileTreeGenerator:
    __logger = get_class_logger("ProfileTreeGenerator")

    def __init__(self, packages_dir: Path | str, snapshots_dir:  Path | str, exclude_dirs, excluded_profiles,
                 module_order, module_translation, fields_to_exclude, field_trees_to_exclude, profiles_to_process):
        self.profiles = {scope: dict() for scope in SnapshotPackageScope}
        self.packages_dir = Path(packages_dir).resolve()
        os.makedirs(self.packages_dir, exist_ok=True)
        self.snapshots_dir = Path(snapshots_dir).resolve()
        os.makedirs(self.snapshots_dir, exist_ok=True)
        self.exclude_dirs = exclude_dirs
        self.excluded_profiles = excluded_profiles
        self.module_order = module_order
        self.module_translation = module_translation
        self.fields_to_exclude = fields_to_exclude
        self.field_trees_to_exclude = field_trees_to_exclude
        self.profiles_to_process = profiles_to_process

    @staticmethod
    def get_name_from_id(id):
        name = id.split(".")[-1]
        name = name.split(":")[-1]
        name = name.replace("[x]", "")
        return name

    def filter_element(self, element: Mapping[str, any]) -> bool:
        # TODO: This is a temporary workaround to allow both the postal code and the country information to be selected
        #       during data selection. To preserve context, selecting elements with simple data types which are not on
        #       the top level of a resource is disabled (e.g. to forbid selecting just Coding.code without
        #       Coding.system etc.).
        #       In the future we should switch to a more dynamic solution were the selectable elements can be defined in
        #       externalized config files using a well-defined syntax to prevent such hard-coded solutions.
        element_id = element.get('id')
        if element_id in {"Patient.address:Strassenanschrift.postalCode", "Patient.address:Strassenanschrift.country"}:
            return False

        attributes_true_level_one = ["mustSupport", "isModifier", "min"]
        try:
            path = re.split(r"[.:]", element["id"])
            path = path[1:]
        except KeyError:
            self.__logger.warning(f"ElementDefinition instance will be rejected since it does not have an 'id' element "
                                  f"[path='{element.get('path')}']")
            return False

        if "type" in element and element["type"][0]["code"] in FhirPrimitiveDataType and len(path) > 1:
            return True

        if all(element.get(attr) is False or element.get(attr) == 0 or attr not in element
               for attr in attributes_true_level_one):
            return True

        attributes_true_level_two = ["mustSupport", "isModifier"]

        if all(element.get(attr) is False or element.get(attr) == 0 or attr not in element
               for attr in attributes_true_level_two) and len(element["id"].split(".")) > 2:
            return True

        if any(element['id'].endswith(field) or f"{field}." in element['id'] for field in self.fields_to_exclude):
            return True

        if any(f"{field}" in element['id'] for field in self.field_trees_to_exclude):
            return True

        if "[x]" in element['id'] and not element['id'].endswith("[x]"):
            return True

        if element["base"]["path"].split(".")[0] in {"Resource", "DomainResource"} and not "mustSupport" in element:
            return True

    def get_field_names_for_profile(self, struct_def) -> BulkTranslationDisplayElement:
        names_original = []
        names_en = []
        names_de = []

        for element in struct_def["snapshot"]["element"]:
            if self.filter_element(element):
                continue

            elem_name_de = get_value_for_lang_code(element.get('_short', {}), "de-DE")
            elem_name_en = get_value_for_lang_code(element.get('_short', {}), "en-US")

            names_original.append(self.get_name_from_id(element["id"]))

            #if elem_name_de == "":
            #    continue

            names_de.append(elem_name_de)
            names_en.append(elem_name_en)

        return BulkTranslationDisplayElement(
            original=names_original,
            translations=[
                BulkTranslation(
                    language="de-DE",
                    value=names_de
                ),
                BulkTranslation(
                    language="en-US",
                    value=names_en
                )
            ]
        )

    def build_profile_path(self, path, profile, profiles):
        profile_struct = profile["structureDefinition"]
        parent_profile_url = profile_struct.get("baseDefinition")

        try:
            profile_field_names = self.get_field_names_for_profile(profile_struct)
        except KeyError as err:
            print(profile["structureDefinition"]["url"])
            raise err

        path.insert(
            0,
            {
                "id": str(uuid.uuid4()),
                "name": profile["name"],
                "display": {
                    "original": profile_struct.get("title", ""),
                    "translations": [
                        {
                            "language": "de-DE",
                            "value": get_value_for_lang_code(profile_struct.get('_title', {}), "de-DE")
                        },
                        {
                            "language": "en-US",
                            "value": get_value_for_lang_code(profile_struct.get('_title', {}), "en-US")
                        }
                    ]
                },
                "fields": profile_field_names,
                "module": profile["module"],
                "url": profile["url"],
            },
        )

        if parent_profile_url in profiles:
            parent_profile = profiles[parent_profile_url]
            self.build_profile_path(path, parent_profile, profiles)

        return path

    def get_profile_in_node(self, node, name):
        if "children" not in node:
            node["children"] = []

        children = node["children"]

        for index in range(0, len(children)):

            child = children[index]
            if child["name"] == name:
                return index

        return -1

    def insert_path_to_tree(self, tree, path):
        cur_node = tree
        for index in range(0, len(path)):

            profile = path[index]

            profile_child_index = self.get_profile_in_node(cur_node, profile["name"])

            if index == len(path) - 1 and profile_child_index == -1:
                profile["leaf"] = True
                profile["selectable"] = True
            else:
                profile["leaf"] = False
                profile["selectable"] = False

            if profile_child_index == -1:
                cur_node["children"].append(profile)
                profile_child_index = self.get_profile_in_node(cur_node, profile["name"])
                cur_node = cur_node["children"][profile_child_index]
            else:
                cur_node = cur_node["children"][profile_child_index]

    def module_name_to_display(self, profile_name):
        parts = profile_name.split('-')
        if len(parts) > 1:
            return parts[1].capitalize()
        return profile_name

    def extract_module_string(self, path):
        match = re.search(r"/(?P<module>modul-[^/]+)/", path)
        if match:
            return match.group("module")
        return None

    def copy_profile_snapshots(self):
        #exclude_dirs = set(os.path.abspath(os.path.join(self.packages_dir, d)) for d in self.exclude_dirs)
        #print(exclude_dirs)
        if not any(self.packages_dir.iterdir()):
            self.__logger.warning(f"Package directory @ '{self.packages_dir}' is empty => No snapshots can be copied")

        package_dirs = [os.path.join(self.packages_dir, i) for i in os.listdir(self.packages_dir)
                        if os.path.isdir(os.path.join(self.packages_dir, i)) and i not in self.exclude_dirs]
        os.makedirs(os.path.join(self.snapshots_dir, "mii"), exist_ok=True)
        os.makedirs(os.path.join(self.snapshots_dir, "default"), exist_ok=True)

        for package_dir in package_dirs:
            manifest_file_path = os.path.join(package_dir, "package", "package.json")
            snapshot_scope = self.determine_snapshot_scope_for_package(manifest_file_path)

            for file_path in Path(package_dir, "package").resolve().rglob("*.json"):
                try:
                    with open(file_path, mode="r", encoding='utf-8-sig') as f:
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
                                and content["kind"] == "resource" or content.get("type") == "Extension"
                                and content["url"] not in self.excluded_profiles
                        ):
                            destination = os.path.join(os.path.join(self.snapshots_dir, snapshot_scope),
                                                       os.path.basename(file_path))
                            self.__logger.info(f"Copying snapshot file for further processing: {file_path} -> "
                                               f"{destination}")
                            shutil.copy(file_path, destination)
                except UnicodeDecodeError:
                    self.__logger.warning(f"File {file_path} is not a text file or cannot be read as text.")
                except Exception as exc:
                    self.__logger.error(f"Failed to copy file '{file_path}'", exc_info=exc)


    def get_profile_snapshots(self):
        for root, dirs, files in os.walk(self.snapshots_dir):
            dirs[:] = [d for d in dirs if os.path.abspath(os.path.join(root, d))]

            for file in (file for file in files if file.endswith(".json")):
                file_path = os.path.join(root, file)
                scope = SnapshotPackageScope(file_path.split(os.sep)[-2]).value

                try:
                    with open(file_path, mode='r', encoding='utf-8') as f:
                        content = json.load(f)

                        if self.profiles_to_process and content["url"] not in self.profiles_to_process:
                            continue

                        if (
                                "resourceType" in content
                                and content["resourceType"] == "StructureDefinition"
                                # and content["status"] == "active"
                                and content["kind"] == "resource" or content.get("type") == "Extension"
                                and content.get("snapshot")
                        ):
                            module_extract = self.extract_module_string(content["url"])
                            module = content["url"]

                            if module_extract:
                                module = module_extract

                            self.profiles[scope][content["url"]] = {
                                "structureDefinition": content,
                                "name": content["name"],
                                "module": module,
                                "url": content["url"],
                            }

                            self.__logger.info(f"Adding profile snapshot to tree: {file_path}")

                        else:
                            self.__logger.debug(f"Profile did not match criteria for inclusion: {file_path}")

                except UnicodeDecodeError:
                    self.__logger.warning(f"File {file_path} is not a text file or cannot be read as text => Skipping")
                except Exception as exc:
                    self.__logger.warning(f"File {file_path} could not be processed. Reason: {exc}", exc_info=exc)

    @staticmethod
    def custom_sort(item, order):
        name = item.get('name')
        if name in order:
            return 0, order.index(name)
        else:
            return 1, name

    def __get_profiles(self, scope: Optional[str] = None) -> Mapping[str, Mapping[str, Any]]:
        """
        Returns all profile entries in a certain scope or all if none is provided
        :param scope: Scope from which to return the profile entries
        :return: All profile entries matching the provided scope
        """
        if scope:
            return self.profiles.get(scope, {})
        else:
            return {k: v for d in self.profiles.values() for k, v in d.items()}

    def get_suitable_mii_profiles(self) -> Mapping[str, Mapping[str, any]]:
        """
        Returns only those profiles which are snapshots that apply to FHIR resource types excluding Extension and are
        part of the Medical Informatics Initiative (MII)
        <"""
        profiles = {}
        for url, profile in self.profiles.get('mii', {}).items():
            snapshot = profile.get('structureDefinition')
            if snapshot.get('type') != "Extension" and snapshot.get('kind') == 'resource' and 'snapshot' in snapshot:
                profiles[url] = profile
        return  profiles

    def generate_profiles_tree(self):
        self.__logger.info("Generating profile tree")

        tree = {"name": "Root", "module": "no-module", "url": "no-url", "children": [], "selectable": False}

        for profile in self.get_suitable_mii_profiles().values():
            # The Patient resource is selected by default due to its special status and thus there is no need to have
            # profiles constraining this resource type in the profile tree
            struct_def = profile.get('structureDefinition', {})
            if struct_def.get('type') == "Patient":
                self.__logger.info(f"Profile '{struct_def.get('id')}' will not be present in the profile tree as the "
                                   f"Patient resource is selected by default => Skipping")
                continue

            self.__logger.info(f"Processing profile {profile.get('name')}")
            try:
                path = self.build_profile_path([], profile, self.__get_profiles(SnapshotPackageScope.MII))
                module = profile["module"]
                path.insert(0, {
                    "id": str(uuid.uuid4()),
                    "name": module,
                    "display": {
                        "original": self.module_translation["de-DE"].get(module, module),
                        "translations": [
                            {
                                "language": "de-DE",
                                "value": self.module_translation["de-DE"].get(module, module)
                            },
                            {
                                "language": "en-US",
                                "value": self.module_translation["en-US"].get(module, module)
                            }
                        ]
                    },
                    "url": module,
                    "module": module,
                    "selectable": False,
                    "leaf": False,
                    "fields": {
                        "original": [],
                        "translations": [
                            {
                                "language": "de-DE",
                                "value": []
                            },
                            {
                                "language": "en-US",
                                "value": []
                            }
                        ]
                    }
                })
                self.insert_path_to_tree(tree, path)
            except Exception as exc:
                print(profile.get('name'))
                raise exc

        sorted_tree = tree

        sorted_tree['children'] = sorted(tree['children'], key=lambda item: self.custom_sort(item, self.module_order))

        return sorted_tree

    @staticmethod
    def determine_snapshot_scope_for_package(manifest_file_path: Path | str) -> SnapshotPackageScope:
        with open(manifest_file_path, encoding="utf8", mode="r") as manifest_file:
            manifest = json.load(manifest_file)
            package_name =  manifest.get('name', None)
            if not package_name:
                return SnapshotPackageScope.DEFAULT
            elif package_name.startswith("de.medizininformatikinitiative"):
                return SnapshotPackageScope.MII
            else:
                return SnapshotPackageScope.DEFAULT
