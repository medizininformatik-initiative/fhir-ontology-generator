import os

from FHIRProfileConfiguration import *
from helper import to_upper_camel_case
from model.Exceptions import UnknownHandlingException
from model.UiDataModel import *

MAIN_CATEGORIES = ["Einwilligung", "Bioproben"]


def is_logical_bundle_or_extension(json_data: dict) -> bool:
    """
    evaluates if the FHIR json data is a logical model, bundle or extension
    :param json_data: FHIR json data
    :return: true if the json data is a logical model, bundle or extension else false
    """
    return is_logical_or_bundle(json_data) or (json_data.get("type") == "Extension")


def is_logical_or_bundle(json_data: dict) -> bool:
    """
    evaluates if the FHIR json data is a logical model or bundle
    :param json_data: FHIR json data
    :return: true if the json data is a logical model or bundle else false
    """
    return (json_data.get("kind") == "logical") or (json_data.get("type") == "Bundle")


def profile_is_of_interest(json_data: dict, module_name: str) -> bool:
    """
    evaluates if the FHIR json data is of interest. The data is not of interest if it is a logical model, bundle or
    extension or is part of the IGNORE_LIST
    :param json_data: FHIR json data
    :param module_name: name of the module
    :return: true if the json data is not a logical model, bundle or extension and module_name is not part of the
    IGNORE_LIST else false
    """
    return (not is_logical_bundle_or_extension(json_data)) and (module_name not in IGNORE_LIST)


def get_gecco_categories():
    # categories are BackboneElements within the LogicalModel
    with open(f"{GECCO_DATA_SET}/StructureDefinition-LogicalModel-GECCO.json", encoding="utf-8") as json_file:
        categories = []
        data = json.load(json_file)
        for element in data["differential"]["element"]:
            try:
                # ignore Gecco base element:
                if element["base"]["path"] == "forschungsdatensatz_gecco.gecco":
                    continue
                if element["type"][0]["code"] == "BackboneElement":
                    categories += get_categories(element)
            except KeyError:
                pass
        return categories


def get_categories(element):
    result = []
    for extension in element["_short"]["extension"]:
        for nested_extension in extension["extension"]:
            if "valueMarkdown" in nested_extension:
                result.append(
                    CategoryEntry(str(uuid.uuid4()), nested_extension["valueMarkdown"], element["base"]["path"]))
    return result


def create_terminology_definition_for(categories):
    category_terminology_entries = []
    for category_entry in categories:
        category_terminology_entries.append(create_category_terminology_entry(category_entry))
    with open(f"{GECCO_DATA_SET}/StructureDefinition-LogicalModel-GECCO.json", encoding="utf-8") as json_file:
        data = json.load(json_file)
        for element in data["differential"]["element"]:
            if "type" in element:
                if element["type"][0]["code"] == "BackboneElement":
                    continue
                elif element["type"][0]["code"] in ["CodeableConcept", "Quantity", "date"]:
                    add_terminology_entry_to_category(element, category_terminology_entries, element["type"][0]["code"])
                else:
                    raise Exception(f"Unknown element {element['type'][0]['code']}")
    for category_entry in category_terminology_entries:
        category_entry.children = sorted(category_entry.children)
    print(category_terminology_entries)
    return category_terminology_entries


def create_category_terminology_entry(category_entry):
    term_code = [TermCode("mii.abide", category_entry.display, category_entry.display)]
    result = TermEntry(term_code, "Category", leaf=False, selectable=False)
    result.path = category_entry.path
    return result


# element from Logical Model
def add_terminology_entry_to_category(element, categories, terminology_type):
    for category_entry in categories:
        # same path -> sub element of that category
        if category_entry.path in element["base"]["path"]:
            terminology_entry = TermEntry(get_term_codes(element), terminology_type)
            # We use the english display to resolve after we switch to german.
            terminology_entry.display = element["short"]
            if terminology_entry.display in IGNORE_LIST:
                continue
            resolve_terminology_entry_profile(terminology_entry, element)
            if terminology_entry.display == category_entry.display:
                # Resolves issue like : -- Symptoms                 --Symptoms
                #                           -- Symptoms     --->      -- Coughing
                #                              -- Coughing
                category_entry.children += terminology_entry.children
            else:
                category_entry.children.append(terminology_entry)
            break


def get_term_codes(element):
    # Do not use code once using an Ontoserver to resolve the children.
    term_codes = []
    if "code" in element:
        for code in element["code"]:
            term_codes.append(TermCode(code["system"], code["code"], code["display"],
                                       code["version"] if "version" in code else None))
    if not term_codes:
        term_codes.append(TermCode("mii.abide", element["short"], element["short"]))
    return term_codes


def resolve_terminology_entry_profile(terminology_entry, element=None, data_set=GECCO_DATA_SET):
    name = to_upper_camel_case(terminology_entry.display)
    for filename in os.listdir("%s" % data_set):
        if name in filename and "snapshot" in filename:
            with open(data_set + "/" + filename, encoding="UTF-8") as profile_file:
                profile_data = json.load(profile_file)
                if is_logical_or_bundle(profile_data):
                    continue
                else:
                    raise UnknownHandlingException(filename)
    if element:
        terminology_entry.display = get_german_display(element) if get_german_display(element) else element["short"]


def get_german_display(element):
    for extension in element["_short"]["extension"]:
        next_value_is_german_display_content = False
        for nested_extension in extension["extension"]:
            if nested_extension["url"] == "lang":
                next_value_is_german_display_content = nested_extension["valueCode"] == "de-DE"
                continue
            elif next_value_is_german_display_content:
                return nested_extension["valueMarkdown"]
    return None


def get_german_display_from_designation(contains):
    if "designation" in contains:
        for designation in contains["designation"]:
            if "language" in designation and designation["language"] == "de-DE":
                return designation["value"]
    return None


def do_nothing(_profile_data, _terminology_entry, _element):
    pass
