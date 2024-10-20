import re

class ProfileDetailGenerator():

    def __init__(self, profiles, mapping_type_code, blacklistedValueSets, fields_to_exclude):

        self.blacklistedValueSets = blacklistedValueSets
        self.profiles = profiles
        self.mapping_type_code = mapping_type_code
        self.fields_to_exclude = fields_to_exclude
        self.simple_data_types = ["instant", "time", "date", "dateTime", "decimal", "boolean", "integer", "string", "uri", "base64Binary", "code", "id", "oid", "unsignedInt", "positiveInt", "markdown", "url", "canonical", "uuid"]

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

            elif len(value_sets) == 0 and "patternCoding" in elem or "fixed" in elem:
                return None

        if len(value_sets) > 0:
            return value_sets

        pattern = rf"{type}\.{code_path}($|\.coding$)"

        for elem in (elem for elem in elements if re.search(pattern, elem['id'])):

            if "binding" in elem:

                if elem["binding"]["valueSet"] not in self.blacklistedValueSets:
                    value_sets.append(elem["binding"]["valueSet"])

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

        if len(path) == 0:
            return

        if field['type'] in self.simple_data_types and len(path) > 1:
            return

        for index in range(0, len(path) - 1):

            id_end = path[index]
            field_child_index = self.get_field_in_node(cur_node, id_end)

            if field_child_index != -1:
                cur_node = cur_node["children"][field_child_index]

        if "children" not in cur_node:
            cur_node["children"] = []

        cur_node["children"].append(field)

    def filter_element(self, element):

        if "mustSupport" not in element or element['mustSupport'] is False:
            return True

        if any(element['id'].endswith(field) or f"{field}." in element['id'] for field in self.fields_to_exclude):
            return True

        if "[x]" in element['id'] and not element['id'].endswith("[x]"):
            return True

        if element['id'].endswith(".extension"):
            return True

    def get_name_from_id(self, id):

        name = id.split(".")[-1]
        name = name.split(":")[-1]
        name = name.replace("[x]", "")

        return name

    def find_field_in_profile_fields(self,field_id, fields):

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

    def generate_detail_for_profile(self, profile):

        print(f"Generating profile detail for: {profile['url']}")

        code_filter = self.mapping_type_code.get(profile['structureDefinition']['type'], None)

        if not "snapshot" in profile["structureDefinition"]:
            print(f'profile with url {profile["url"]} has no snapshot - ignoring')
            # TODO - check why this happens and if this is a problem
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
                {"type": "date", "name": date_param , "ui_type": "timeRestriction"}
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

            if "type" in element:
                field_type = element["type"][0]["code"]
            else:
                print(f"Element without type: {element}")
                continue

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
                                             "value": self.get_value_for_lang_code(element.get('_definition', {}), "de-DE")
                                         },
                                         {
                                             "language": "en-US",
                                             "value": self.get_value_for_lang_code(element.get('_definition', {}), "en-US")
                                         }
                                     ],
                                     },
                     "type": field_type
                     }

            self.insert_field_to_tree(field_tree, field)

        profile_detail["fields"] = field_tree["children"]

        return profile_detail
