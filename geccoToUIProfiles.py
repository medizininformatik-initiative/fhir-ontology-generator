import os
from os import chdir

import requests
import csv
from lxml import etree
from UiDataModel import *
from LogicalModelToProfile import LOGICAL_MODEL_TO_PROFILE
from valueSetToRoots import create_vs_tree

GECCO_DATA_SET = "core_data_sets/de.gecco#1.0.5/package"
MII_MEDICATION_DATA_SET = "core_data_sets/de.medizininformatikinitiative.kerndatensatz.medikation#1.0.10/package"
SPECIMEN_VS = "https://www.medizininformatik-initiative.de/fhir/abide/ValueSet/sct-specimen-type-napkon-sprec"

"""
    Date of birth requires date selection in the ui
    ResuscitationOrder Consent is not mappable for fhir search
    RespiratoryOutcome needs special handling its a condition but has a value in the verification status:
        Confirmed -> Patient dependent on ventilator 
        Refuted -> Patient not dependent on ventilator 
    Severity is handled within Symptoms
"""

IGNORE_LIST = ["Date of birth", "Severity", "OrganizationSammlungBiobank", "SubstanceAdditiv",
               "MedicationMedikation", "MedicationStatementMedikation", "ProbandIn", "Laborbefund", "Laboranforderung"]

IGNORE_CATEGORIES = []

MAIN_CATEGORIES = ["Einwilligung"]

ONTOLOGY_SERVER_ADDRESS = os.environ.get('ONTOLOGY_SERVER_ADDRESS')

GENERATE_DUPLICATES = os.getenv("GENERATE_DUPLICATES", 'False').lower() == "true"


class UnknownHandlingException(Exception):
    def __init__(self, message):
        self.message = message


def to_upper_camel_case(string):
    result = ""
    if re.match("([A-Z][a-z0-9]+)+", string) and " " not in string:
        return string
    for substring in string.split(" "):
        result += substring.capitalize()
    return result


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
                elif element["type"][0]["code"] == "CodeableConcept":
                    add_terminology_entry_to_category(element, category_terminology_entries, "CodeableConcept")
                elif element["type"][0]["code"] == "Quantity":
                    add_terminology_entry_to_category(element, category_terminology_entries, "Quantity")
                elif element["type"][0]["code"] == "date":
                    add_terminology_entry_to_category(element, category_terminology_entries, "date")
                else:
                    raise Exception(f"Unknown element {element['type'][0]['code']}")
    for category_entry in category_terminology_entries:
        category_entry.children = sorted(category_entry.children)
    return category_terminology_entries


def create_category_terminology_entry(category_entry):
    term_code = [TermCode("num.codex", category_entry.display, category_entry.display)]
    result = TerminologyEntry(term_code, "Category", leaf=False, selectable=False)
    result.path = category_entry.path
    return result


# element from Logical Model
def add_terminology_entry_to_category(element, categories, terminology_type):
    for category_entry in categories:
        # same path -> sub element of that category
        if category_entry.path in element["base"]["path"]:
            terminology_entry = TerminologyEntry(get_term_codes(element), terminology_type)
            # We use the english display to resolve after we switch to german.
            terminology_entry.display = element["short"]
            if terminology_entry.display in IGNORE_LIST:
                continue
            # TODO: Refactor don't do this here?!
            resolve_terminology_entry_profile(terminology_entry)
            if terminology_entry.terminologyType == "Quantity":
                terminology_entry.valueDefinition = get_value_definition(element)
                # FIXME: This is only a quick workaround for GasPanel values.
                for child in terminology_entry.children:
                    child.valueDefinition = get_value_definition(element)
            terminology_entry.display = get_german_display(element) if get_german_display(element) else element["short"]
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
                            if coding["system"] == "http://unitsofmeasure.org/" or \
                                    coding["system"] == "http://unitsofmeasure.org":
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


