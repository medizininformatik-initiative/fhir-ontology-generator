import os

from lxml import etree

import csv
from FHIRProfileConfiguration import *
from LogicalModelToProfile import LOGICAL_MODEL_TO_PROFILE
from TerminologService.ValueSetResolver import get_term_entries_from_onto_server, \
    get_term_entries_by_id, get_term_entries_by_path, pattern_coding_to_termcode
from TerminologService.icd10MortalityDownloader import download_sonderverzeichnis_mortality
from helper import to_upper_camel_case
from model.Exceptions import UnknownHandlingException
from model.UIProfileModel import *
from model.UiDataModel import *

IGNORE_CATEGORIES = []

MAIN_CATEGORIES = ["Einwilligung", "Bioproben"]

GENERATE_DUPLICATES = os.getenv("GENERATE_DUPLICATES", 'False').lower() == "true"


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
    name = LOGICAL_MODEL_TO_PROFILE.get(to_upper_camel_case(terminology_entry.display)) \
        if to_upper_camel_case(terminology_entry.display) in LOGICAL_MODEL_TO_PROFILE else to_upper_camel_case(
        terminology_entry.display)
    for filename in os.listdir("%s" % data_set):
        if name in filename and "snapshot" in filename:
            with open(data_set + "/" + filename, encoding="UTF-8") as profile_file:
                profile_data = json.load(profile_file)
                if is_logical_or_bundle(profile_data):
                    continue
                # We differentiate between corner and none corner cases only for readability.
                if profile_data["name"] in corner_cases:
                    corner_cases.get(profile_data["name"])(profile_data, terminology_entry, element)
                elif profile_data["type"] in profile_translation_mapping:
                    profile_translation_mapping.get(profile_data["type"])(profile_data, terminology_entry, element)
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


def inherit_parent_attributes(terminology_entry):
    for child in terminology_entry.children:
        child.fhirMapperType = terminology_entry.fhirMapperType
        child.uiProfile = terminology_entry.uiProfile
        if child.children:
            inherit_parent_attributes(child)


def parse_term_code(terminology_entry, element, path):
    if element["path"] == path and "patternCoding" in element:
        if "system" in element["patternCoding"] and "code" in element["patternCoding"]:
            term_code = pattern_coding_to_termcode(element)
            terminology_entry.termCodes.append(term_code)
            terminology_entry.termCode = term_code


def update_termcode_to_match_pattern_coding(terminology_entry, element):
    if terminology_entry.termCode.system == "mii.abide":
        if element["path"] == "Observation.code.coding" and "patternCoding" in element:
            terminology_entry.termCode.code = element["patternCoding"]["code"]
            terminology_entry.termCode.system = element["patternCoding"]["system"]


def translate_age(profile_data, terminology_entry, logical_element):
    terminology_entry.fhirMapperType = "Age"
    terminology_entry.uiProfile = generate_age_ui_profile(profile_data, logical_element)


def translate_blood_pressure(profile_data, terminology_entry, logical_element):
    terminology_entry.fhirMapperType = "BloodPressure"
    terminology_entry.uiProfile = generate_quantity_observation_ui_profile(profile_data, logical_element)


def translate_cause_of_death(profile_data, terminology_entry, _logical_element):
    # TODO: Corner case. Requires new Mapping Type
    terminology_entry.fhirMapperType = "Condition"
    terminology_entry.uiProfile = generate_default_ui_profile(profile_data["name"], _logical_element)
    children = download_sonderverzeichnis_mortality()
    if children:
        terminology_entry.leaf = False
        terminology_entry.children += children
        inherit_parent_attributes(terminology_entry)


def translate_condition(profile_data, terminology_entry, _logical_element):
    element_id = "Condition.code.coding:icd10-gm"
    terminology_entry.fhirMapperType = "Condition"
    terminology_entry.uiProfile = generate_default_ui_profile(profile_data["name"], _logical_element)
    children = get_term_entries_by_id(element_id, profile_data)
    if children:
        terminology_entry.leaf = False
        terminology_entry.children += children
        inherit_parent_attributes(terminology_entry)


def translate_consent(profile_data, terminology_entry, _logical_element):
    terminology_entry.fhirMapperType = "Consent"
    terminology_entry.uiProfile = generate_consent_ui_profile(profile_data, _logical_element)


