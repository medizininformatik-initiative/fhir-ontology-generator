import os
import requests
import re
from UiDataModel import *
from mapper import LOGICAL_MODEL_TO_PROFILE

IGNORE_LIST = ["Date of birth", "History of travel", "Resuscitation order", "Immunization status",
               "SARS-CoV-2 (COVID-19) IgG IA Ql", "Sars-cov-2(covid-19)IggIaQl", "SARS-CoV-2 (COVID-19) IgG IA Qn",
               "Sars-cov-2(covid-19)IggIaQn", "SARS-CoV-2 (COVID-19) IgM IA Ql", "Sars-cov-2(covid-19)IgmIaQl",
               "SARS-CoV-2 (COVID-19) IgM IA Qn", "Sars-cov-2(covid-19)IgmIaQn", "SARS-CoV-2 (COVID-19) IgA IA Ql",
               "Sars-cov-2(covid-19)IgaIaQl", "SARS-CoV-2 (COVID-19) IgA IA Qn", "Sars-cov-2(covid-19)IgaIaQn",
               "SARS-CoV-2 (COVID-19) Ab IA Ql", "Sars-cov-2(covid-19)AbIaQl", "SARS-CoV-2 (COVID-19) Ab IA Qn",
               "Sars-cov-2(covid-19)AbIaQn", "Ventilation therapy", "Is the patient in the intensive care unit?",
               "Radiological findings", "Respiratory outcome", "Follow-up swab result",
               "Study enrolment due to Covid-19", "Interventional studies participation", "Severity", "SOFA-Score"]

IGNORE_CATEGORIES = ["Studieneinschluss / Einschlusskriterien "]

MAIN_CATEGORIES = ["Anamnese / Risikofaktoren", "Demographie", "Laborwerte", "Therapie"]

ONTOLOGY_SERVER_ADDRESS = "https://ontoserver.imi.uni-luebeck.de/fhir/"


class UnknownHandlingException(Exception):
    def __init__(self, message):
        self.message = message


def to_upper_camel_case(string):
    result = ""
    for substring in string.split(" "):
        result += substring.capitalize()
    return result


def translate_condition(profile_data, terminology_entry):
    for element in profile_data["differential"]["element"]:
        if element["path"] == "Condition.code.coding":
            if "binding" in element:
                value_set = element["binding"]["valueSet"]
                terminology_entry.children += (
                    get_termentries_from_onto_server(value_set))
                # FIXME: Incorrect break multiple valuesets are allowed but this is currently a work around
                break
        elif element["path"] == "Condition.stage.summary.coding":
            if "binding" in element:
                value_set = element["binding"]["valueSet"]
                terminology_entry.children += (
                    get_termentries_from_onto_server(value_set))
                # FIXME: Incorrect break multiple valuesets are allowed but this is currently a work around
                break


def translate_symptom(profile_data, terminology_entry):
    # TODO: Refactor not hardcoded!
    severity_vs = "https://www.netzwerk-universitaetsmedizin.de/fhir/ValueSet/condition-severity"
    for element in profile_data["differential"]["element"]:
        if element["path"] == "Condition.code.coding":
            if "binding" in element:
                value_set = element["binding"]["valueSet"]
                children = get_termentries_from_onto_server(value_set)
                for child in children:
                    value_definition = ValueDefinition("concept")
                    value_definition.selectableConcepts += get_termcodes_from_onto_server(severity_vs)
                    child.valueDefinitions.append(value_definition)
                terminology_entry.children += children
                break


def translate_medication_statement(profile_data, terminology_entry):
    for element in profile_data["differential"]["element"]:
        if element["path"] == "MedicationStatement.medication[x].coding":
            if "binding" in element:
                value_set = element["binding"]["valueSet"]
                terminology_entry.children += (
                    get_termentries_from_onto_server(value_set))
                break


