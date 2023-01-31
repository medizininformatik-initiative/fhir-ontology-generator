import json
import os.path
import re

from lxml import etree

from profile_information_extractor import get_loinc_code_leafs

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
    with open(f"../../shared_resources/{template_name}", 'r', encoding="utf-8") as f:
        data = json.load(f)
    return data


def get_element_by_id(template, element_id):
    for element in get_by_path(template, ELEMENT_PATH):
        if element.get("id") == element_id:
            return element
    return None


def get_by_path(data, keys: list):
    if keys and keys[0] not in data:
        return None
    return get_by_path(data[keys[0]], keys[1:]) if keys else data


def set_if_exists(dictionary, attribute_path: list, value):
    current = dictionary
    for key in attribute_path[:-1]:
        if key not in current:
            return
        current = current[key]
    current[attribute_path[-1]] = value


def set_id(template, element_id):
    set_if_exists(template, ID_PATH, element_id)


def set_name(template, name):
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
    with open(f"../resources/fdpg_differential/Laboruntersuchung/package/{file_name}.json", "w") as json_file:
        json.dump(template, json_file, indent=4)


def remove_whitespace_replace_slash(file_name):
    return file_name.replace(" ", "").replace("/", "-").replace("<=", "ge").replace(",", "_")


def remove_reserved_characters(file_name):
    return file_name.translate({ord(c): None for c in WINDOWS_RESERVED_CHARACTERS})


def remove_unit_dimension(file_name):
    return re.sub(r"[.*?]", "", file_name)


def replace_173sq(file_name):
    if "173sqMpredicted" in file_name:
        print("Replacing 1.73sqM.predicted[VolumeRate-Area]inSerum with ''")
    return file_name.replace("1.73sqM.predicted[VolumeRate-Area]inSerum", "")


def replace_extrinsiccoagulationsystemactivated(file_name):
    return file_name.replace(".extrinsiccoagulationsystemactivated", "")


def fix_file_name(file_name: str):
    file_name_without_whit_space = remove_whitespace_replace_slash(file_name)
    file_name_without_reserved = remove_reserved_characters(file_name_without_whit_space)
    file_name_without_173sq = replace_173sq(file_name_without_reserved)
    file_name_shorted = replace_extrinsiccoagulationsystemactivated(file_name_without_173sq)
    if len(file_name_without_173sq) > 100:
        print(f"File name {file_name_shorted} is too long, removing unit dimension")
        return remove_unit_dimension(file_name_shorted)
    return file_name_shorted


def set_value_set_url(template, answer_list_vs):
    element = get_element_by_id(template, "Observation.value[x]:valueCodeableConcept")
    set_if_exists(element, VS_PATH, answer_list_vs)


def create_observation_template(profile: dict, element_id, name) -> dict:
    """
    Based on the profile the profile template is selected and content filled
    :param profile: the profile to create the template for
    :param element_id: the id of the element
    :param name: the name of the resulting profile
    :return: fhir profile based on the template
    """
    if profile.units:
        template = open_template(QUANTITY_OBSERVATION_TEMPLATE)
        set_unit_code(template, profile.units[0])
    elif profile.answer_list_vs:
        template = open_template(CONCEPT_OBSERVATION_TEMPLATE)
        set_value_set_url(template, profile.answer_list_vs)
    else:
        template = open_template(DEFAULT_OBSERVATION_PROFILE)
    set_id(template, element_id)
    set_name(template, name)
    system, code = profile.code
    set_loinc_code(template, code)
    return template


def delete_snapshots():
    for file in os.listdir("../resources/fdpg_differential/Laboruntersuchung/package"):
        if file.endswith("-snapshot.json"):
            os.remove(os.path.join("../resources/fdpg_differential/Laboruntersuchung/package", file))


def generate_observation_profile_for_top300_loinc_codes():
    top_loinc_tree = etree.parse("../resources/additional_resources/Top300Loinc.xml")
    profiles = get_loinc_code_leafs("11ccdc84-a237-49a5-860a-b0f65068c023", top_loinc_tree)
    for profile in profiles:
        element_id = profile.id
        name = profile.name_de if profile.name_de else profile.name_en
        template = create_observation_template(profile, element_id, name)
        save_template(template, f"FDPG_Observation_{fix_file_name(name)}")


if __name__ == '__main__':
    generate_observation_profile_for_top300_loinc_codes()
