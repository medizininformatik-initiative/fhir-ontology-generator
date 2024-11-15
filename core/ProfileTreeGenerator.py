import uuid
import re
import os
import json
import shutil

class ProfileTreeGenerator():

    def __init__(self, packages_dir: str, snapshots_dir: str, exclude_dirs, module_order, module_translation, fields_to_exclude):

        self.profiles = {}
        self.packages_dir = packages_dir
        self.snapshots_dir = snapshots_dir
        self.exclude_dirs = exclude_dirs
        self.module_order = module_order
        self.module_translation = module_translation
        self.fields_to_exclude = fields_to_exclude
        self.simple_data_types = ["instant", "time", "date", "dateTime", "decimal", "boolean", "integer", "string",
                                  "uri", "base64Binary", "code", "id", "oid", "unsignedInt", "positiveInt", "markdown",
                                  "url", "canonical", "uuid"]

    def get_name_from_id(self, id):

        name = id.split(".")[-1]
        name = name.split(":")[-1]
        name = name.replace("[x]", "")

        return name

    def get_value_for_lang_code(self, data, langCode):
        for ext in data.get('extension', []):
            if any(e.get('url') == 'lang' and e.get('valueCode') == langCode for e in ext.get('extension', [])):
                return next(e['valueString'] for e in ext['extension'] if e.get('url') == 'content')
        return ""

    def filter_element(self, element):

        attributes_true_level_one = ["mustSupport", "isModifier", "min"]
        path = re.split(r"[.:]", element["id"])
        path = path[1:]

        if "type" in element and element["type"][0]["code"] in self.simple_data_types and len(path) > 1:
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

        if "[x]" in element['id'] and not element['id'].endswith("[x]"):
            return True

        if element["base"]["path"].split(".")[0] in {"Resource", "DomainResource"} and not "mustSupport" in element:
            return True

    def get_field_names_for_profile(self, struct_def):

        names_original = []
        names_en = []
        names_de = []

        for element in struct_def["snapshot"]["element"]:

            if self.filter_element(element):
                continue

            elem_name_de = self.get_value_for_lang_code(element.get('_short', {}), "de-DE")
            elem_name_en = self.get_value_for_lang_code(element.get('_short', {}), "en-US")

            names_original.append(self.get_name_from_id(element["id"]))

            if elem_name_de == "":
                continue

            names_de.append(elem_name_de)
            names_en.append(elem_name_en)

        return {
            "original": names_original,
            "translations": [
                {
                    "language": "de-DE",
                    "value": names_de
                },
                {
                    "language": "en-US",
                    "value": names_en
                }
            ]
        }

    def build_profile_path(self, path, profile, profiles):

        profile_struct = profile["structureDefinition"]
        parent_profile_url = profile_struct["baseDefinition"]

        profile_field_names = self.get_field_names_for_profile(profile_struct)

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
                            "value": self.get_value_for_lang_code(profile_struct.get('_title', {}), "de-DE")
                        },
                        {
                            "language": "en-US",
                            "value": self.get_value_for_lang_code(profile_struct.get('_title', {}), "en-US")
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


    def copy_profile_snapshots(self):

        exclude_dirs = set(os.path.abspath(os.path.join(self.packages_dir, d)) for d in self.exclude_dirs)

        for root, dirs, files in os.walk(self.packages_dir):
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

                            destination = f"{self.snapshots_dir}/{os.path.basename(file_path)}"
                            print(f"Copying snapshot file for further processing: {file_path} -> {destination}")
                            shutil.copy(file_path, destination)

                except UnicodeDecodeError:
                    print(f"File {file_path} is not a text file or cannot be read as text.")
                except Exception:
                    pass



    def get_profiles(self):

        for root, dirs, files in os.walk(self.snapshots_dir):
            dirs[:] = [d for d in dirs if os.path.abspath(os.path.join(root, d))]

            for file in (file for file in files if file.endswith(".json")):
                file_path = os.path.join(root, file)

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
        name = item["module"]
        if name in order:
            return (0, order.index(name))
        else:
            return (1, name)

    def get_value_for_lang_code(self, data, langCode):
        for ext in data.get('extension', []):
            if any(e.get('url') == 'lang' and e.get('valueCode') == langCode for e in ext.get('extension', [])):
                return next(e['valueString'] for e in ext['extension'] if e.get('url') == 'content')
        return ""

    def generate_profiles_tree(self):

        tree = {"name": "Root", "module": "no-module", "url": "no-url", "children": [], "selectable": False}

        for profile in self.profiles.values():
            path = self.build_profile_path([], profile, self.profiles)
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
            }
                        )

            self.insert_path_to_tree(tree, path)

        sorted_tree = tree

        sorted_tree['children'] = sorted(tree['children'], key=lambda item: self.custom_sort(item, self.module_order))

        return sorted_tree
