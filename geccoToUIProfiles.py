import os
import requests
import csv
from UiDataModel import *
from LogicalModelToProfile import LOGICAL_MODEL_TO_PROFILE

GECCO_DATA_SET = "geccoDataSet/de.gecco#1.0.4/package"

"""
    Date of birth requires date selection in the ui
    ResuscitationOrder Consent is not mappable for fhir search
    RespiratoryOutcome needs special handling its a condition but has a value in the verification status:
        Confirmed -> Patient dependent on ventilator 
        Refuted -> Patient not dependent on ventilator 
    Severity is handled within Symptoms
"""

IGNORE_LIST = ["Date of birth", "RespiratoryOutcome", "Severity"]

IGNORE_CATEGORIES = []

MAIN_CATEGORIES = ["Anamnese / Risikofaktoren", "Demographie", "Einwilligung", "Laborwerte", "Therapie", "Bioproben"]

ONTOLOGY_SERVER_ADDRESS = os.environ.get('ONTOLOGY_SERVER_ADDRESS')


class UnknownHandlingException(Exception):
    def __init__(self, message):
        self.message = message


def to_upper_camel_case(string):
    result = ""
    for substring in string.split(" "):
        result += substring.capitalize()
    return result


def resolve_terminology_entry_profile(terminology_entry):
    name = LOGICAL_MODEL_TO_PROFILE.get(to_upper_camel_case(terminology_entry.display)) \
        if to_upper_camel_case(terminology_entry.display) in LOGICAL_MODEL_TO_PROFILE else to_upper_camel_case(
        terminology_entry.display)
    found = False
    for filename in os.listdir("%s" % GECCO_DATA_SET):
        if name in filename and filename.startswith("Profile"):
            found = True
            with open(GECCO_DATA_SET + "/" + filename) as profile_file:
                profile_data = json.load(profile_file)
                if profile_data["type"] == "Condition":
                    # Corner case
                    if profile_data["name"] == "SymptomsCovid19":
                        translate_symptom(profile_data, terminology_entry)
                    # Corner case
                    elif profile_data["name"] == "DiagnosisCovid19":
                        translate_diagnosis_covid_19(profile_data, terminology_entry)
                    else:
                        translate_condition(profile_data, terminology_entry)
                elif profile_data["type"] == "Observation":
                    # Corner case
                    if name == "ObservationLab":
                        translate_laboratory_values(profile_data, terminology_entry)
                    elif name == "BloodPressure":
                        translate_blood_pressure(profile_data, terminology_entry)
                    elif name == "HistoryOfTravel":
                        translate_history_of_travel(profile_data, terminology_entry)
                    elif profile_data["name"] == "PaCO2" or profile_data["name"] == "PaO2" or profile_data[
                        "name"] == "PH":
                        translate_gas_panel(profile_data, terminology_entry)
                    elif name == "SOFA":
                        translate_sofa(profile_data, terminology_entry)
                    else:
                        translate_observation(profile_data, terminology_entry)
                elif profile_data["type"] == "date":
                    pass
                elif profile_data["type"] == "Procedure":
                    translate_procedure(profile_data, terminology_entry)
                elif profile_data["type"] == "Immunization":
                    translate_immunization(profile_data, terminology_entry)
                elif profile_data["type"] == "Consent":
                    # Corner case Resuscitation
                    if profile_data["name"] == "DoNotResuscitateOrder":
                        translate_resuscitation(profile_data, terminology_entry)
                    else:
                        translate_consent(profile_data, terminology_entry)
                elif profile_data["type"] == "DiagnosticReport":
                    translate_diagnostic_report(profile_data, terminology_entry)
                elif profile_data["type"] == "MedicationStatement":
                    translate_medication_statement(profile_data, terminology_entry)
                else:
                    raise UnknownHandlingException(profile_data["type"])
        elif name in filename and filename.startswith("Extension"):  #
            found = True
            with open(GECCO_DATA_SET + "/" + filename) as profile_file:
                profile_data = json.load(profile_file)
                if filename == "Extension-EthnicGroup.json":
                    translate_ethnic_group(profile_data, terminology_entry)
                elif filename == "Extension-Age.json":
                    translate_age(profile_data, terminology_entry)
    if not found:
        print(to_upper_camel_case(terminology_entry.display) + "Not found!")