def translate_observation(profile_data, terminology_entry):
    for element in profile_data["differential"]["element"]:
        if "type" in element:
            if element["path"] == "Observation.value[x]" and element["type"][0]["code"] == "CodeableConcept":
                if "binding" in element:
                    value_set = element["binding"]["valueSet"]
                    value_definition = ValueDefinition("concept")
                    value_definition.selectableConcepts += get_termcodes_from_onto_server(value_set)
                    terminology_entry.valueDefinitions.append(value_definition)
                    terminology_entry.leaf = True
                    terminology_entry.selectable = True
                    break
        elif "sliceName" in element:
            if element["path"] == "Observation.value[x]" and element["sliceName"] == "valueCodeableConcept" or \
                    element["path"] == "Observation.value[x].coding":
                if "binding" in element:
                    value_set = element["binding"]["valueSet"]
                    value_definition = ValueDefinition("concept")
                    value_definition.selectableConcepts += get_termcodes_from_onto_server(value_set)
                    terminology_entry.valueDefinitions.append(value_definition)
                    terminology_entry.leaf = True
                    terminology_entry.selectable = True
                    break


def translate_procedure(profile_data, terminology_entry):
    value_definition = ValueDefinition("concept")
    value_definition.selectableConcepts = get_status_termcodes_for_procedures()
    terminology_entry.valueDefinitions.append(value_definition)
    terminology_entry.leaf = True
    terminology_entry.selectable = True


# TODO: Refactor to not being hardcoded
def get_status_termcodes_for_procedures():
    # TODO: Double-Check with native speaker/medical professional
    status_codes = {"preparation": "Vorbereitung",
                    "in-progress": "in Bearbeitung",
                    "not-done": "nicht Durchgeführt",
                    "on-hold": "in Wartestellung",
                    "stopped": "gestoppt",
                    "completed": "abgeschlossen",
                    "entered-in-error": "fehlerhafte Eingabe",
                    "unknown": "Unbekannt"}
    system = "http://hl7.org/fhir/event-status"
    version = "4.0.1"
    result = []
    for code, german_display in status_codes.items():
        result.append(TermCode(system, code, german_display, version))
    return result


def translate_immunization(profile_data, terminology_entry):
    for element in profile_data["differential"]["element"]:
        if "type" in element:
            if element["path"] == "Immunization.vaccineCode.coding":  # and element["slicingName"] == "atc":
                if "binding" in element:
                    value_set = element["binding"]["valueSet"]
                    value_definition = ValueDefinition("concept")
                    value_definition.selectableConcepts += get_termcodes_from_onto_server(value_set)
                    terminology_entry.valueDefinitions.append(value_definition)
                    terminology_entry.leaf = True
                    terminology_entry.selectable = True
                    break


def translate_ethnic_group(profile_data, terminology_entry):
    for element in profile_data["differential"]["element"]:
        if element["path"] == "Extension.value[x]":
            if "binding" in element:
                value_set = element["binding"]["valueSet"]
                value_definition = ValueDefinition("concept")
                value_definition.selectableConcepts += get_termcodes_from_onto_server(value_set)
                terminology_entry.valueDefinitions.append(value_definition)
                terminology_entry.leaf = True
                terminology_entry.selectable = True
                break


def translate_diagnostic_report(profile_data, terminology_entry):
    for element in profile_data["differential"]["element"]:
        if element["path"] == "DiagnosticReport.conclusionCode":
            if "binding" in element:
                value_set = element["binding"]["valueSet"]
                value_definition = ValueDefinition("concept")
                value_definition.selectableConcepts += get_termcodes_from_onto_server(value_set)
                terminology_entry.valueDefinitions.append(value_definition)
                terminology_entry.leaf = True
                terminology_entry.selectable = True
                break


