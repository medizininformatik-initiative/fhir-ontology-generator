import uuid

import requests as requests
from lxml import etree


class ProfileInformation:
    def __init__(self, name_en, name_de, code, units):
        self.id = str(uuid.uuid4())
        self.name_en = name_en
        self.name_de = name_de
        self.code = code
        self.units = units
        self.answer_list_vs = None
        if not units:
            self.answer_list_vs = get_answer_list(self.code)

    def __repr__(self):
        return f"Profile : {self.name_de} Loinc Code: {self.code} with unit {self.units}"


def get_code_from_slots(element):
    coding_system = ""
    code = ""
    for slot in element.xpath("xmlns:slots/xmlns:slot",
                              namespaces={'xmlns': "http://schema.samply.de/mdr/common"}):
        next_is_coding_system = False
        next_is_code = False
        for child in slot:
            if (child.tag == "{http://schema.samply.de/mdr/common}key") and (
                    child.text == "fhir-coding-system"):
                next_is_coding_system = True
            if (child.tag == "{http://schema.samply.de/mdr/common}value") and next_is_coding_system:
                coding_system = child.text
                next_is_coding_system = False
            if (child.tag == "{http://schema.samply.de/mdr/common}key") and (child.text == "terminology-code"):
                next_is_code = True
            if (child.tag == "{http://schema.samply.de/mdr/common}value") and next_is_code:
                code = child.text
                next_is_code = False
    return coding_system, code


def resolve_unit_information(element_id, element_tree):
    units = []
    described_value_domain_id = ""
    for data_element in element_tree.xpath("/xmlns:export/xmlns:dataElement",
                                           namespaces={'xmlns': "http://schema.samply.de/mdr/common"}):
        if data_element.get("uuid") == element_id:
            for child in data_element:
                described_value_domain_id = child.text
    for described_value_domain in element_tree.xpath("/xmlns:export/xmlns:describedValueDomain",
                                                     namespaces={"xmlns": "http://schema.samply.de/mdr/common"}):
        if described_value_domain.get("uuid") == described_value_domain_id:
            for child in described_value_domain:
                if child.tag == "{http://schema.samply.de/mdr/common}unitOfMeasure":
                    if not child.text:
                        continue
                    units.append(child.text)
    return units


def get_loinc_code_leafs(element_id, element_tree):
    profile_information = []
    for element in element_tree.xpath("/xmlns:export/xmlns:scopedIdentifier",
                                      namespaces={'xmlns': "http://schema.samply.de/mdr/common"}):
        if element.get("uuid") == element_id:
            if subs := element.xpath("xmlns:sub", namespaces={'xmlns': "http://schema.samply.de/mdr/common"}):
                for sub in subs:
                    profile_information += get_loinc_code_leafs(sub.text, element_tree)
            else:
                for definition in element.xpath("xmlns:definitions/xmlns:definition",
                                                namespaces={'xmlns': "http://schema.samply.de/mdr/common"}):
                    code_name_de = ""
                    if definition.get("lang") == "de":
                        for designation in (
                                definition.xpath("xmlns:designation",
                                                 namespaces={'xmlns': "http://schema.samply.de/mdr/common"})):
                            code_name_de = designation.text
                    code_name_en = ""
                    if definition.get("lang") == "en":
                        for designation in (
                                definition.xpath("xmlns:designation",
                                                 namespaces={'xmlns': "http://schema.samply.de/mdr/common"})):
                            code_name_en = designation.text
                code = get_code_from_slots(element)
                for child in element:
                    if child.tag == "{http://schema.samply.de/mdr/common}element":
                        unit = resolve_unit_information(child.text, element_tree)
                information = ProfileInformation(code_name_en, code_name_de, code, unit)
                profile_information.append(information)
    return profile_information


def get_answer_list_code(response):
    if parameters := response.get("parameter"):
        for parameter in parameters:
            if parts := parameter.get("part"):
                next_is_answer_list = False
                for part in parts:
                    if next_is_answer_list and (valueCode := part.get("valueCode")):
                        return valueCode
                    if (valueCode := part.get("valueCode")) and (valueCode == "answer-list"):
                        next_is_answer_list = True


def get_answer_list(code):
    response = requests.get(
        f"https://ontoserver.imi.uni-luebeck.de/fhir/CodeSystem/$lookup?system=http://loinc.org&code={code[1]}&property=answer-list")
    if answer_list_code := get_answer_list_code(response.json()):
        return "http://loinc.org/vs/" + answer_list_code
    return None