def translate_condition(profile_data, terminology_entry):
    terminology_entry.fhirMapperType = "Condition"
    for element in profile_data["differential"]["element"]:
        if element["path"] == "Condition.code.coding":
            if "binding" in element:
                value_set = element["binding"]["valueSet"]
                terminology_entry.children += (
                    get_termentries_from_onto_server(value_set))
                # FIXME: Incorrect break multiple valuesets are allowed but this is currently a work around
                break
            elif "patternCoding" in element:
                code = element["patternCoding"]["code"]
                # FIXME: Working with differential is not sufficient here.
                system = element["patternCoding"]["system"] if "system" in element[
                    "patternCoding"] else "http://snomed.info/sct"
                display = get_term_code_display_from_onto_server(system, code)
                terminology_entry.leaf = False
                terminology_entry.selectable = False
                term_code = TermCode(system, code, display)
                child = TerminologyEntry([term_code], "CodeableConcept", leaf=True, selectable=True)
                terminology_entry.children.append(child)


def translate_diagnosis_covid_19(profile_data, terminology_entry):
    terminology_entry.fhirMapperType = "DiagnosisCovid19"
    for element in profile_data["differential"]["element"]:
        parse_term_code(terminology_entry, element, "Condition.code.coding")
        if element["path"] == "Condition.stage.summary.coding":
            if "binding" in element:
                value_set = element["binding"]["valueSet"]
                value_definition = ValueDefinition("concept")
                value_definition.selectableConcepts += get_termcodes_from_onto_server(value_set)
                terminology_entry.valueDefinitions.append(value_definition)
                terminology_entry.leaf = True
                terminology_entry.selectable = True
                # FIXME: Incorrect break multiple valuesets are allowed but this is currently a work around
                break


def translate_symptom(profile_data, terminology_entry):
    terminology_entry.fhirMapperType = "Symptom"
    # TODO: Refactor not hardcoded!
    severity_vs = "https://www.netzwerk-universitaetsmedizin.de/fhir/ValueSet/condition-severity"
    for element in profile_data["differential"]["element"]:
        if element["path"] == "Condition.code.coding":
            if "binding" in element:
                value_set = element["binding"]["valueSet"]
                children = get_termentries_from_onto_server(value_set)
                for child in children:
                    child.fhirMapperType = "Symptom"
                    value_definition = ValueDefinition("concept")
                    value_definition.selectableConcepts += get_termcodes_from_onto_server(severity_vs)
                    child.valueDefinitions.append(value_definition)
                terminology_entry.children += children
                break


def translate_medication_statement(profile_data, terminology_entry):
    terminology_entry.fhirMapperType = "MedicationStatement"
    for element in profile_data["differential"]["element"]:
        if element["path"] == "MedicationStatement.medication[x].coding":
            if "binding" in element:
                value_set = element["binding"]["valueSet"]
                terminology_entry.children += (
                    get_termentries_from_onto_server(value_set))
    terminology_entry.children = sorted(terminology_entry.children)


def update_termcode_to_match_pattern_coding(terminology_entry, element):
    if terminology_entry.termCode.system == "num.codex":
        if element["path"] == "Observation.code.coding" and "patternCoding" in element:
            terminology_entry.termCode.code = element["patternCoding"]["code"]
            terminology_entry.termCode.system = element["patternCoding"]["system"]


