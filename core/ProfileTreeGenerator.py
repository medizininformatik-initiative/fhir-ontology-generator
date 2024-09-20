import uuid
import re
import os
import json

class ProfileTreeGenerator():

    def __init__(self, packagesDir: str, exclude_dirs, module_order):

        self.profiles = {}
        self.packagesDir = packagesDir
        self.exclude_dirs = exclude_dirs
        self.module_order = module_order

    def build_profile_path(self, path, profile, profiles, translated_profiles):

        profile_struct = profile["structureDefinition"]
        parent_profile_url = profile_struct["baseDefinition"]

        translated_profile = translated_profiles[profile["url"]]
        translation_de = translated_profile['display']['translation']['de']

        if translation_de != "":
            display = translation_de
        else:
            display = profile_struct["title"]

        path.insert(
            0,
            {
                "id": str(uuid.uuid4()),
                "name": profile["name"],
                "display": display,
                "module": profile["module"],
                "url": profile["url"],
            },
        )

        if parent_profile_url in profiles:
            parent_profile = profiles[parent_profile_url]
            self.build_profile_path(path, parent_profile, profiles, translated_profiles)

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

            if index == len(path) - 1:
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

    def extract_modul_string(self, path):
        match = re.search(r"/(?P<module>modul-[^/]+)/", path)
        if match:
            return match.group("module")
        return None

    def get_profiles(self):

        exclude_dirs = set(os.path.abspath(os.path.join(self.packagesDir, d)) for d in self.exclude_dirs)

        for root, dirs, files in os.walk(self.packagesDir):
            dirs[:] = [d for d in dirs if os.path.abspath(os.path.join(root, d)) not in exclude_dirs]

            for file in (file for file in files if file.endswith(".json")):
                file_path = os.path.join(root, file)

                if "/examples/" in file_path:
                    continue

                try:

                    with open(file_path, "r") as f:

                        content = json.load(f)

                        if (
                                "resourceType" in content
                                and content["resourceType"] == "StructureDefinition"
                                and content["baseDefinition"]
                                not in ["http://hl7.org/fhir/StructureDefinition/Extension"]
                                and content["status"] == "active"
                                and content["kind"] == "resource"
                        ):

                            module_extract = self.extract_modul_string(content["url"])
                            module = content["url"]

                            if module_extract:
                                module = module_extract

                            self.profiles[content["url"]] = {
                                "structureDefinition": content,
                                "name": content["name"],
                                "module": module,
                                "url": content["url"],
                            }

                            print(f"Adding profile to tree: {file_path}")

                except UnicodeDecodeError:
                    print(f"File {file_path} is not a text file or cannot be read as text.")
                except Exception:
                    pass

    def custom_sort(self, item, order):
        name = item["display"]
        if name in order:
            return (0, order.index(name))
        else:
            return (1, name)

    def generate_profiles_tree(self, translated_profiles):

        tree = {"name": "Root", "module": "no-module", "url": "no-url", "children": [], "selectable": False}

        for profile in self.profiles.values():

            translated_profile = translated_profiles[profile["module"]]
            translation_de = translated_profile['display']['translation']['de']

            if translation_de != "":
                display = translation_de
            else:
                display = self.module_name_to_display(profile["module"])

            path = self.build_profile_path([], profile, self.profiles, translated_profiles)
            path.insert(0, {
                "id": str(uuid.uuid4()),
                "name": profile["module"],
                "display": display,
                "url": profile["module"],
                "module": profile["module"],
                "selectable": False,
                "leaf": False
            }
                        )

            self.insert_path_to_tree(tree, path)

        sorted_tree = tree

        sorted_tree['children'] = sorted(tree['children'], key= lambda item: self.custom_sort(item, self.module_order))

        return sorted_tree