def translate_dependency_on_ventilator(profile_data, terminology_entry, _logical_element):
    element_id = "Condition.code.coding:sct"
    terminology_entry.fhirMapperType = "Condition"
    terminology_entry.uiProfile = generate_default_ui_profile(profile_data["name"], _logical_element)
    children = get_term_entries_by_id(element_id, profile_data)
    if children:
        terminology_entry.leaf = False
        terminology_entry.children += children
        inherit_parent_attributes(terminology_entry)


def translate_diagnosis_covid_19(profile_data, terminology_entry, _logical_element):
    terminology_entry.fhirMapperType = "DiagnosisCovid19"
    terminology_entry.uiProfile = generate_diagnosis_covid_19_ui_profile(profile_data, _logical_element)
    for element in profile_data["snapshot"]["element"]:
        parse_term_code(terminology_entry, element, "Condition.code.coding")


def translate_diagnostic_report(profile_data, terminology_entry, _logical_element):
    terminology_entry.fhirMapperType = "DiagnosticReport"
    terminology_entry.uiProfile = generate_diagnostic_report_ui_profile(profile_data, _logical_element)


def translate_ethnic_group(profile_data, terminology_entry, _logical_element):
    terminology_entry.fhirMapperType = "EthnicGroup"
    terminology_entry.uiProfile = generate_ethnic_group_ui_profile(profile_data, _logical_element)


def translate_gas_panel(profile_data, terminology_entry, logical_element):
    for element in profile_data["snapshot"]["element"]:
        if element["path"] == "Observation.code.coding" and "patternCoding" in element:
            term_code = TermCode(element["patternCoding"]["system"], element["patternCoding"]["code"],
                                 element["sliceName"])
            child = TermEntry([term_code], "Quantity", leaf=True, selectable=True)
            terminology_entry.children.append(child)
    terminology_entry.leaf = False
    terminology_entry.selectable = False
    terminology_entry.fhirMapperType = "QuantityObservation"
    terminology_entry.uiProfile = generate_default_ui_profile(profile_data["name"], logical_element)
    for child in terminology_entry.children:
        child.uiProfile = generate_quantity_observation_ui_profile(profile_data, logical_element)


def translate_history_of_travel(profile_data, terminology_entry, _logical_element):
    terminology_entry.fhirMapperType = "HistoryOfTravel"
    terminology_entry.uiProfile = generate_history_of_travel_ui_profile(profile_data, _logical_element)


def translate_immunization(profile_data, terminology_entry, _logical_element):
    terminology_entry.fhirMapperType = "Immunization"
    terminology_entry.uiProfile = generate_default_ui_profile(profile_data["name"], _logical_element)
    terminology_entry.children = get_term_entries_by_id("Immunization.vaccineCode.coding:snomed", profile_data)
    terminology_entry.leaf = False
    terminology_entry.selectable = False
    inherit_parent_attributes(terminology_entry)


def translate_laboratory_values(profile_data, terminology_entry, logical_element):
    if terminology_entry.terminologyType == "Quantity":
        for code in terminology_entry.termCodes:
            entry = TermEntry([code], terminology_entry.terminologyType)
            entry.fhirMapperType = "QuantityObservation"
            entry.uiProfile = generate_quantity_observation_ui_profile(profile_data, logical_element)
            terminology_entry.children.append(entry)
        terminology_entry.fhirMapperType = "QuantityObservation"
        terminology_entry.selectable = False
        terminology_entry.leaf = False
    else:
        # FIXME: Hacky Solution
        translate_top_300_loinc_codes(profile_data, terminology_entry)


def translate_medication_administration(profile_data, terminology_entry, _logical_element):
    # This code is tailored for MedicationAdministration as defined in kerndatensatz.medikation
    # We use the Medication profile to get the codings referred to by the MedicationAdministration
    with open(MII_MEDICATION_DATA_SET + "/" + "Medication.StructureDefinition-snapshot.json", encoding="UTF-8") \
            as profile_file:
        medication_profile_data = json.load(profile_file)
        terminology_entry.display = "Medikamentenverabreichungen"
        terminology_entry.fhirMapperType = "MedicationAdministration"
        terminology_entry.uiProfile = generate_default_ui_profile(profile_data["name"], _logical_element)
        terminology_entry.children = get_term_entries_by_path("Medication.code.coding", medication_profile_data)
        terminology_entry.leaf = False
        terminology_entry.children = sorted(terminology_entry.children)
        inherit_parent_attributes(terminology_entry)