def translate_observation(profile_data, terminology_entry):
    is_concept_value = False
    # TODO: THIS IS AWFUL REFACTOR!!!
    if terminology_entry.terminologyType != "Quantity":
        for element in profile_data["differential"]["element"]:
            update_termcode_to_match_pattern_coding(terminology_entry, element)
            if "type" in element:
                if element["path"] == "Observation.value[x]" and element["type"][0]["code"] == "CodeableConcept":
                    terminology_entry.fhirMapperType = "ConceptObservation"
                    is_concept_value = True
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
                    terminology_entry.fhirMapperType = "ConceptObservation"
                    is_concept_value = True
                    if "binding" in element:
                        value_set = element["binding"]["valueSet"]
                        value_definition = ValueDefinition("concept")
                        value_definition.selectableConcepts += get_termcodes_from_onto_server(value_set)
                        terminology_entry.valueDefinitions.append(value_definition)
                        terminology_entry.leaf = True
                        terminology_entry.selectable = True
                        break
    if not is_concept_value:
        terminology_entry.fhirMapperType = "QuantityObservation"
        terminology_entry.terminologyType = "Quantity"
    if terminology_entry.terminologyType == "Quantity":
        terminology_entry.fhirMapperType = "QuantityObservation"
        terminology_entry.leaf = True
        terminology_entry.selectable = True


def translate_gas_panel(profile_data, terminology_entry):
    for element in profile_data["differential"]["element"]:
        if element["path"] == "Observation.code.coding" and "patternCoding" in element:
            term_code = TermCode(element["patternCoding"]["system"], element["patternCoding"]["code"],
                                 element["sliceName"])
            child = TerminologyEntry([term_code], "Quantity", leaf=True, selectable=True)
            terminology_entry.children.append(child)
    terminology_entry.leaf = False
    terminology_entry.selectable = False
    terminology_entry.fhirMapperType = "QuantityObservation"


def translate_laboratory_values(_profile_data, terminology_entry: TerminologyEntry):
    if terminology_entry.terminologyType == "Quantity":
        for code in terminology_entry.termCodes:
            entry = TerminologyEntry([code], terminology_entry.terminologyType)
            entry.leaf = True
            entry.selectable = True
            entry.fhirMapperType = "QuantityObservation"
            entry.valueDefinitions = []
            terminology_entry.children.append(entry)
        terminology_entry.fhirMapperType = "QuantityObservation"
        terminology_entry.selectable = False
        terminology_entry.leaf = False


def translate_sofa(profile_data, terminology_entry):
    for element in profile_data["differential"]["element"]:
        update_termcode_to_match_pattern_coding(terminology_entry, element)
    terminology_entry.fhirMapperType = "Sofa"
    terminology_entry.selectable = True
    terminology_entry.leaf = True
    terminology_entry.terminologyType = "Quantity"


def translate_procedure(profile_data, terminology_entry):
    terminology_entry.fhirMapperType = "Procedure"
    terminology_entry.leaf = True
    terminology_entry.selectable = True
    for element in profile_data["differential"]["element"]:
        if element["id"] == "Procedure.code.coding:sct":
            if "binding" in element:
                value_set = element["binding"]["valueSet"]
                terminology_entry.children += (get_termentries_from_onto_server(value_set))
                terminology_entry.leaf = False
                break


def translate_immunization(profile_data, terminology_entry):
    terminology_entry.fhirMapperType = "Immunization"
    for element in profile_data["differential"]["element"]:
        if element["id"] == "Immunization.vaccineCode.coding:snomed":  # and element["slicingName"] == "atc":
            if "binding" in element:
                value_set = element["binding"]["valueSet"]
                terminology_entry.children += (get_termentries_from_onto_server(value_set))
                terminology_entry.selectable = False
                break


def translate_ethnic_group(profile_data, terminology_entry):
    terminology_entry.fhirMapperType = "EthnicGroup"
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


def translate_age(_profile_data, terminology_entry):
    terminology_entry.fhirMapperType = "Age"
    terminology_entry.selectable = True
    terminology_entry.leaf = True