def resolve_terminology_entry_profile(terminology_entry, data_set=GECCO_DATA_SET):
    name = LOGICAL_MODEL_TO_PROFILE.get(to_upper_camel_case(terminology_entry.display)) \
        if to_upper_camel_case(terminology_entry.display) in LOGICAL_MODEL_TO_PROFILE else to_upper_camel_case(
        terminology_entry.display)
    for filename in os.listdir("%s" % data_set):
        if name in filename and "snapshot" in filename:
            with open(data_set + "/" + filename, encoding="UTF-8") as profile_file:
                profile_data = json.load(profile_file)
                if profile_data["kind"] == "logical":
                    continue
                if profile_data["name"] in corner_cases:
                    corner_cases.get(profile_data["name"])(profile_data, terminology_entry)
                elif profile_data["type"] in profile_translation_mapping:
                    profile_translation_mapping.get(profile_data["type"])(profile_data, terminology_entry)
                else:
                    raise UnknownHandlingException(profile_data["type"])


def translate_research_subject(_profile_data, _terminology_entry):
    pass


def translate_patient(profile_data, terminology_entry):
    terminology_entry.fhirMapperType = "Patient"
    terminology_entry.timeRestrictionAllowed = False
    terminology_entry.selectable = True
    terminology_entry.leaf = True
    gender_attribute_code = TermCode("num.abide", "gender", "Geschlecht")
    gender_attribute = AttributeDefinition(gender_attribute_code, "concept")
    gender_attribute.optional = False
    gender_attribute.selectableConcepts = (get_term_codes_by_path("Patient.gender", profile_data))
    terminology_entry.attributeDefinitions.append(gender_attribute)


def inherit_parent_attributes(terminology_entry):
    for child in terminology_entry.children:
        child.attributeDefinitions = terminology_entry.attributeDefinitions
        child.timeRestrictionAllowed = terminology_entry.timeRestrictionAllowed
        if child.children:
            inherit_parent_attributes(child)


def translate_specimen(profile_data, terminology_entry):
    terminology_entry.fhirMapperType = "Specimen"
    terminology_entry.display = "Bioprobe"
    status_attribute_code = TermCode("num.abide", "status", "Status")
    status_attribute_code = AttributeDefinition(attribute_code=status_attribute_code, value_type="concept")
    status_attribute_code.selectableConcepts = get_term_codes_by_path("Specimen.status", profile_data)
    terminology_entry.attributeDefinitions.append(status_attribute_code)
    body_site_attribute_code = TermCode("mii.module_specimen", "Specimen.collection.bodySite", "Entnahmeort")
    body_site_attribute = AttributeDefinition(attribute_code=body_site_attribute_code, value_type="concept")
    body_site_attribute.selectableConcepts = get_term_code_by_id("Specimen.collection.bodySite.coding:icd-o-3",
                                                                 profile_data)
    terminology_entry.attributeDefinitions.append(body_site_attribute)
    terminology_entry.children = get_termentries_from_onto_server(SPECIMEN_VS)
    terminology_entry.leaf = False
    # FIXME: BETTER HANDLING FOR "inheriting" parents attributes. By Normalizing.
    for child in terminology_entry.children:
        child.attributeDefinitions = terminology_entry.attributeDefinitions
        child.timeRestrictionAllowed = terminology_entry.timeRestrictionAllowed


def translate_substance(_profile_data, _terminology_entry):
    pass


def pattern_coding_to_termcode(element):
    code = element["patternCoding"]["code"]
    system = element["patternCoding"]["system"]
    display = get_term_code_display_from_onto_server(system, code)
    term_code = TermCode(system, code, display)
    return term_code


def parse_term_code(terminology_entry, element, path):
    if element["path"] == path and "patternCoding" in element:
        if "system" in element["patternCoding"] and "code" in element["patternCoding"]:
            term_code = pattern_coding_to_termcode(element)
            terminology_entry.termCodes.append(term_code)
            terminology_entry.termCode = term_code