def translate_medication_statement(profile_data, terminology_entry, _logical_element):
    terminology_entry.fhirMapperType = "MedicationStatement"
    terminology_entry.uiProfile = generate_default_ui_profile(profile_data["name"], _logical_element)
    terminology_entry.children = get_term_entries_by_path("MedicationStatement.medication[x].coding", profile_data)
    inherit_parent_attributes(terminology_entry)
    terminology_entry.leaf = False


def translate_observation(profile_data, terminology_entry, logical_element):
    terminology_entry.leaf = True
    terminology_entry.selectable = True
    for element in profile_data["snapshot"]["element"]:
        update_termcode_to_match_pattern_coding(terminology_entry, element)
    if is_concept_observation(profile_data):
        terminology_entry.fhirMapperType = "ConceptObservation"
        terminology_entry.uiProfile = generate_concept_observation_ui_profile(profile_data, logical_element)
    else:
        terminology_entry.fhirMapperType = "QuantityObservation"
        terminology_entry.uiProfile = generate_quantity_observation_ui_profile(profile_data, logical_element)


def is_concept_observation(profile_data):
    is_concept_value = False
    for element in profile_data["snapshot"]["element"]:
        # ToDo: This is awfully implemented in the Profiles, once they fixed this issue, this first if clause can be
        #  removed
        if "id" in element and element["id"] == "Observation.value[x]:valueCodeableConcept":
            if element["max"] == "0":
                return False
        if "type" in element:
            if element["path"] == "Observation.value[x]" and element["type"][0]["code"] == "CodeableConcept":
                return True
        if "sliceName" in element:
            if (element["path"] == "Observation.value[x]" and element["sliceName"] == "valueCodeableConcept") or \
                    (element["path"] == "Observation.value[x].coding"):
                return True
    return is_concept_value


def translate_patient(profile_data, terminology_entry, _logical_element):
    # Care if we make attributes children we cannot use inherit_parent_attributes! nor can we use a single ui-profile.

    def get_age_entry():
        age_code = TermCode("mii.abide", "age", "Alter")
        age_entry = TermEntry([age_code])
        age_entry.fhirMapperType = "Patient"
        age_entry.uiProfile = generate_age_kds_ui_profile(profile_data, _logical_element)
        return age_entry

    def get_gender_entry():
        gender_code = TermCode("mii.abide", "gender", "Geschlecht")
        gender_entry = TermEntry([gender_code])
        gender_entry.fhirMapperType = "Patient"
        gender_entry.uiProfile = generate_gender_ui_profile(profile_data, _logical_element)
        return gender_entry

    terminology_entry.fhirMapperType = "Patient"
    terminology_entry.selectable = False
    terminology_entry.leaf = False
    terminology_entry.children.append(get_age_entry())
    terminology_entry.children.append(get_gender_entry())


def translate_procedure(profile_data, terminology_entry, _logical_element):
    terminology_entry.fhirMapperType = "Procedure"
    terminology_entry.uiProfile = generate_default_ui_profile(profile_data["name"], _logical_element)
    sct_children = get_term_entries_by_id("Procedure.code.coding:sct", profile_data)
    if sct_children and not terminology_entry.display == "ECMO therapy" and not terminology_entry.display == "Prozedur":
        terminology_entry.children = sct_children
    else:
        ops_children = get_term_entries_by_id("Procedure.code.coding:ops", profile_data)
        terminology_entry.children = ops_children
    inherit_parent_attributes(terminology_entry)
    terminology_entry.leaf = False


def translate_research_subject(_profile_data, _terminology_entry, _logical_element):
    pass


def translate_resuscitation(profile_data, terminology_entry, _logical_element):
    terminology_entry.fhirMapperType = "ResuscitationStatus"
    for element in profile_data["snapshot"]["element"]:
        if element["id"] == "Consent.category.coding.system":
            terminology_entry.termCode.system = element["fixedUri"]
        if element["id"] == "Consent.category.coding.code":
            terminology_entry.termCode.code = element["fixedCode"]
    terminology_entry.uiProfile = generate_consent_ui_profile(profile_data, _logical_element)


def translate_sofa(profile_data, terminology_entry, logical_element):
    for element in profile_data["snapshot"]["element"]:
        update_termcode_to_match_pattern_coding(terminology_entry, element)
    terminology_entry.fhirMapperType = "Sofa"
    terminology_entry.uiProfile = generate_quantity_observation_ui_profile(profile_data, logical_element)