def translate_diagnostic_report(profile_data, terminology_entry):
    terminology_entry.fhirMapperType = "DiagnosticReport"
    for element in profile_data["differential"]["element"]:
        parse_term_code(terminology_entry, element, "DiagnosticReport.code.coding")
        if element["path"] == "DiagnosticReport.conclusionCode" and "binding" in element:
            value_set = element["binding"]["valueSet"]
            value_definition = ValueDefinition("concept")
            value_definition.selectableConcepts += get_termcodes_from_onto_server(value_set)
            terminology_entry.valueDefinitions.append(value_definition)
            terminology_entry.leaf = True
            terminology_entry.selectable = True
            break


def parse_term_code(terminology_entry, element, path):
    if element["path"] == path and "patternCoding" in element:
        if "system" in element["patternCoding"] and "code" in element["patternCoding"]:
            term_code = TermCode(element["patternCoding"]["system"], element["patternCoding"]["code"],
                                 terminology_entry.termCode.display)
            terminology_entry.termCodes.append(term_code)
            terminology_entry.termCode = term_code


# TODO
def translate_consent(profile_data, terminology_entry):
    terminology_entry.fhirMapperType = "Consent"
    terminology_entry.selectable = True
    terminology_entry.leaf = True
    for element in profile_data["differential"]["element"]:
        if element["id"] == "Consent.provision.code":
            if "binding" in element:
                value_set = element["binding"]["valueSet"]
                value_definition = ValueDefinition("concept")
                value_definition.selectableConcepts += get_termcodes_from_onto_server(value_set)
                terminology_entry.valueDefinitions.append(value_definition)
                break


def translate_resuscitation(profile_data, terminology_entry):
    terminology_entry.fhirMapperType = "ResuscitationStatus"
    terminology_entry.selectable = True
    terminology_entry.leaf = True
    for element in profile_data["differential"]["element"]:
        if element["id"] == "Consent.category.coding.system":
            terminology_entry.termCode.system = element["fixedUri"]
        if element["id"] == "Consent.category.coding.code":
            terminology_entry.termCode.code = element["fixedCode"]
        if element["id"] == "Consent.provision.code":
            if "binding" in element:
                value_set = element["binding"]["valueSet"]
                value_definition = ValueDefinition("concept")
                value_definition.selectableConcepts += get_termcodes_from_onto_server(value_set)
                terminology_entry.valueDefinitions.append(value_definition)
                break


def translate_blood_pressure(_profile_data, terminology_entry):
    terminology_entry.fhirMapperType = "BloodPressure"
    terminology_entry.selectable = True
    terminology_entry.leaf = True


def translate_history_of_travel(profile_data, terminology_entry):
    terminology_entry.fhirMapperType = "HistoryOfTravel"
    terminology_entry.selectable = True
    terminology_entry.leaf = True
    for element in profile_data["differential"]["element"]:
        if element["id"] == "Observation.component:Country.value[x]":
            if "binding" in element:
                value_set = element["binding"]["valueSet"]
                value_definition = ValueDefinition("concept")
                value_definition.selectableConcepts += get_termcodes_from_onto_server(value_set)
                terminology_entry.valueDefinitions.append(value_definition)
                terminology_entry.leaf = True
                terminology_entry.selectable = True
                break


def get_term_code_display_from_onto_server(system, code):
    response = requests.get(f"{ONTOLOGY_SERVER_ADDRESS}CodeSystem/$lookup?system={system}&code={code}")
    if response.status_code == 200:
        response_data = response.json()
        for parameter in response_data["parameter"]:
            if name := parameter.get("name"):
                if name == "display":
                    return parameter.get("valueString") if parameter.get("valueString") else ""
    return ""


