import json
import os
import requests
import re

ontology_server_address = "https://ontoserver.imi.uni-luebeck.de/fhir/"


class ComplexEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, TerminologyEntry):
            return obj.__dict__  # <-----
        return json.JSONEncoder.default(self, obj)


class CategoryEntry:
    def __init__(self, category_id, display, german_display, path):
        self.category_id = category_id
        self.display = display
        self.german_display = german_display
        self.path = path
        self.children = []
        self.shortDisplay = german_display[0]

    def __str__(self):
        output = ""
        for _, var in vars(self).items():
            output += " " + str(var)
        return output

    def to_json(self):
        return json.dumps(self, default=lambda o: self.del_none(
            self.del_keys(o.__dict__, ["path"])),
                          sort_keys=True, indent=4)

    @staticmethod
    def del_keys(d, keys):
        for k in keys:
            d.pop(k, None)
        return d

    def del_none(self, d):
        """
        Delete keys with the value ``None`` in a dictionary, recursively.

        This alters the input so you may wish to ``copy`` the dict first.
        """
        for key, value in list(d.items()):
            if value is None:
                del d[key]
            elif isinstance(value, dict):
                self.del_none(value)
        return d  # For convenience

    def to_java_init(self):
        return f"new CategoryEntry(\"{self.category_id}\", \"{self.german_display}\"),"


class TermCode:
    def __init__(self, system, code, display, version=None):
        self.system = system
        self.code = code
        self.version = version
        self.display = display

    def __lt__(self, other):
        self.display < other.display

    def __repr__(self):
        return self.display + " " + self.code + " " + self.system


class ValueDefinition:
    def __init__(self, value_type):
        self.valueType = value_type
        self.selectableConcepts = []


class TerminologyEntry:
    def __init__(self, term_code, terminology_type):
        self.termCode = term_code
        self.terminologyType = terminology_type
        self.children = []
        # This is the preferred display this might be the same as self.termCode.display but doesnt have to.
        # This is necessary for termCodes that do not have a german translation. Coding it inside the termCode would
        # result in a contradiction
        self.preferredDisplay = self.termCode.display
        self.leaf = False
        self.selectable: False
        self.timeRestrictionAllowed: False
        self.valueDefinition = None

    def __lt__(self, other):
        self.germanDisplay < self.germanDisplay

    def __repr__(self):
        return self.termCode.code

    def del_none(self, d):
        """
        Delete keys with the value ``None`` in a dictionary, recursively.

        This alters the input so you may wish to ``copy`` the dict first.
        """
        for key, value in list(d.items()):
            if value is None:
                del d[key]
            elif isinstance(value, dict):
                self.del_none(value)
        return d  # For convenience

    def to_json(self):
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4)


def to_upper_camel_case(string):
    result = ""
    for substring in string.split(" "):
        result += substring.capitalize()
    return result


def resolve_terminology_entry_profile(terminology_entry):
    for filename in os.listdir("geccoDataset"):
        if to_upper_camel_case(terminology_entry.display) in filename:
            with open("geccoDataset/" + filename) as profile_file:
                profile_data = json.load(profile_file)
                if profile_data["type"] == "Condition":
                    for element in profile_data["differential"]["element"]:
                        if element["path"] == "Condition.code.coding":
                            value_set = element["binding"]["valueSet"]
                            terminology_entry.children += (
                                get_termcodes_from_value_set(value_set))
                elif profile_data["type"] == "Observable":
                    pass


# This gets the Terminology Tree
def get_termcodes_from_value_set(value_set):
    result = []
    response = requests.get(f"{ontology_server_address}ValueSet/$expand?url={value_set}")
    if response.status_code == 200:
        value_set_data = response.json()
        for contains in value_set_data["expansion"]["contains"]:
            if contains["system"] != "http://fhir.de/CodeSystem/dimdi/icd-10-gm":
                continue
            system = contains["system"]
            code = contains["code"]
            display = contains["display"]
            result.append(TermCode(system, code, display))
    return to_icd_tree(result)