def update_termcode_to_match_pattern_coding(terminology_entry, element):
    if terminology_entry.termCode.system == "num.codex":
        if element["path"] == "Observation.code.coding" and "patternCoding" in element:
            terminology_entry.termCode.code = element["patternCoding"]["code"]
            terminology_entry.termCode.system = element["patternCoding"]["system"]


# Ideally we would want to use [path] not the id, but using the id gives us control on which valueSet we want to use.
def get_term_entries_by_id(element_id, profile_data):
    value_set = ""
    for element in profile_data["snapshot"]["element"]:
        if "id" in element and element["id"] == element_id and "patternCoding" in element:
            if "code" in element["patternCoding"]:
                term_code = pattern_coding_to_termcode(element)
                return [TerminologyEntry([term_code], "CodeableConcept", leaf=True, selectable=True)]
        if "id" in element and element["id"] == element_id and "binding" in element:
            value_set = element["binding"]["valueSet"]
            return get_termentries_from_onto_server(value_set)
    if value_set:
        return get_termentries_from_onto_server(value_set)
    return []


def get_term_entries_by_path(element_path, profile_data):
    value_set = ""
    for element in profile_data["snapshot"]["element"]:
        if "path" in element and element["path"] == element_path and "patternCoding" in element:
            if "code" in element["patternCoding"]:
                term_code = pattern_coding_to_termcode(element)
                return [TerminologyEntry([term_code], "CodeableConcept", leaf=True, selectable=True)]
        if "path" in element and element["path"] == element_path and "binding" in element:
            value_set = element["binding"]["valueSet"]
            return get_termentries_from_onto_server(value_set)
    if value_set:
        return get_termentries_from_onto_server(value_set)
    return []


def get_term_code_by_id(element_id, profile_data):
    value_set = ""
    for element in profile_data["snapshot"]["element"]:
        if "id" in element and element["id"] == element_id and "patternCoding" in element:
            if "code" in element["patternCoding"]:
                term_code = pattern_coding_to_termcode(element)
                return [term_code]
        if "id" in element and element["id"] == element_id and "binding" in element:
            value_set = element["binding"]["valueSet"]
            return get_termcodes_from_onto_server(value_set)
    if value_set:
        return get_termcodes_from_onto_server(value_set)
    return []


def get_term_codes_by_path(element_path, profile_data):
    value_set = ""
    for element in profile_data["snapshot"]["element"]:
        if "path" in element and element["path"] == element_path and "patternCoding" in element:
            if "code" in element["patternCoding"]:
                term_code = pattern_coding_to_termcode(element)
                return [term_code]
        if "path" in element and element["path"] == element_path and "binding" in element:
            value_set = element["binding"]["valueSet"]
            return get_termcodes_from_onto_server(value_set)
    if value_set:
        return get_termcodes_from_onto_server(value_set)
    return []


def translate_condition(profile_data, terminology_entry):
    terminology_entry.fhirMapperType = "Condition"
    children = get_term_entries_by_id("Condition.code.coding:icd10-gm", profile_data)
    if children:
        terminology_entry.leaf = False
        terminology_entry.children += children


def translate_dependency_on_ventilator(profile_data, terminology_entry):
    terminology_entry.fhirMapperType = "Condition"
    children = get_term_entries_by_id("Condition.code.coding:sct", profile_data)
    if children:
        terminology_entry.leaf = False
        terminology_entry.children += children


def translate_diagnosis_covid_19(profile_data, terminology_entry):
    terminology_entry.fhirMapperType = "DiagnosisCovid19"
    stage_code = TermCode("num.abide", "stage", "Stadium")
    stage_attribute = AttributeDefinition(stage_code, "concept")
    stage_attribute.selectableConcepts = get_term_codes_by_path("Condition.stage.summary.coding", profile_data)
    terminology_entry.attributeDefinitions.append(stage_attribute)
    for element in profile_data["snapshot"]["element"]:
        parse_term_code(terminology_entry, element, "Condition.code.coding")