# TODO: We only want to use a single coding system. The different coding systems need to be prioratized
# We do not want to expand is-A relations of snomed or we need a tree structure , but we cant gain the information
# needed to create a tree structure
def get_termentries_from_onto_server(canonical_address_value_set):
    # In Gecco 1.04 all icd10 elements with children got removed this brings them back. Requires matching valuesets on
    # Ontoserver
    if "icd" in canonical_address_value_set:
        canonical_address_value_set = canonical_address_value_set + "-with-parent"
    icd10_result = []
    snomed_result = []
    result = []
    response = requests.get(
        f"{ONTOLOGY_SERVER_ADDRESS}ValueSet/$expand?url={canonical_address_value_set}"
        f"&includeDesignations=true&system-version=http://fhir.de/CodeSystem/dimdi/icd-10-gm%7C2020&"
        f"system-version=http://fhir.de/CodeSystem/dimdi/atc%7Catcgm2021")
    if response.status_code == 200:
        value_set_data = response.json()
        for contains in value_set_data["expansion"]["contains"]:
            system = contains["system"]
            code = contains["code"]
            display = contains["display"]
            version = None
            if "version" in contains:
                version = contains["version"]
            term_code = TermCode(system, code, display, version)
            terminology_entry = TerminologyEntry([term_code], "CodeableConcept", leaf=True, selectable=True)
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
    else:
        print(canonical_address_value_set)
        # TODO better Exception
        raise (Exception("HTTP Error"))
    # Order matters here!
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
                        if "language" in designation and designation["language"] == "de-DE":
                            term_code.display = designation["value"]
                snomed_result.append(term_code)
            else:
                result.append(term_code)
    else:
        print(canonical_address_value_set)
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


# Deprecated
def to_reduced_icd_tree(termcodes):
    groups, categories, subcategories_three_digit, subcategories_four_digit = \
        get_groups_categories_subcategories(termcodes)

    result = []

    for subcategory_four_digit_entry in sorted(subcategories_four_digit):

        if not any(subcategory_three_digit_entry.termCode.code == subcategory_four_digit_entry.termCode.code[:-1] for
                   subcategory_three_digit_entry in subcategories_three_digit):
            result.append(subcategory_four_digit_entry)

    for subcategory_three_digit_entry in sorted(subcategories_three_digit):
        if not any(category_entry.termCode.code == subcategory_three_digit_entry.termCode.code[:-2] for
                   category_entry in categories):
            result.append(subcategory_three_digit_entry)

    add_category_entries_to_groups_or_result(groups, categories, result)

    result += sorted(groups)

    return result


def get_groups_categories_subcategories(termcodes):
    groups = set()
    categories = set()
    subcategories_three_digit = set()
    subcategories_four_digit = set()

    for termcode in termcodes:
        if re.match("[A-Z][0-9][0-9]-[A-Z][0-9][0-9]$", termcode.code):
            groups.add(TerminologyEntry([termcode], "CodeableConcept", leaf=True))
        elif re.match("[A-Z][0-9][0-9]$", termcode.code):
            categories.add(TerminologyEntry([termcode], "CodeableConcept", leaf=True))
        elif re.match("[A-Z][0-9][0-9]\\.[0-9]$", termcode.code):
            subcategories_three_digit.add(TerminologyEntry([termcode], "CodeableConcept", leaf=True))
        elif re.match("[A-Z][0-9][0-9]\\.[0-9][0-9]$", termcode.code):
            terminology_entry = TerminologyEntry([termcode], "CodeableConcept", leaf=True)
            subcategories_four_digit.add(terminology_entry)
    return groups, categories, subcategories_three_digit, subcategories_four_digit


def add_category_entries_to_groups_or_result(groups, categories, result):
    for category_entry in sorted(categories):
        if group_entry := get_parent_group(category_entry, groups):
            group_entry.children.append(category_entry)
            group_entry.leaf = False
        else:
            result.append(category_entry)


def get_parent_group(category_entry, groups):
    for group_entry in sorted(groups, key=lambda x: get_range_size(x)):
        if int(group_entry.termCode.code[-2:]) >= int(category_entry.termCode.code[1:]) >= int(
                group_entry.termCode.code[1:3]) and \
                category_entry.termCode.code[0] == group_entry.termCode.code[0]:
            return group_entry
    return None