def translate_specimen(profile_data, terminology_entry, _logical_element):
    terminology_entry.fhirMapperType = "Specimen"
    terminology_entry.uiProfile = generate_specimen_ui_profile(profile_data, _logical_element)
    terminology_entry.display = "Bioprobe"
    terminology_entry.children = get_term_entries_from_onto_server(SPECIMEN_VS)
    terminology_entry.leaf = False
    inherit_parent_attributes(terminology_entry)


def translate_substance(_profile_data, _terminology_entry, _logical_element):
    pass


def translate_symptom(profile_data, terminology_entry, _logical_element):
    terminology_entry.fhirMapperType = "Symptom"
    terminology_entry.uiProfile = generate_symptom_ui_profile(profile_data, _logical_element)
    terminology_entry.children = get_term_entries_by_id("Condition.code.coding:sct", profile_data)
    terminology_entry.leaf = False
    inherit_parent_attributes(terminology_entry)


def translate_top_300_loinc_codes(_profile_data, terminology_entry):
    top_loinc_tree = etree.parse("Top300Loinc.xml")
    terminology_entry.fhirMapperType = "QuantityObservation"
    terminology_entry.children = sorted(get_terminology_entry_from_top_300_loinc("11ccdc84-a237-49a5-860a-b0f65068c023",
                                                                                 top_loinc_tree).children)
    terminology_entry.leaf = False
    terminology_entry.selectable = False


def get_specimen():
    specimen_term_code = TermCode("mii.abide", "Bioproben", "Bioproben")
    specimen_category_entry = TermEntry([specimen_term_code], "Category", selectable=False, leaf=False)
    specimen_category_entry.fhirMapperType = "Specimen"

    with open('SpecimenCodes_clean.csv', mode='r') as csv_file:
        csv_reader = csv.DictReader(csv_file, delimiter=",")
        for row in csv_reader:
            term_code = TermCode(row["System"], row["Code"], row["Display"])
            specimen_child = TermEntry([term_code], "CodeableConcept", selectable=True, leaf=True)
            specimen_child.fhirMapperType = "Specimen"
            specimen_child.display = row["Display"]
            ui_profile = UIProfile("Bioprobe")
            # status_attribute_code = TermCode("mii.abide", "status", "Status")
            # status_attribute_code = AttributeDefinition(attribute_code=status_attribute_code, value_type="concept")
            # status_attribute_code.selectableConcepts = get_term_codes_by_path("Specimen.status", profile_data)
            # ui_profile.attributeDefinitions.append(status_attribute_code)
            body_site_attribute_code = TermCode("mii.module_specimen", "Specimen.collection.bodySite", "Entnahmeort")
            body_site_attribute = AttributeDefinition(attribute_code=body_site_attribute_code, value_type="concept")
            body_site_attribute.selectableConcepts = get_termcodes_from_onto_server(
                "https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/ValueSet/icd-o-3-topography")
            ui_profile.attributeDefinitions.append(body_site_attribute)
            UI_PROFILES.add(ui_profile)
            specimen_child.uiProfile = ui_profile
            specimen_category_entry.children.append(specimen_child)
    return specimen_category_entry


def get_consent():
    consent_term_code = TermCode("mii.abide", "Einwilligung", "Einwilligung")
    consent_category_entry = TermEntry([consent_term_code], "Category", selectable=False, leaf=False)
    consent_category_entry.fhirMapperType = "Consent"
    with open('CONSENT_PROVISIONS.CSV', mode='r', encoding="utf-8") as csv_file:
        csv_reader = csv.DictReader(csv_file, delimiter=";")
        for row in csv_reader:
            term_code = TermCode(row["System"], row["Code"], row["Display"])
            consent_child = TermEntry([term_code], "CodeableConcept", selectable=True, leaf=True)
            consent_child.fhirMapperType = "Consent"
            consent_child.display = row["guiDisplay"]
            value_definition = ValueDefinition("concept")
            value_definition.selectableConcepts.append(
                TermCode("http://hl7.org/fhir/consent-provision-type", "permit", "permit"))
            value_definition.selectableConcepts.append(
                TermCode("http://hl7.org/fhir/consent-provision-type", "deny", "deny"))
            ui_profile = generate_default_ui_profile("Einwilligung", None)
            ui_profile.valueDefinition = value_definition

            consent_child.uiProfile = ui_profile
            consent_category_entry.children.append(consent_child)
    return consent_category_entry


def get_german_display_from_designation(contains):
    if "designation" in contains:
        for designation in contains["designation"]:
            if "language" in designation and designation["language"] == "de-DE":
                return designation["value"]
    return None


