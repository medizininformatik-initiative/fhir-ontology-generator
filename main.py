import os
import requests
import re
from UiDataModel import *
from mapper import LOGICAL_MODEL_TO_PROFILE

ONTOLOGY_SERVER_ADDRESS = "https://ontoserver.imi.uni-luebeck.de/fhir/"

def to_upper_camel_case(string):
    result = ""
    for substring in string.split(" "):
        result += substring.capitalize()
    return result

def resolve_terminology_entry_profile(terminology_entry):
    name = LOGICAL_MODEL_TO_PROFILE.get(to_upper_camel_case(terminology_entry.display)) \
        if to_upper_camel_case(terminology_entry.display) in LOGICAL_MODEL_TO_PROFILE else to_upper_camel_case(terminology_entry.display)
    found = False
    for filename in os.listdir("geccoDataset"):
        if name in filename and filename.startswith("Profile"):
            found = True
            with open("geccoDataset/" + filename) as profile_file:
                profile_data = json.load(profile_file)
                if profile_data["type"] == "Condition":
                    for element in profile_data["differential"]["element"]:
                        if element["path"] == "Condition.code.coding":
                            if "binding" in element:
                                value_set = element["binding"]["valueSet"]
                                terminology_entry.children += (
                                    get_termcodes_from_value_set(value_set))
                elif profile_data["type"] == "Observation":
                    for element in profile_data["differential"]["element"]:
                        if element["path"] == "Observation.value[x]":
                            if "type" in element:
                                for element_type in element["type"]:
                                    if element_type["code"] == "CodeableConcept":
                                        if "binding" in element:
                                            print(element["binding"]["valueSet"])
                                            value_set = element["binding"]["valueSet"]
                                            value_definition = ValueDefinition("concept")
                                            value_definition.selectableConcepts += get_termcodes_from_value_set(value_set)
                                            terminology_entry.valueDefinitions.append(value_definition)
    if not found:
        print(to_upper_camel_case(terminology_entry.display))


# TODO: We only want to use a single coding system. The different coding systems need to be prioratized
# We do not want to expand is-A relations of snomed or we need a tree structure , but we cant gain the information
# needed to create a tree structure
def get_termcodes_from_value_set(value_set):
    icd10_result = []
    snomed_result = []
    result = []
    response = requests.get(f"{ONTOLOGY_SERVER_ADDRESS}ValueSet/$expand?url={value_set}&includeDesignations=true")
    if response.status_code == 200:
        value_set_data = response.json()
        for contains in value_set_data["expansion"]["contains"]:
            system = contains["system"]
            code = contains["code"]
            display = contains["display"]
            term_code = TermCode(system, code, display)
            if system == "http://fhir.de/CodeSystem/dimdi/icd-10-gm":
                icd10_result.append(term_code)
            elif system == "http://snomed.info/sct":
                if "designation" in contains:
                    for designation in contains["designation"]:
                        if designation["language"] == "de-DE":
                            if "use" in designation:
                                term_code.code = designation["use"]["code"]
                            term_code.display = designation["value"]
                snomed_result.append(term_code)
            else:
                result.append(term_code)
    if icd10_result:
        return to_icd_tree(icd10_result)
    elif snomed_result:
        return snomed_result
    else:
        return result


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

    for subcategory_four_digit_entry in sorted(subcategories_four_digit):
        parent_found = False
        for subcategory_three_digit_entry in subcategories_three_digit:
            if subcategory_three_digit_entry == subcategory_four_digit_entry.termCode.code[:-1]:
                subcategory_three_digit_entry.children.append(subcategory_four_digit_entry)
                parent_found = True
        if not parent_found:
            result.append(subcategory_four_digit_entry)

    for subcategory_three_digit_entry in sorted(subcategories_three_digit):
        parent_found = False
        for category_entry in categories:
            if category_entry == subcategory_three_digit_entry.termCode.code[:-2]:
                subcategory_three_digit_entry.children.append(subcategory_three_digit_entry)
                parent_found = True
        if not parent_found:
            result.append(subcategory_three_digit_entry)

    for category_entry in sorted(categories):
        parent_found = False
        for group_entry in groups:
            if int(group_entry.termCode.code[-2:]) >= int(category_entry.termCode.code[1:]) >= int(
                    group_entry.termCode.code[1:2]) and \
                    category_entry.termCode.code[0] == group_entry.termCode.code[0]:
                group_entry.children.append(category_entry)
                parent_found = True
        if not parent_found:
            result.append(category_entry)

    result += sorted(groups)

    return result


def get_allowed_values():
    pass


def add_terminology_entry_to_category(element, categories, terminology_type):
    for category_entry in categories:
        if category_entry.path in element["base"]["path"]:
            term_codes = []
            if "code" in element:
                for code in element["code"]:
                    term_codes.append(TermCode(code["system"], code["code"], code["display"],
                                               code["version"] if "version" in code else None))
            term_code = term_codes[0] if term_codes else None
            for term_code_entry in term_codes:
                if term_code_entry.system == "http://fhir.de/CodeSystem/dimdi/icd-10-gm":
                    term_code == term_code_entry
                    break
            terminology_entry = TerminologyEntry(term_code, terminology_type)
            terminology_entry.display = element["short"]
            resolve_terminology_entry_profile(terminology_entry)
            for extension in element["_short"]["extension"]:
                next_value_is_german_display_content = False
                for nested_extension in extension["extension"]:
                    if nested_extension["url"] == "lang":
                        next_value_is_german_display_content = nested_extension["valueCode"] == "de-DE"
                        continue
                    elif next_value_is_german_display_content:
                        terminology_entry.display = nested_extension["valueMarkdown"]
            category_entry.children.append(terminology_entry)


def get_categories():
    with open("geccoDataset/StructureDefinition-LogicalModel-GECCO.json", encoding="utf-8") as json_file:
        categories = []
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
                                categories.append(CategoryEntry(str(uuid.uuid4()),
                                                                nested_extension["valueMarkdown"],
                                                                element["base"]["path"]))
            except KeyError:
                continue
        return categories


def create_category_terminology_entry(category_entry):
    result = TerminologyEntry(None, "Category", category_entry.entryId)
    result.display = category_entry.display
    result.path = category_entry.path
    return result


def create_terminology_definition_for(categories):
    category_terminology_entries = []
    for category_entry in categories:
        category_terminology_entries.append(create_category_terminology_entry(category_entry))
    with open("geccoDataset/StructureDefinition-LogicalModel-GECCO.json", encoding="utf-8") as json_file:
        data = json.load(json_file)
        for element in data["snapshot"]["element"]:
            if "type" in element:
                if element["type"][0]["code"] == "BackboneElement":
                    continue
                elif element["type"][0]["code"] == "CodeableConcept":
                    add_terminology_entry_to_category(element, category_terminology_entries, "CodeableConcept")
                elif element["type"][0]["code"] == "Quantity":
                    add_terminology_entry_to_category(element, category_terminology_entries, "Quantity")
                elif element["type"][0]["code"] == "date":
                    add_terminology_entry_to_category(element, category_terminology_entries, "date")
                else:
                    raise Exception(f"Unknown element {element['type'][0]['code']}")
    return category_terminology_entries


if __name__ == '__main__':
    for category in create_terminology_definition_for(get_categories()):
        f = open("result/" + category.display.replace("/", "") + ".json", 'w')
        f.write(category.to_json())