def to_icd_tree(termcodes):
    groups, categories, subcategories_three_digit, subcategories_four_digit = \
        get_groups_categories_subcategories(termcodes)
    result = []

    add_subcategories_four_digit_to_subcategories_three_digit_or_result(subcategories_four_digit,
                                                                        subcategories_three_digit, result)

    add_subcategories_three_digit_to_category_or_result(subcategories_three_digit, categories, result)

    add_category_entries_to_groups_or_result(groups, categories, result)

    groups = structure_groups_to_tree(groups)

    result += sorted(groups)

    result = sorted(result)

    return result


def get_range_size(terminology_entry):
    if terminology_entry:
        return int(terminology_entry.termCode.code[-2:]) - int(terminology_entry.termCode.code[1:3])
    else:
        return 10000


def structure_groups_to_tree(groups):
    def within_range_of(terminology_entry, other_terminology_entry):
        if terminology_entry.termCode.code == other_terminology_entry.termCode.code:
            return False
        return ((int(other_terminology_entry.termCode.code[1:3]) <= int(terminology_entry.termCode.code[1:3]) <=
                 int(other_terminology_entry.termCode.code[-2:])) and
                (int(other_terminology_entry.termCode.code[1:3]) <= int(terminology_entry.termCode.code[-2:]) <=
                 int(other_terminology_entry.termCode.code[-2:])))

    groups_list = list(groups)
    groups_list.sort(key=lambda x: get_range_size(x))
    to_be_removed_groups = set()
    for group_entry in groups_list:
        parent_group = None
        for other_group_entry in groups_list:
            if within_range_of(group_entry, other_group_entry) and get_range_size(other_group_entry) < \
                    get_range_size(parent_group):
                parent_group = other_group_entry
        if parent_group:
            parent_group.children.append(group_entry)
            parent_group.children.sort()
            parent_group.leaf = False
            to_be_removed_groups.add(group_entry)
    groups = groups - to_be_removed_groups
    return groups


def add_subcategories_four_digit_to_subcategories_three_digit_or_result(subcategories_four_digit,
                                                                        subcategories_three_digit, result):
    for subcategory_four_digit_entry in sorted(subcategories_four_digit):
        parent_found = False
        for subcategory_three_digit_entry in subcategories_three_digit:
            if subcategory_three_digit_entry.termCode.code == subcategory_four_digit_entry.termCode.code[:-1]:
                subcategory_three_digit_entry.children.append(subcategory_four_digit_entry)
                subcategory_three_digit_entry.leaf = False
                parent_found = True
        if not parent_found:
            result.append(subcategory_four_digit_entry)


def add_subcategories_three_digit_to_category_or_result(subcategories_three_digit, categories, result):
    for subcategory_three_digit_entry in sorted(subcategories_three_digit):
        parent_found = False
        for category_entry in categories:
            if category_entry.termCode.code == subcategory_three_digit_entry.termCode.code[:-2]:
                category_entry.children.append(subcategory_three_digit_entry)
                category_entry.leaf = False
                parent_found = True
        if not parent_found:
            result.append(subcategory_three_digit_entry)


# element from Logical Model
def add_terminology_entry_to_category(element, categories, terminology_type):
    for category_entry in categories:
        if category_entry.path in element["base"]["path"]:
            terminology_entry = TerminologyEntry(get_term_codes(element), terminology_type)
            # We use the english display to resolve after we switch to german.
            terminology_entry.display = element["short"]
            if terminology_entry.display in IGNORE_LIST:
                continue
            # TODO: Refactor don't do this here?!
            resolve_terminology_entry_profile(terminology_entry)
            if terminology_entry.terminologyType == "Quantity":
                terminology_entry.valueDefinitions.append(get_value_definition(element))
                # FIXME: This is only a quick workaround for GasPanel values.
                for child in terminology_entry.children:
                    child.valueDefinitions.append(get_value_definition(element))
            terminology_entry.display = get_german_display(element) if get_german_display(element) else element["short"]
            if terminology_entry.display == category_entry.display:
                # Resolves issue like : -- Symptoms                 --Symptoms
                #                           -- Symptoms     --->      -- Coughing
                #                              -- Coughing
                category_entry.children += terminology_entry.children
            else:
                category_entry.children.append(terminology_entry)