def translate_symptom(profile_data, terminology_entry):
    terminology_entry.fhirMapperType = "Symptom"
    # TODO: Refactor not hardcoded!
    severity_vs = "https://www.netzwerk-universitaetsmedizin.de/fhir/ValueSet/condition-severity"
    terminology_entry.children = get_term_entries_by_id("Condition.code.coding:sct", profile_data)
    terminology_entry.leaf = False
    severity_attribute_code = TermCode("num.abide", "severity", "Schweregrad")
    severity_attribute = AttributeDefinition(severity_attribute_code, "concept")
    severity_attribute.optional = False
    severity_attribute.selectableConcepts += get_termcodes_from_onto_server(severity_vs)
    terminology_entry.attributeDefinitions.append(severity_attribute)
    inherit_parent_attributes(terminology_entry)


def translate_medication_statement(profile_data, terminology_entry):
    terminology_entry.fhirMapperType = "MedicationStatement"
    terminology_entry.children = get_term_entries_by_path("MedicationStatement.medication[x].coding", profile_data)
    terminology_entry.leaf = False


def translate_medication_administration(_profile_data, terminology_entry):
    # This code is tailored for MedicationAdministration as defined in kerndatensatz.medikation
    # We use the Medication profile to get the codings referred to by the MedicationAdministration
    with open(MII_MEDICATION_DATA_SET + "/" + "Medication.StructureDefinition-snapshot.json", encoding="UTF-8") \
            as profile_file:
        medication_profile_data = json.load(profile_file)
        terminology_entry.display = "Medikamentenverabreichungen"
        terminology_entry.fhirMapperType = "MedicationAdministration"
        terminology_entry.children = get_term_entries_by_path("Medication.code.coding", medication_profile_data)
        terminology_entry.leaf = False
        terminology_entry.children = sorted(terminology_entry.children)


def is_concept_observation(profile_data):
    is_concept_value = False
    for element in profile_data["snapshot"]["element"]:
        if "type" in element:
            if element["path"] == "Observation.value[x]" and element["type"][0]["code"] == "CodeableConcept":
                return True
        if "sliceName" in element:
            if (element["path"] == "Observation.value[x]" and element["sliceName"] == "valueCodeableConcept") or \
                    (element["path"] == "Observation.value[x].coding"):
                return True
    return is_concept_value


def translate_observation(profile_data, terminology_entry):
    terminology_entry.leaf = True
    terminology_entry.selectable = True
    for element in profile_data["snapshot"]["element"]:
        update_termcode_to_match_pattern_coding(terminology_entry, element)
    if is_concept_observation(profile_data):
        terminology_entry.terminologyType = "Concept"
        terminology_entry.fhirMapperType = "ConceptObservation"
        value_definition = ValueDefinition("concept")
        if selectable_concepts := get_term_codes_by_path("Observation.value[x]", profile_data):
            value_definition.selectableConcepts = selectable_concepts
        else:
            value_definition.selectableConcepts = get_term_codes_by_path("Observation.value[x].coding", profile_data)
        terminology_entry.valueDefinition = value_definition
    else:
        terminology_entry.fhirMapperType = "QuantityObservation"
        terminology_entry.terminologyType = "Quantity"


def translate_gas_panel(profile_data, terminology_entry):
    for element in profile_data["snapshot"]["element"]:
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
            entry.fhirMapperType = "QuantityObservation"
            entry.valueDefinition = []
            terminology_entry.children.append(entry)
        terminology_entry.fhirMapperType = "QuantityObservation"
        terminology_entry.selectable = False
        terminology_entry.leaf = False
    else:
        # FIXME: Hacky Solution
        translate_top_300_loinc_codes(_profile_data, terminology_entry)