# TODO: REFACTOR OR DETAILED DESCRIPTION!
def to_icd_tree(termcodes):
    groups = []
    categories = []
    subcategories_three_digit = []
    subcategories_four_digit = []

    for termcode in termcodes:
        if re.match("[A-Z][0-9][0-9]-[A-Z][0-9][0-9]$", termcode.code):
            groups.append(TerminologyEntry(termcode, "CodeableConcept"))
        elif re.match("[A-Z][0-9][0-9]$", termcode.code):
            categories.append(TerminologyEntry(termcode, "CodeableConcept"))
        elif re.match("[A-Z][0-9][0-9]\.[0-9]$", termcode.code):
            subcategories_three_digit.append(TerminologyEntry(termcode, "CodeableConcept"))
        elif re.match("[A-Z][0-9][0-9]\.[0-9][0-9]$", termcode.code):
            subcategories_four_digit.append(TerminologyEntry(termcode, "CodeableConcept"))

    result = []

    for subcategory_four_digit_entry in subcategories_four_digit:
        parent_found = False
        for subcategory_three_digit_entry in subcategories_three_digit:
            if subcategory_three_digit_entry == subcategory_four_digit_entry.termCode.code[:-1]:
                subcategory_three_digit_entry.children.append(subcategory_four_digit_entry)
                parent_found = True
        if not parent_found:
            result.append(subcategory_four_digit_entry)

    for subcategory_three_digit_entry in subcategories_three_digit:
        parent_found = False
        for category_entry in categories:
            if category_entry == subcategory_three_digit_entry.termCode.code[:-2]:
                subcategory_three_digit_entry.children.append(subcategory_three_digit_entry)
                parent_found = True
        if not parent_found:
            result.append(subcategory_three_digit_entry)

    for category_entry in categories:
        parent_found = False
        for group_entry in groups:
            if int(group_entry.termCode.code[-2:]) >= int(category_entry.termCode.code[1:]) >= int(
                    group_entry.termCode.code[1:2]) and \
                    category_entry.termCode.code[0] == group_entry.termCode.code[0]:
                group_entry.children.append(category_entry)
                parent_found = True
        if not parent_found:
            result.append(category_entry)

    result += groups

    return result


def get_allowed_values():
    pass


def add_terminology_entry_to_category(element, categories, terminology_type):
    for category_path in categories:
        if category_path in element["base"]["path"]:
            equivalent_concept_codes = []
            for code in element["code"]:
                equivalent_concept_codes.append(
                    TermCode(code["system"], code["code"], code["display"],
                             code["version"] if "version" in code else None))
            terminology_entry = TerminologyEntry(equivalent_concept_codes, terminology_type)
            terminology_entry.display = element["short"]
            resolve_terminology_entry_profile(terminology_entry)
            for extension in element["_short"]["extension"]:
                next_value_is_german_display_content = False
                for nested_extension in extension["extension"]:
                    if nested_extension["url"] == "lang":
                        next_value_is_german_display_content = nested_extension["valueCode"] == "de-DE"
                        continue
                    elif next_value_is_german_display_content:
                        terminology_entry.germanDisplay = nested_extension["valueMarkdown"]
            categories[category_path].terminologyEntries.append(terminology_entry)


def get_categories():
    with open("geccoDataset/StructureDefinition-LogicalModel-GECCO.json", encoding="utf-8") as json_file:
        categories = dict()
        data = json.load(json_file)
        for element in data["snapshot"]["element"]:
            try:
                # ignore Gecco base element:
                if element["base"]["path"] == "forschungsdatensatz_gecco.gecco":
                    continue
                if element["type"][0]["code"] == "BackboneElement":
                    for extension in element["_short"]["extension"]:
                        for nested_extension in extension["extension"]:
                            if "valueMarkdown" in nested_extension:
                                categories[element["base"]["path"]] = (CategoryEntry(element["id"], element["short"],
                                                                                     nested_extension["valueMarkdown"],
                                                                                     element["base"]["path"]))
                elif element["type"][0]["code"] == "CodeableConcept":
                    add_terminology_entry_to_category(element, categories, "CodeableConcept")
                elif element["type"][0]["code"] == "Quantity":
                    add_terminology_entry_to_category(element, categories, "CodeableConcept")
                elif element["type"][0]["code"] == "date":
                    add_terminology_entry_to_category(element, categories, "CodeableConcept")
                else:
                    print(element["type"][0]["code"])
            except KeyError:
                continue
        return categories


if __name__ == '__main__':
    for category in get_categories().values():
        f = open("result/" + category.german_display.replace("/", "") + ".json", 'w')
        f.write(category.to_json())
