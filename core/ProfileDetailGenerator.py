import uuid
import re
import os
import json

class ProfileDetailGenerator():

    def __init__(self, profiles, mapping_type_code, blacklistedValueSets):

        self.blacklistedValueSets = blacklistedValueSets
        self.profiles = profiles
        self.mapping_type_code = mapping_type_code

    def get_value_sets_for_code_filter(self, structDef):

        value_sets = []
        elements = structDef['snapshot']["element"]
        type = structDef["type"]

        if type not in self.mapping_type_code:
            return None

        code_path = self.mapping_type_code[type]

        pattern = rf"{type}\.{code_path}\.coding:[^.]*$"

        for elem in (elem for elem in elements if re.search(pattern, elem['id'])):

            if "binding" in elem:
                value_sets.append(elem["binding"]["valueSet"])

            elif "patternCoding" or "fixed" in elem:
                return None

        if len(value_sets) > 0:
            return value_sets

        pattern = rf"{type}\.{code_path}($|\.coding$)"

        for elem in (elem for elem in elements if re.search(pattern, elem['id'])):
            if "binding" in elem:

                if elem["binding"]["valueSet"] not in self.blacklistedValueSets:
                    value_sets.append(elem["binding"]["valueSet"])

            elif "patternCoding" or "fixed" in elem:
                return None

        if len(value_sets) == 0:
            return None

        return value_sets

    def get_field_in_node(self, node, name):

        if "children" not in node:
            node["children"] = []

        children = node["children"]

        for index in range(0, len(children)):

            child = children[index]
            if child["name"] == name:
                return index

        return -1

    def insert_field_to_tree(self, tree, elements, field):

        cur_node = tree
        path = re.split(r"[.:]", field["id"])
        path = path[1:]

        if len(path) == 0:
            return

        field["name"] = path[len(path) - 1]

        for index in range(0, len(path) - 1):

            name = path[index]
            field_child_index = self.get_field_in_node(cur_node, name)

            if field_child_index != -1:
                cur_node = cur_node["children"][field_child_index]

        if "children" not in cur_node:
            cur_node["children"] = []

        cur_node["children"].append(field)

    def generate_detail_for_profile(self, profile):

        print(f"Generating profile detail for: {profile['url']}")

        code_filter = self.mapping_type_code.get(profile['structureDefinition']['type'], None)

        if not "snapshot" in profile["structureDefinition"]:
            print(f'profile with url {profile["url"]} has no snapshot - ignoring')
            # TODO - check why this happens and if this is a problem
            return None

        profile_detail = {
            "url": profile["url"],
            "display": profile["name"],
            "filters": [
                {"type": "date", "name": "date", "ui_type": "timeRestriction"},
            ],
        }

        value_set_urls = self.get_value_sets_for_code_filter(profile['structureDefinition'])

        if value_set_urls:
            profile_detail['filters'].append({
                "type": "token",
                "name": code_filter,
                "ui_type": "code",
                "valueSetUrls": self.get_value_sets_for_code_filter(profile['structureDefinition']),
            })

        elements = {}
        field_tree = {"children": []}

        source_elements = profile["structureDefinition"]["snapshot"]["element"]

        for element in source_elements:
            elements[element["id"]] = element

        for element in source_elements:

            type = "unknown"

            if "type" in element:
                type = element["type"][0]["code"]

            field = {"id": element["id"], "display": element["short"], "type": type}

            self.insert_field_to_tree(field_tree, elements, field)

        profile_detail["fields"] = field_tree["children"]

        return profile_detail