def translate_sofa(profile_data, terminology_entry):
    for element in profile_data["snapshot"]["element"]:
        update_termcode_to_match_pattern_coding(terminology_entry, element)
    terminology_entry.fhirMapperType = "Sofa"
    terminology_entry.selectable = True
    terminology_entry.leaf = True
    terminology_entry.terminologyType = "Quantity"


def translate_procedure(profile_data, terminology_entry):
    terminology_entry.fhirMapperType = "Procedure"
    sct_children = get_term_entries_by_id("Procedure.code.coding:sct", profile_data)
    if sct_children and not terminology_entry.display == "ECMO therapy" and not terminology_entry.display == "Prozedur":
        terminology_entry.children = sct_children
    else:
        ops_children = get_term_entries_by_id("Procedure.code.coding:ops", profile_data)
        terminology_entry.children = ops_children
    terminology_entry.leaf = False


def translate_immunization(profile_data, terminology_entry):
    terminology_entry.fhirMapperType = "Immunization"
    terminology_entry.children = get_term_entries_by_id("Immunization.vaccineCode.coding:snomed", profile_data)
    terminology_entry.leaf = False
    terminology_entry.selectable = False


def translate_ethnic_group(profile_data, terminology_entry):
    terminology_entry.fhirMapperType = "EthnicGroup"
    value_definition = ValueDefinition("concept")
    value_definition.selectableConcepts += get_term_codes_by_path("Extension.value[x]", profile_data)
    terminology_entry.valueDefinition = value_definition


def translate_age(_profile_data, terminology_entry):
    terminology_entry.fhirMapperType = "Age"


def translate_diagnostic_report(profile_data, terminology_entry):
    terminology_entry.fhirMapperType = "DiagnosticReport"
    value_definition = ValueDefinition("concept")
    value_definition.selectableConcepts = get_term_codes_by_path("DiagnosticReport.conclusionCode", profile_data)
    terminology_entry.valueDefinition = value_definition


# TODO
def translate_consent(profile_data, terminology_entry):
    terminology_entry.fhirMapperType = "Consent"
    terminology_entry.selectable = True
    terminology_entry.leaf = True
    for element in profile_data["snapshot"]["element"]:
        if element["id"] == "Consent.provision.code":
            if "binding" in element:
                value_set = element["binding"]["valueSet"]
                value_definition = ValueDefinition("concept")
                value_definition.selectableConcepts += get_termcodes_from_onto_server(value_set)
                terminology_entry.valueDefinition = value_definition
                break


def translate_resuscitation(profile_data, terminology_entry):
    terminology_entry.fhirMapperType = "ResuscitationStatus"
    terminology_entry.selectable = True
    terminology_entry.leaf = True
    for element in profile_data["snapshot"]["element"]:
        if element["id"] == "Consent.category.coding.system":
            terminology_entry.termCode.system = element["fixedUri"]
        if element["id"] == "Consent.category.coding.code":
            terminology_entry.termCode.code = element["fixedCode"]
        if element["id"] == "Consent.provision.code":
            if "binding" in element:
                value_set = element["binding"]["valueSet"]
                value_definition = ValueDefinition("concept")
                value_definition.selectableConcepts += get_termcodes_from_onto_server(value_set)
                terminology_entry.valueDefinition = value_definition
                break


def translate_blood_pressure(_profile_data, terminology_entry):
    terminology_entry.fhirMapperType = "BloodPressure"


def translate_history_of_travel(profile_data, terminology_entry):
    terminology_entry.fhirMapperType = "HistoryOfTravel"
    value_definition = ValueDefinition("concept")
    value_definition.selectableConcepts = get_term_codes_by_path("Observation.component:Country.value[x]", profile_data)
    terminology_entry.valueDefinition = value_definition


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
            consent_child.valueDefinition = value_definition
            consent_category_entry.children.append(consent_child)
    return consent_category_entry


