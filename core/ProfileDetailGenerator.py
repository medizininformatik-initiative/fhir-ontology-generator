import logging
import re


class ProfileDetailGenerator():

    def __init__(self, profiles, mapping_type_code, blacklistedValueSets, fields_to_exclude, field_trees_to_exclude, reference_base_url):

        self.logger = logging.getLogger(self.__class__.__name__)
        self.blacklistedValueSets = blacklistedValueSets
        self.profiles = profiles
        self.mapping_type_code = mapping_type_code
        self.fields_to_exclude = fields_to_exclude
        self.field_trees_to_exclude = field_trees_to_exclude
        self.simple_data_types = ["instant", "time", "date", "dateTime", "decimal", "boolean", "integer", "string",
                                  "uri", "base64Binary", "code", "id", "oid", "unsignedInt", "positiveInt", "markdown",
                                  "url", "canonical", "uuid"]
        self.reference_base_url = reference_base_url

    def find_and_load_scruct_def_from_path(self, struct_def, path):

        elements = struct_def['snapshot']["element"]

        for elem in (elem for elem in elements if elem['id'] == path):

            elem_type = elem['type']

            for type_elem in (elem for elem in elem_type if re.search("Reference", elem['code'])):

                target_profile_url = next(
                    (url for url in type_elem['targetProfile'] if url.startswith(self.reference_base_url)),
                    None)

                if not target_profile_url:
                    continue

                if target_profile_url not in self.profiles:
                    for profile in self.profiles:
                        if target_profile_url.split("/")[-1] == profile.split("/")[-1]:
                            return self.profiles[profile]['structureDefinition']

                return self.profiles[target_profile_url]['structureDefinition']

        return None

    def get_value_sets_for_code_filter(self, struct_def, fhir_path):

        value_sets = []
        elements = struct_def['snapshot']["element"]
        part_match = re.search(r'\((.*?)\)', fhir_path)

        if part_match:
            struct_def = self.find_and_load_scruct_def_from_path(struct_def, part_match.group(1))

            if not struct_def:
                return None

            type = struct_def['type']
            return self.get_value_sets_for_code_filter(struct_def, f"{type}.{fhir_path.split(').')[-1]}")

        pattern = rf"{fhir_path}[^.]*$"

        for elem in (elem for elem in elements if re.search(pattern, elem['id'])):

            if "binding" in elem :

                value_set = elem["binding"]["valueSet"]

                if value_set not in self.blacklistedValueSets:
                    value_sets.append(value_set)

            elif len(value_sets) == 0 and "patternCoding" in elem or "fixed" in elem:
                return None

        if len(value_sets) > 0:
            return value_sets

        pattern = rf"{fhir_path}($|\.coding$)"

        for elem in (elem for elem in elements if re.search(pattern, elem['id'])):

            if "binding" in elem:

                value_set = elem["binding"]["valueSet"]

                if value_set not in self.blacklistedValueSets:
                    value_sets.append(value_set)

            elif "patternCoding" in elem or "fixed" in elem:
                return None

        if len(value_sets) == 0:
            return None

        return value_sets

    def get_field_in_node(self, node, id_end):

        if "children" not in node:
            node["children"] = []

        children = node["children"]

        for index in range(0, len(children)):

            child = children[index]
            if child["id"].endswith(id_end):
                return index

        return -1

    def insert_field_to_tree(self, tree, field):

        cur_node = tree
        path = re.split(r"[.:]", field["id"])
        path = path[1:]
        parent_recommended = False

        if len(path) == 0:
            return

        if field['type'] in self.simple_data_types and len(path) > 1:
            return

        for index in range(0, len(path) - 1):

            id_end = path[index]
            field_child_index = self.get_field_in_node(cur_node, id_end)

            if field_child_index != -1:
                cur_node = cur_node["children"][field_child_index]

            if parent_recommended == False and "recommended" in cur_node:
                parent_recommended = cur_node['recommended']

            if parent_recommended:
                field['recommended'] = False

        if "children" not in cur_node:
            cur_node["children"] = []

        cur_node["children"].append(field)

    def filter_element(self, element):

        attributes_true_level_one = ["mustSupport", "isModifier", "min"]

        if all(element.get(attr) is False or element.get(attr) == 0 or attr not in element
               for attr in attributes_true_level_one):
            self.logger.debug(f"Excluding: {element['id']} as not mustSupport, modifier or min > 0")
            return True

        attributes_true_level_two = ["mustSupport", "isModifier"]

        if all(element.get(attr) is False or element.get(attr) == 0 or attr not in element
               for attr in attributes_true_level_two) and len(element["id"].split(".")) > 2:
            self.logger.debug(f"Excluding: {element['id']} as not mustSupport or modifier on level > 2")
            return True

        if any(element['id'].endswith(field) or f"{field}." in element['id']for field in self.fields_to_exclude):
            self.logger.debug(f"Excluding: {element['id']} as excluded field")
            return True

        if any(f"{field}" in element['id'] for field in self.field_trees_to_exclude):
            self.logger.debug(f"Excluding: {element['id']} as part of field tree")
            return True

        if "[x]" in element['id'] and not element['id'].endswith("[x]"):
            self.logger.debug(f"Excluding: {element['id']} as sub-elements relevant")
            return True

        if element["base"]["path"].split(".")[0] in {"Resource", "DomainResource"} and not "mustSupport" in element:
            self.logger.debug(f"Excluding: {element['id']} as base is Resource or DomainResource and not must Support")
            return True

    def check_at_least_one_in_elem_and_true(self, element, attributes_to_check):

        path = element["id"].split(".")

        if len(path) > 2:
            return False

        if all(element.get(attr) is False or element.get(attr) == 0 or attr not in element
               for attr in attributes_to_check):
            return False

        return True

    def get_name_from_id(self, id):

        name = id.split(".")[-1]
        name = name.split(":")[-1]
        name = name.replace("[x]", "")

        return name

    def find_field_in_profile_fields(self, field_id, fields):

        for field in fields:

            if 'children' in field:
                self.find_field_in_profile_fields(field_id, field['children'])

            if field['id'] == field_id:
                return field

        return None

    def get_element_by_content_ref(self, content_ref, elements):

        for element in elements:
            if element['id'] == content_ref:
                return element

        return None

    def get_value_for_lang_code(self, data, langCode):
        for ext in data.get('extension', []):
            if any(e.get('url') == 'lang' and e.get('valueCode') == langCode for e in ext.get('extension', [])):
                return next(e['valueString'] for e in ext['extension'] if e.get('url') == 'content')
        return ""

    def resource_type_to_date_param(self, resource_type):

        if resource_type == 'Condition':
            return "recorded-date"

        return "date"

    def find_mii_references_by_type(self, fhir_type):

        matching_mii_references = []

        for profile in self.profiles.values():

            profile_fhir_type = profile["structureDefinition"]["type"]
            if profile_fhir_type == fhir_type:
                matching_mii_references.append(profile["url"])

        return matching_mii_references

    def get_referenced_mii_profiles(self, element, field_type):

        mii_references = []

        if field_type == 'Reference':

            target_profiles = None

            for type in element['type']:
                if "targetProfile" in type:
                    target_profiles = type['targetProfile']

            for profile in target_profiles:
                if profile.startswith('https://www.medizininformatik-initiative.de'):
                    mii_references.append(profile)

            if len(mii_references) == 0:

                for profile in target_profiles:
                    fhir_type = profile.rstrip('/').split('/')[-1]
                    mii_references.extend(self.find_mii_references_by_type(fhir_type))

        return mii_references

    def generate_detail_for_profile(self, profile):

        self.logger.info(f"Generating profile detail for: {profile['url']}")

        if not "snapshot" in profile["structureDefinition"]:
            self.logger.warning(f'profile with url {profile["url"]} has no snapshot - ignoring')
            return None

        struct_def = profile["structureDefinition"]

        date_param = self.resource_type_to_date_param(struct_def['type'])

        profile_detail = {
            "url": profile["url"],
            "display": {"original": struct_def.get("title", ""),
                        "translations": [
                            {
                                "language": "de-DE",
                                "value": self.get_value_for_lang_code(struct_def.get("_title", {}), "de-DE")
                            },
                            {
                                "language": "en-US",
                                "value": self.get_value_for_lang_code(struct_def.get("_title", {}), "en-US")
                            }
                        ]
                        },
            "filters": [
                {"type": "date", "name": date_param, "ui_type": "timeRestriction"}
            ],
        }

        profile_type = profile['structureDefinition']['type']
        code_search_param = (result := self.mapping_type_code.get(profile_type, None)) and result.get("search_param",
                                                                                                      None)
        fhir_path = (result := self.mapping_type_code.get(profile_type, None)) and result.get("fhir_path", None)
        value_set_urls = None

        if fhir_path is not None:
            value_set_urls = self.get_value_sets_for_code_filter(profile['structureDefinition'], fhir_path)

        if value_set_urls:
            profile_detail['filters'].append({
                "type": "token",
                "name": code_search_param,
                "ui_type": "code",
                "valueSetUrls": value_set_urls,
            })

        field_tree = {"children": []}
        source_elements = profile["structureDefinition"]["snapshot"]["element"]

        for element in source_elements:

            field_id = element["id"]

            if self.filter_element(element):
                continue

            if 'contentReference' in element:
                content_reference_split = element['contentReference'].split("#")
                if len(content_reference_split) > 1:
                    content_reference = content_reference_split[1]
                else:
                    content_reference = content_reference_split[0]

                element = self.get_element_by_content_ref(content_reference, source_elements)

            field_type = None

            if "type" in element:
                for type in element["type"]:

                    field_type = type["code"]

                    if type["code"] == "Reference":
                        break

            else:
                self.logger.warning(f"Element without type: {element} - discarding")
                continue

            is_recommended_field = self.check_at_least_one_in_elem_and_true(element, ["min"])
            is_required_field = self.check_at_least_one_in_elem_and_true(element, ["isModifier"])

            name = self.get_name_from_id(element["id"])

            field = {"id": field_id,
                     "display": {"original": name,
                                 "translations": [
                                     {
                                         "language": "de-DE",
                                         "value": self.get_value_for_lang_code(element.get('_short', {}), "de-DE")
                                     },
                                     {
                                         "language": "en-US",
                                         "value": self.get_value_for_lang_code(element.get('_short', {}), "en-US")
                                     }
                                 ],
                                 },
                     "description": {"original": element.get("definition", ""),
                                     "translations": [
                                         {
                                             "language": "de-DE",
                                             "value": self.get_value_for_lang_code(element.get('_definition', {}),
                                                                                   "de-DE")
                                         },
                                         {
                                             "language": "en-US",
                                             "value": self.get_value_for_lang_code(element.get('_definition', {}),
                                                                                   "en-US")
                                         }
                                     ],
                                     },
                     "referencedProfiles": self.get_referenced_mii_profiles(element, field_type),
                     "type": field_type,
                     "recommended": is_recommended_field,
                     "required": is_required_field
                     }

            if field_type == "Reference" and len(self.get_referenced_mii_profiles(element, field_type)) == 0:
                self.logger.warning(f"Discarding field: {element['id']} - No mii profiles that match referenced profiles, parent profile is {profile['url']}")
                continue


            self.insert_field_to_tree(field_tree, field)

        profile_detail["fields"] = field_tree["children"]

        return profile_detail