def get_terminology_entry_from_top_300_loinc(element_id, element_tree):
    # TODO: Better namespace handling
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
                terminology_entry = TermEntry([term_code])
                for sub in subs:
                    terminology_entry.children.append(get_terminology_entry_from_top_300_loinc(sub.text, element_tree))
                    terminology_entry.leaf = False
                    terminology_entry.selectable = False
                terminology_entry.children = sorted(terminology_entry.children)
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
            terminology_entry = TermEntry([term_code])
            for child in element:
                if child.tag == "{http://schema.samply.de/mdr/common}element":
                    terminology_entry.uiProfile = generate_top300_loinc_ui_profile(terminology_entry, child.text,
                                                                                   element_tree)
                    # TODO: Refactor!
                    if terminology_entry.uiProfile.valueDefinition:
                        if terminology_entry.uiProfile.valueDefinition.type == "concept":
                            terminology_entry.fhirMapperType = "ConceptObservation"
                        elif terminology_entry.uiProfile.valueDefinition.type == "QuantityObservation":
                            terminology_entry.fhirMapperType = "QuantityObservation"
    return terminology_entry


def do_nothing(_profile_data, _terminology_entry, _element):
    pass


profile_translation_mapping = {
    "date": do_nothing,
    "Extension": do_nothing,
    "Organization": do_nothing,
    "OrganizationAffiliation": do_nothing,

    "Condition": translate_condition,
    "Consent": translate_consent,
    "DiagnosticReport": translate_diagnostic_report,
    "Immunization": translate_immunization,
    "MedicationAdministration": translate_medication_administration,
    "MedicationStatement": translate_medication_statement,
    "Observation": translate_observation,
    "Patient": translate_patient,
    "Procedure": translate_procedure,
    "ResearchSubject": translate_research_subject,
    "Specimen": do_nothing,
    "Substance": translate_substance
}

corner_cases = {
    "Age": translate_age,
    "BloodPressure": translate_blood_pressure,
    "DependenceOnVentilator": translate_dependency_on_ventilator,
    "DiagnosisCovid19": translate_diagnosis_covid_19,
    "DoNotResuscitateOrder": translate_resuscitation,
    "EthnicGroup": translate_ethnic_group,
    "HistoryOfTravel": translate_history_of_travel,
    "PaCO2": translate_gas_panel,
    "PaO2": translate_gas_panel,
    "PH": translate_gas_panel,
    "ProfileConditionTodesursache": translate_cause_of_death,
    "ProfileObservationLaboruntersuchung": translate_laboratory_values,
    "SOFA": translate_sofa,
    "SymptomsCovid19": translate_symptom
}


def translate_chronic_lung_diseases_with_duplicates(profile_data, terminology_entry, _logical_element):
    terminology_entry.fhirMapperType = "Condition"
    icd_code = TermCode("mii.abide", "icd10-gm-concepts", "ICD10 Konzepte")
    icd_logical = TermEntry([icd_code], selectable=False, leaf=False)
    icd_logical.children = get_term_entries_by_id("Condition.code.coding:icd10-gm", profile_data)
    terminology_entry.children.append(icd_logical)
    sct_code = TermCode("mii.abide", "sct-concepts", "SNOMED CT Konzepte")
    sct_logical_entry = TermEntry([sct_code], selectable=False, leaf=False)
    sct_logical_entry.children = get_term_entries_by_id("Condition.code.coding:sct", profile_data)
    terminology_entry.children.append(sct_logical_entry)
    terminology_entry.uiProfile = generate_default_ui_profile(profile_data["name"], _logical_element)
    inherit_parent_attributes(terminology_entry)
    terminology_entry.leaf = False


def translate_radiology_procedures_with_duplicates(profile_data, terminology_entry, _logical_element):
    terminology_entry.fhirMapperType = "Procedure"
    terminology_entry.children += get_term_entries_by_id("Procedure.code.coding:sct", profile_data)
    terminology_entry.children += get_term_entries_by_id("Procedure.code.coding:dicom", profile_data)
    terminology_entry.uiProfile = generate_default_ui_profile(profile_data["name"], _logical_element)
    inherit_parent_attributes(terminology_entry)
    terminology_entry.leaf = False


if GENERATE_DUPLICATES:
    corner_cases["ChronicLungDiseases"] = translate_chronic_lung_diseases_with_duplicates
    corner_cases["RadiologyProcedures"] = translate_radiology_procedures_with_duplicates