# TODO duplicated code in valueSetToRoots
def get_term_code_display_from_onto_server(system, code):
    response = requests.get(f"{ONTOLOGY_SERVER_ADDRESS}CodeSystem/$lookup?system={system}&code={code}")
    if response.status_code == 200:
        response_data = response.json()
        for parameter in response_data["parameter"]:
            if name := parameter.get("name"):
                if name == "display":
                    return parameter.get("valueString") if parameter.get("valueString") else ""
    return ""


def value_set_json_to_term_code_set(response):
    term_codes = set()
    if response.status_code == 200:
        value_set_data = response.json()
        if "expansion" in value_set_data and "contains" in value_set_data["expansion"]:
            for contains in value_set_data["expansion"]["contains"]:
                system = contains["system"]
                code = contains["code"]
                display = contains["display"]
                version = None
                if "version" in contains:
                    version = contains["version"]
                term_code = TermCode(system, code, display, version)
                term_codes.add(term_code)
    return term_codes


def get_termentries_from_onto_server(canonical_address_value_set):
    if canonical_address_value_set in ["https://www.medizininformatik-initiative.de/fhir/core/modul-diagnose/ValueSet" \
                                       "/diagnoses-sct",
                                       "https://www.medizininformatik-initiative.de/fhir/core/modul-prozedur/ValueSet/procedures-sct"]:
        return []
    canonical_address_value_set = canonical_address_value_set.replace("|", "&version=")
    print(canonical_address_value_set)
    # In Gecco 1.04 all icd10 elements with children got removed this brings them back. Requires matching valuesets on
    # Ontoserver
    if canonical_address_value_set.endswith("icd"):
        canonical_address_value_set = canonical_address_value_set + "-with-parent"
    result = create_vs_tree(canonical_address_value_set)
    if len(result) < 1:
        print("ERROR", canonical_address_value_set)
    return result


# TODO: We only want to use a single coding system. The different coding systems need to be prioritized
def get_termcodes_from_onto_server(canonical_address_value_set):
    canonical_address_value_set = canonical_address_value_set.replace("|", "&version=")
    print(canonical_address_value_set)
    icd10_result = []
    snomed_result = []
    result = []
    response = requests.get(
        f"{ONTOLOGY_SERVER_ADDRESS}ValueSet/$expand?url={canonical_address_value_set}&includeDesignations=true")
    if response.status_code == 200:
        value_set_data = response.json()
        if "contains" in value_set_data["expansion"]:
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
            return []
    else:
        print(f"{canonical_address_value_set} is empty")
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


def translate_top_300_loinc_codes(_profile_data, terminology_entry):
    top_loinc_tree = etree.parse("Top300Loinc.xml")
    lab_root = get_terminology_entry_from_top_300_loinc("11ccdc84-a237-49a5-860a-b0f65068c023", top_loinc_tree)
    terminology_entry.children.append(lab_root)
    terminology_entry.leaf = False
    terminology_entry.selectable = False


def get_terminology_entry_from_top_300_loinc(element_id, element_tree):
    # TODO: Bettter namespace handling
    coding_system = ""
    code = ""
    display = ""
    terminology_entry = None
    for element in element_tree.xpath("/xmlns:export/xmlns:scopedIdentifier",
                                      namespaces={'xmlns': "http://schema.samply.de/mdr/common"}):
        if element.get("uuid") == element_id:
            for definition in element.xpath("xmlns:definitions/xmlns:definition",
                                            namespaces={'xmlns': "http://schema.samply.de/mdr/common"}):
                if definition.get("lang") == "de":
                    for designation in (
                            definition.xpath("xmlns:designation",
                                             namespaces={'xmlns': "http://schema.samply.de/mdr/common"})):
                        display = designation.text
                if not display and definition.get("lang") == "en":
                    for designation in (
                            definition.xpath("xmlns:designation",
                                             namespaces={'xmlns': "http://schema.samply.de/mdr/common"})):
                        display = designation.text
            if subs := element.xpath("xmlns:sub", namespaces={'xmlns': "http://schema.samply.de/mdr/common"}):
                term_code = TermCode("nun.abide", display, display)
                terminology_entry = TerminologyEntry([term_code])
                for sub in subs:
                    terminology_entry.children.append(get_terminology_entry_from_top_300_loinc(sub.text, element_tree))
                    terminology_entry.leaf = False
                    terminology_entry.selectable = False
                return terminology_entry
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
            term_code = TermCode(coding_system, code, display)
            terminology_entry = TerminologyEntry([term_code])
            for child in element:
                if child.tag == "{http://schema.samply.de/mdr/common}element":
                    terminology_entry.valueDefinition = get_value_description_from_top_300_loinc(child.text,
                                                                                                 element_tree)
    return terminology_entry