def resolve_terminology_entry_profile(terminology_entry):
    name = LOGICAL_MODEL_TO_PROFILE.get(to_upper_camel_case(terminology_entry.display)) \
        if to_upper_camel_case(terminology_entry.display) in LOGICAL_MODEL_TO_PROFILE else to_upper_camel_case(
        terminology_entry.display)
    found = False
    for filename in os.listdir("geccoDataset"):
        if name in filename and filename.startswith("Profile"):
            found = True
            with open("geccoDataset/" + filename) as profile_file:
                profile_data = json.load(profile_file)
                if profile_data["type"] == "Condition":
                    # Corner case
                    if profile_data["name"] == "SymptomsCovid19":
                        translate_symptom(profile_data, terminology_entry)
                    else:
                        translate_condition(profile_data, terminology_entry)
                elif profile_data["type"] == "Observation":
                    translate_observation(profile_data, terminology_entry)
                elif profile_data["type"] == "date":
                    pass
                elif profile_data["type"] == "Procedure":
                    translate_procedure(profile_data, terminology_entry)
                elif profile_data["type"] == "Immunization":
                    translate_immunization(profile_data, terminology_entry)
                elif profile_data["type"] == "Consent":
                    pass
                elif profile_data["type"] == "DiagnosticReport":
                    translate_diagnostic_report(profile_data, terminology_entry)
                elif profile_data["type"] == "MedicationStatement":
                    translate_medication_statement(profile_data, terminology_entry)
                else:
                    raise UnknownHandlingException(profile_data["type"])
        elif name in filename and filename.startswith("Extension"):  #
            found = True
            with open("geccoDataset/" + filename) as profile_file:
                profile_data = json.load(profile_file)
                if filename == "Extension-EthnicGroup.json":
                    translate_ethnic_group(profile_data, terminology_entry)
                elif filename == "Extension-Age.json":
                    pass
    if not found:
        # pass
        print(to_upper_camel_case(terminology_entry.display))


# TODO: We only want to use a single coding system. The different coding systems need to be prioratized
# We do not want to expand is-A relations of snomed or we need a tree structure , but we cant gain the information
# needed to create a tree structure
def get_termentries_from_onto_server(canonical_address_value_set):
    icd10_result = []
    snomed_result = []
    result = []
    response = requests.get(
        f"{ONTOLOGY_SERVER_ADDRESS}ValueSet/$expand?url={canonical_address_value_set}&includeDesignations=true")
    if response.status_code == 200:
        value_set_data = response.json()
        for contains in value_set_data["expansion"]["contains"]:
            system = contains["system"]
            code = contains["code"]
            display = contains["display"]
            term_code = TermCode(system, code, display)
            terminology_entry = TerminologyEntry(term_code, "CodeableConcept", leaf=True, selectable=True)
            if system == "http://fhir.de/CodeSystem/dimdi/icd-10-gm":
                icd10_result.append(term_code)
            elif system == "http://snomed.info/sct":
                if "designation" in contains:
                    for designation in contains["designation"]:
                        if designation["language"] == "de-DE":
                            term_code.display = designation["value"]
                snomed_result.append(terminology_entry)
            else:
                result.append(terminology_entry)
    if icd10_result:
        return to_icd_tree(icd10_result)
    elif result:
        return sorted(result)
    else:
        return sorted(snomed_result)


# TODO: We only want to use a single coding system. The different coding systems need to be prioratized
# We do not want to expand is-A relations of snomed or we need a tree structure , but we cant gain the information
# needed to create a tree structure
def get_termcodes_from_onto_server(canonical_address_value_set):
    icd10_result = []
    snomed_result = []
    result = []
    response = requests.get(
        f"{ONTOLOGY_SERVER_ADDRESS}ValueSet/$expand?url={canonical_address_value_set}&includeDesignations=true")
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
                            term_code.display = designation["value"]
                snomed_result.append(term_code)
            else:
                result.append(term_code)
    else:
        return []
    # TODO: Workaround
    if result and result[0].display == "Hispanic or Latino":
        return sorted(result + snomed_result)
    if icd10_result:
        return icd10_result
    elif result:
        return sorted(result)
    else:
        return sorted(snomed_result)


