import json

from TerminologService.ValueSetResolver import get_termcodes_from_onto_server
from model.UiDataModel import TermCode

ID_PATH = ["id"]
URL_PATH = ["url"]
NAME_PATH = ["name"]
ELEMENT_PATH = ["differential", "element"]
SHORT_PATH = ["short"]
DEFINITION_PATH = ["definition"]
CODE_PATH = ["patternCoding", "code"]
UNIT_CODE_PATH = ["fixedCode"]
VS_PATH = ["binding", "valueSet"]
WINDOWS_RESERVED_CHARACTERS = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']

QUANTITY_OBSERVATION_TEMPLATE = 'FDPG_Quantity_Observation_Template.json'
CONCEPT_OBSERVATION_TEMPLATE = 'FDPG_Concept_AnswerList_Observation_Template.json'
DEFAULT_OBSERVATION_PROFILE = 'FDPG_Concept_Missing_AnswerList_Observation_Template.json'


def open_template(template_name) -> dict:
    """
    open template from file
    :param template_name: file name of the template
    :return: the template as json
    """
    with open(f"../resources/{template_name}", 'r', encoding="utf-8") as f:
        data = json.load(f)
    return data


def get_element_by_id(template, element_id) -> dict:
    """
    get element by id
    :param template: template to search in
    :param element_id: the id of the element
    :return: the element with the given id if it exists, otherwise None
    """
    for element in get_by_path(template, ELEMENT_PATH):
        if element.get("id") == element_id:
            return element
    return {}


def get_by_path(data: dict, keys: list):
    """
    walks the data and returns the value at the given path
    :param data: the data to walk
    :param keys: the keys
    :return: element at the given path
    """
    if keys and keys[0] not in data:
        return None
    return get_by_path(data[keys[0]], keys[1:]) if keys else data


def set_if_exists(dictionary, attribute_path: list, value):
    """
    sets the value at the given path if the path exists
    :param dictionary: the dictionary to set the value in
    :param attribute_path: the path to set the value at
    :param value: the value to set
    """
    current = dictionary
    for key in attribute_path[:-1]:
        if key not in current:
            return
        current = current[key]
    current[attribute_path[-1]] = value


def set_id(template: dict, element_id: str):
    """
    sets the id of the template
    :param template: the template
    :param element_id: the id to set
    """
    set_if_exists(template, ID_PATH, element_id)


def set_name(template: dict, name: str):
    """

    :param template:
    :param name:
    :return:
    """
    set_if_exists(template, NAME_PATH, name)
    template_url = get_by_path(template, URL_PATH)
    set_if_exists(template, URL_PATH, template_url + remove_whitespace_replace_slash(name))
    element = get_element_by_id(template, "Observation.code")
    set_if_exists(element, SHORT_PATH, name)
    set_if_exists(element, DEFINITION_PATH, name)


def set_loinc_code(template, code):
    element = get_element_by_id(template, "Observation.code.coding:loinc")
    set_if_exists(element, CODE_PATH, code)


def set_unit_code(template, unit_code):
    element = get_element_by_id(template, "Observation.valueQuantity.code")
    set_if_exists(element, UNIT_CODE_PATH, unit_code)


def save_template(template, file_name):
    with open(f"../resources/differential/gecco/package/{file_name}.json", "w") as json_file:
        json.dump(template, json_file, indent=4)


def remove_whitespace_replace_slash(file_name):
    return file_name.replace(" ", "").replace("/", "-").replace("<=", "ge").replace(",", "_")


def remove_reserved_characters(file_name):
    return file_name.translate({ord(c): None for c in WINDOWS_RESERVED_CHARACTERS})


def load_logical_model():
    """
    load logical model from file
    :return:
    """
    with open("../resources/de.gecco#1.0.5/package/StructureDefinition-LogicalModel-GECCO.json",
              'r', encoding="utf-8") as f:
        return json.load(f)


def get_unit_from_logical_model(term_code):
    """
    extract unit from logical model based on the term code
    :param term_code: term code to search for
    :return: list of valid units for the given term code
    """
    logical_model = load_logical_model()
    for element in get_by_path(logical_model, ELEMENT_PATH):
        for code in element.get("code", []):
            if TermCode(code.get("system"), code.get("code"), code.get("display")) == term_code:
                units = [extension.get("valueCodeableConcept").get("coding")[0].get("code") for extension in
                         element.get("extension", []) if extension.get(
                        "url") == "http://hl7.org/fhir/StructureDefinition/elementdefinition-allowedUnits"]
                return [TermCode("http://unitsofmeasure.org", unit, unit) for unit in units]
    return []


def load_profile_to_query_meta_data():
    """
    load profile to query meta data from file
    :return:
    """
    with open("../resources/profile_to_query_meta_data_resolver_mapping.json", 'r', encoding="utf-8") as f:
        return json.load(f)


def write_profile_to_query_meta_data(profile_to_query_meta_data):
    """
    write profile to query meta data to file
    :return:
    """
    with open("../resources/profile_to_query_meta_data_resolver_mapping.json", 'w', encoding="utf-8") as f:
        json.dump(profile_to_query_meta_data, f, indent=4)


if __name__ == "__main__":
    observation_codes = get_termcodes_from_onto_server(
        "https://www.netzwerk-universitaetsmedizin.de/fhir/ValueSet/lab-tests-gecco")
    observation_codes.append(TermCode("http://loinc.org", "8302-2", "Body height"))
    observation_codes.append(TermCode("http://loinc.org", "29463-7", "Body weight"))
    query_data_mapping = load_profile_to_query_meta_data()
    for observation_code in observation_codes:
        unit = get_unit_from_logical_model(observation_code)
        if unit:
            quantity_template = open_template(QUANTITY_OBSERVATION_TEMPLATE)
            set_id(quantity_template, remove_whitespace_replace_slash(observation_code.display))
            set_name(quantity_template, observation_code.display)
            set_loinc_code(quantity_template, observation_code.code)
            set_unit_code(quantity_template, unit[0].code)
            save_template(quantity_template, remove_whitespace_replace_slash(observation_code.display))
            query_data_mapping[observation_code.display] = ["QuantityObservation"]
        else:
            presence_template = open_template(DEFAULT_OBSERVATION_PROFILE)
            set_id(presence_template, remove_whitespace_replace_slash(observation_code.display))
            set_name(presence_template, observation_code.display)
            set_loinc_code(presence_template, observation_code.code)
            save_template(presence_template, remove_whitespace_replace_slash(observation_code.display))
            query_data_mapping[observation_code.display] = ["ConceptObservation"]
    write_profile_to_query_meta_data(query_data_mapping)