def get_value_description_from_top_300_loinc(element_id, element_tree):
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
                        break
                    unit = Unit(child.text, child.text)
                    value_definition = ValueDefinition("quantity")
                    value_definition.allowedUnits.append(unit)
                    return value_definition


def do_nothing(_profile_data, _terminology_entry):
    pass


profile_translation_mapping = {
    "date": do_nothing,
    "Extension": do_nothing,

    "Condition": translate_condition,
    "Consent": translate_consent,
    "DiagnosticReport": translate_diagnostic_report,
    "Immunization": translate_immunization,
    "MedicationStatement": translate_medication_statement,
    "MedicationAdministration": translate_medication_administration,
    "Observation": translate_observation,
    "Patient": translate_patient,
    "Procedure": translate_procedure,
    "ResearchSubject": translate_research_subject,
    "Specimen": translate_specimen,
    "Substance": translate_substance,
}

corner_cases = {
    "Age": translate_age,
    "BloodPressure": translate_blood_pressure,
    "DependenceOnVentilator": translate_dependency_on_ventilator,
    "DiagnosisCovid19": translate_diagnosis_covid_19,
    "DoNotResuscitateOrder": translate_resuscitation,
    "EthnicGroup": translate_ethnic_group,
    "HistoryOfTravel": translate_history_of_travel,
    "ProfileObservationLaboruntersuchung": translate_laboratory_values,
    "PaCO2": translate_gas_panel,
    "SOFA": translate_sofa,
    "SymptomsCovid19": translate_symptom
}


def translate_chronic_lung_diseases_with_duplicates(profile_data, terminology_entry):
    terminology_entry.fhirMapperType = "Condition"
    icd_code = TermCode("num.abide", "icd10-gm-concepts", "ICD10 Konzepte")
    icd_logical = TerminologyEntry([icd_code], selectable=False, leaf=False)
    icd_logical.children = get_term_entries_by_id("Condition.code.coding:icd10-gm", profile_data)
    terminology_entry.children.append(icd_logical)
    sct_code = TermCode("num.abide", "sct-concepts", "SNOMED CT Konzepte")
    sct_logical_entry = TerminologyEntry([sct_code], selectable=False, leaf=False)
    sct_logical_entry.children = get_term_entries_by_id("Condition.code.coding:sct", profile_data)
    terminology_entry.children.append(sct_logical_entry)
    terminology_entry.leaf = False


def translate_radiology_procedures_with_duplicates(profile_data, terminology_entry):
    terminology_entry.fhirMapperType = "Procedure"
    terminology_entry.children += get_term_entries_by_id("Procedure.code.coding:sct", profile_data)
    terminology_entry.children += get_term_entries_by_id("Procedure.code.coding:dicom", profile_data)
    terminology_entry.leaf = False


if GENERATE_DUPLICATES:
    corner_cases["ChronicLungDiseases"] = translate_chronic_lung_diseases_with_duplicates
    corner_cases["RadiologyProcedures"] = translate_radiology_procedures_with_duplicates