# TODO: REFACTOR OR DETAILED DESCRIPTION!
def to_icd_tree(termcodes):
    groups = set()
    categories = set()
    subcategories_three_digit = set()
    subcategories_four_digit = set()

    for termcode in termcodes:
        if re.match("[A-Z][0-9][0-9]-[A-Z][0-9][0-9]$", termcode.code):
            groups.add(TerminologyEntry(termcode, "CodeableConcept", leaf=True, selectable=False))
        elif re.match("[A-Z][0-9][0-9]$", termcode.code):
            categories.add(TerminologyEntry(termcode, "CodeableConcept", leaf=True, selectable=True))
        elif re.match("[A-Z][0-9][0-9]\.[0-9]$", termcode.code):
            subcategories_three_digit.add(TerminologyEntry(termcode, "CodeableConcept", leaf=True, selectable=True))
        elif re.match("[A-Z][0-9][0-9]\.[0-9][0-9]$", termcode.code):
            terminology_entry = TerminologyEntry(termcode, "CodeableConcept", leaf=True, selectable=True)
            subcategories_four_digit.add(terminology_entry)
    result = []

    for subcategory_four_digit_entry in sorted(subcategories_four_digit):
        parent_found = False
        for subcategory_three_digit_entry in subcategories_three_digit:
            if subcategory_three_digit_entry.termCode.code == subcategory_four_digit_entry.termCode.code[:-1]:
                # subcategory_three_digit_entry.children.append(subcategory_four_digit_entry)
                # subcategory_three_digit_entry.leaf=False
                parent_found = True
        if not parent_found:
            result.append(subcategory_four_digit_entry)

    for subcategory_three_digit_entry in sorted(subcategories_three_digit):
        parent_found = False
        for category_entry in categories:
            if category_entry.termCode.code == subcategory_three_digit_entry.termCode.code[:-2]:
                # category_entry.children.append(subcategory_three_digit_entry)
                # category_entry.leaf = False
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
                group_entry.leaf = False
                parent_found = True
        if not parent_found:
            result.append(category_entry)

    result += sorted(groups)

    return result


def add_terminology_entry_to_category(element, categories, terminology_type):
    for category_entry in categories:
        if category_entry.path in element["base"]["path"]:
            terminology_entry = TerminologyEntry(get_term_code(element), terminology_type)
            # We use the english display to resolve after we switch to german.
            terminology_entry.display = element["short"]
            if terminology_entry.display in IGNORE_LIST:
                continue
            # TODO: Refactor don't do this here?!
            resolve_terminology_entry_profile(terminology_entry)
            terminology_entry.display = get_german_display(element) if get_german_display(element) else element["short"]
            if terminology_type == "Quantity":
                terminology_entry.leaf = True
                terminology_entry.selectable = True
                terminology_entry.valueDefinitions.append(get_value_definition(element))
            category_entry.children.append(terminology_entry)


def get_term_code(element):
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
    return term_code


def get_value_definition(element):
    value_definition = ValueDefinition("quantity")
    if "extension" in element:
        for extension in element["extension"]:
            if extension["url"] == "http://hl7.org/fhir/StructureDefinition/elementdefinition-allowedUnits":
                if "valueCodeableConcept" in extension:
                    value_codeable_concept = extension["valueCodeableConcept"]
                    if "coding" in value_codeable_concept:
                        for coding in value_codeable_concept["coding"]:
                            if coding["system"] == "http://unitsofmeasure.org/":
                                value_definition.allowedUnits.append(Unit(coding["code"], coding["code"]))
    return value_definition


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
    result = TerminologyEntry(None, "Category")
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
    others = TerminologyEntry(None, "CategoryEntry")
    others.display = "Andere"
    for category in create_terminology_definition_for(get_categories()):
        if category in IGNORE_CATEGORIES:
            continue
        if category.display in MAIN_CATEGORIES:
            f = open("result/" + category.display.replace("/", "") + ".json", 'w')
            f.write(category.to_json())
        else:
            others.children.append(category)
    f = open("result/" + others.display + ".json", 'w')
    f.write(others.to_json())