def get_term_codes(element):
    term_codes = []
    if "code" in element:
        for code in element["code"]:
            term_codes.append(TermCode(code["system"], code["code"], code["display"],
                                       code["version"] if "version" in code else None))
    if not term_codes:
        term_codes.append(TermCode("num.codex", element["short"], element["short"]))
    return term_codes


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
    with open(f"{GECCO_DATA_SET}/StructureDefinition-LogicalModel-GECCO.json", encoding="utf-8") as json_file:
        categories = []
        data = json.load(json_file)
        for element in data["differential"]["element"]:
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
    term_code = [TermCode("num.codex", category_entry.display, category_entry.display)]
    result = TerminologyEntry(term_code, "Category", selectable=False)
    result.display = category_entry.display
    result.path = category_entry.path
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
                elif element["type"][0]["code"] == "CodeableConcept":
                    add_terminology_entry_to_category(element, category_terminology_entries, "CodeableConcept")
                elif element["type"][0]["code"] == "Quantity":
                    add_terminology_entry_to_category(element, category_terminology_entries, "Quantity")
                elif element["type"][0]["code"] == "date":
                    add_terminology_entry_to_category(element, category_terminology_entries, "date")
                else:
                    raise Exception(f"Unknown element {element['type'][0]['code']}")
        print(category_terminology_entries)
    for category_entry in category_terminology_entries:
        category_entry.children = sorted(category_entry.children)
        print(category_entry.children)
    return category_terminology_entries


def get_specimen():
    specimen_term_code = TermCode("num.codex", "Bioproben", "Bioproben")
    specimen_category_entry = TerminologyEntry([specimen_term_code], "Category", selectable=False, leaf=False)
    specimen_category_entry.fhirMapperType = "Specimen"

    with open('NAPKON_Typen_SCT_CODEX.CSV', mode='r') as csv_file:
        csv_reader = csv.DictReader(csv_file, delimiter=";")
        for row in csv_reader:
            term_code = TermCode(row["System"], row["Code"], row["Display"])
            specimen_child = TerminologyEntry([term_code], "CodeableConcept", selectable=True, leaf=True)
            specimen_child.fhirMapperType = "Specimen"
            specimen_child.display = row["guiDisplay"]
            specimen_category_entry.children.append(specimen_child)
    return specimen_category_entry


def get_consent():
    consent_term_code = TermCode("num.codex", "Einwilligung", "Einwilligung")
    consent_category_entry = TerminologyEntry([consent_term_code], "Category", selectable=False, leaf=False)
    consent_category_entry.fhirMapperType = "Consent"
    with open('CONSENT_PROVISIONS.CSV', mode='r', encoding="utf-8") as csv_file:
        csv_reader = csv.DictReader(csv_file, delimiter=";")
        for row in csv_reader:
            term_code = TermCode(row["System"], row["Code"], row["Display"])
            consent_child = TerminologyEntry([term_code], "CodeableConcept", selectable=True, leaf=True)
            consent_child.fhirMapperType = "Consent"
            consent_child.display = row["guiDisplay"]
            value_definition = ValueDefinition("concept")
            value_definition.selectableConcepts.append(
                TermCode("http://hl7.org/fhir/consent-provision-type", "permit", "permit"))
            value_definition.selectableConcepts.append(
                TermCode("http://hl7.org/fhir/consent-provision-type", "deny", "deny"))
            consent_child.valueDefinitions.append(value_definition)
            consent_category_entry.children.append(consent_child)
    return consent_category_entry
