import os
import requests
import csv
from lxml import etree
from UiDataModel import *
from LogicalModelToProfile import LOGICAL_MODEL_TO_PROFILE
from valueSetToRoots import create_vs_tree

GECCO_DATA_SET = "core_data_sets/de.gecco#1.0.5/package"
MII_MEDICATION_DATA_SET = "core_data_sets/de.medizininformatikinitiative.kerndatensatz.medikation#1.0.10/package"

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
                    add_category(categories, element)
            except KeyError:
                pass
        return categories


def add_category(categories, element):
    for extension in element["_short"]["extension"]:
        for nested_extension in extension["extension"]:
            if "valueMarkdown" in nested_extension:
                categories.append(CategoryEntry(str(uuid.uuid4()),
                                                nested_extension["valueMarkdown"],
                                                element["base"]["path"]))


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
                if terminology_entry.display == "Age":
                    print(get_value_definition(element).allowedUnits)
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
            break


def get_term_codes(element):
    # TODO: CHECK IF WE SHOULD ALWAYS USE NUM CODES HERE!
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


# One giant switch case for all possible Profiles
def resolve_terminology_entry_profile(terminology_entry, data_set=GECCO_DATA_SET):
    name = LOGICAL_MODEL_TO_PROFILE.get(to_upper_camel_case(terminology_entry.display)) \
        if to_upper_camel_case(terminology_entry.display) in LOGICAL_MODEL_TO_PROFILE else to_upper_camel_case(
        terminology_entry.display)
    found = False
    for filename in os.listdir("%s" % data_set):
        if name in filename and "snapshot" in filename:
            found = True
            with open(data_set + "/" + filename, encoding="UTF-8") as profile_file:
                profile_data = json.load(profile_file)
                if profile_data["kind"] == "logical":
                    continue
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
                        if data_set == GECCO_DATA_SET:
                            translate_laboratory_values(profile_data, terminology_entry)
                        else:
                            translate_top_300_loinc_codes(profile_data, terminology_entry)
                    elif name == "BloodPressure":
                        translate_blood_pressure(profile_data, terminology_entry)
                    elif name == "HistoryOfTravel":
                        translate_history_of_travel(profile_data, terminology_entry)
                    elif profile_data["name"] == "PaCO2" or profile_data["name"] == "PaO2" or \
                            profile_data["name"] == "PH":
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
                elif profile_data["type"] == "MedicationAdministration":
                    translate_medication_administration(profile_data, terminology_entry)
                elif profile_data["type"] == "Organization":
                    translate_organization(profile_data, terminology_entry)
                elif profile_data["type"] == "Specimen":
                    translate_specimen(profile_data, terminology_entry)
                elif profile_data["type"] == "Substance":
                    translate_substance(profile_data, terminology_entry)
                elif profile_data["type"] == "Encounter":
                    translate_encounter(profile_data, terminology_entry)
                elif profile_data["type"] == "ServiceRequest":
                    translate_service_request(profile_data, terminology_entry)
                elif profile_data["type"] == "Patient":
                    translate_patient(profile_data, terminology_entry)
                elif profile_data["type"] == "ResearchSubject":
                    translate_research_subject(profile_data, terminology_entry)
                elif profile_data["type"] == "Extension":
                    continue
                else:
                    raise UnknownHandlingException(profile_data["type"])
        elif name in filename and filename.startswith("Extension"):  #
            found = True
            with open(data_set + "/" + filename) as profile_file:
                profile_data = json.load(profile_file)
                if filename == "Extension-EthnicGroup.json":
                    translate_ethnic_group(profile_data, terminology_entry)
                elif filename == "Extension-Age.json":
                    translate_age(profile_data, terminology_entry)
    if not found:
        print(to_upper_camel_case(terminology_entry.display) + " Not found! " + data_set)


def translate_research_subject(_profile_data, _terminology_entry):
    pass


def translate_patient(profile_data, terminology_entry):
    terminology_entry.fhirMapperType = "Patient"
    terminology_entry.leaf = True
    terminology_entry.selectable = True
    # TODO: This will be attributes!
    for element in profile_data["snapshot"]["element"]:
        if element["path"] == "Patient.gender":
            print("GENDER")
            value_set = element["binding"]["valueSet"].split("|")[0]
            value_definition = ValueDefinition("concept")
            value_definition.selectableConcepts += (get_termentries_from_onto_server(value_set))
            terminology_entry.valueDefinitions.append(value_definition)


def translate_service_request(_profile_data, _terminology_entry):
    pass


def translate_encounter(_profile_data, _terminology_entry):
    pass


def translate_organization(_profile_data, _terminology_entry):
    pass


def translate_specimen(profile_data, terminology_entry):
    # TODO: This should not be hard coded!
    terminology_entry.fhirMapperType = "Specimen"
    for element in profile_data["snapshot"]["element"]:
        if element["path"] == "Specimen.type.coding":
            if "binding" in element:
                value_set = element["binding"]["valueSet"]
                terminology_entry.children += (get_termentries_from_onto_server(value_set))


def translate_substance(_profile_data, _terminology_entry):
    pass


def translate_condition(profile_data, terminology_entry):
    # TODO: Refactor: find a more elegant way to check if a required valuset exists.
    terminology_entry.leaf = True
    terminology_entry.fhirMapperType = "Condition"
    for element in profile_data["snapshot"]["element"]:
        if element["path"] == "Condition.code.coding":
            if "binding" in element and element["min"] > 0:
                # prefer value_sets that are required.
                value_set = element["binding"]["valueSet"]
                terminology_entry.children += (
                    get_termentries_from_onto_server(value_set))
                terminology_entry.leaf = False
                # FIXME: Incorrect break multiple valuesets are allowed but this is currently a work around
                return
            elif "patternCoding" in element:
                if "code" in element["patternCoding"]:
                    code = element["patternCoding"]["code"]
                    system = element["patternCoding"]["system"]
                    display = get_term_code_display_from_onto_server(system, code)
                    terminology_entry.leaf = False
                    terminology_entry.selectable = False
                    term_code = TermCode(system, code, display)
                    child = TerminologyEntry([term_code], "CodeableConcept", leaf=True, selectable=True)
                    terminology_entry.children.append(child)
    for element in profile_data["snapshot"]["element"]:
        if element["path"] == "Condition.code.coding":
            if "binding" in element:
                value_set = element["binding"]["valueSet"]
                terminology_entry.children += (
                    get_termentries_from_onto_server(value_set))
                terminology_entry.leaf = False
                # FIXME: Incorrect break multiple valuesets are allowed but this is currently a work around
                return


def translate_diagnosis_covid_19(profile_data, terminology_entry):
    terminology_entry.fhirMapperType = "DiagnosisCovid19"
    for element in profile_data["snapshot"]["element"]:
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
    for element in profile_data["snapshot"]["element"]:
        if element["path"] == "Condition.code.coding":
            if "binding" in element and element["min"] > 0:
                value_set = element["binding"]["valueSet"]
                children = get_termentries_from_onto_server(value_set)
                for child in children:
                    child.fhirMapperType = "Symptom"
                    value_definition = ValueDefinition("concept")
                    value_definition.selectableConcepts += get_termcodes_from_onto_server(severity_vs)
                    child.valueDefinitions.append(value_definition)
                terminology_entry.children += children
                terminology_entry.leaf = False
                break


def translate_medication_statement(profile_data, terminology_entry):
    terminology_entry.fhirMapperType = "MedicationStatement"
    for element in profile_data["snapshot"]["element"]:
        if element["path"] == "MedicationStatement.medication[x].coding":
            if "binding" in element:
                value_set = element["binding"]["valueSet"]
                terminology_entry.children += (
                    get_termentries_from_onto_server(value_set))
                terminology_entry.leaf = False
    terminology_entry.children = sorted(terminology_entry.children)


def translate_medication_administration(_profile_data, terminology_entry):
    # This code is tailored for MedicationAdministration as defined in kerndatensatz.medikation
    # We use the Medication profile to get the codings referred to by the MedicationAdministration
    with open(MII_MEDICATION_DATA_SET + "/" + "Medication.StructureDefinition-snapshot.json",  encoding="UTF-8")\
            as profile_file:
        medication_profile_data = json.load(profile_file)
        terminology_entry.display = "Medikamentenverabreichungen"
        terminology_entry.fhirMapperType = "MedicationAdministration"
        for element in medication_profile_data["snapshot"]["element"]:
            if element["path"] == "Medication.code.coding":
                if "binding" in element:
                    value_set = element["binding"]["valueSet"]
                    terminology_entry.children += (
                        get_termentries_from_onto_server(value_set))
                    terminology_entry.leaf = False
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
        for element in profile_data["snapshot"]["element"]:
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
            if "sliceName" in element:
                if (element["path"] == "Observation.value[x]" and element["sliceName"] == "valueCodeableConcept") or \
                        (element["path"] == "Observation.value[x].coding"):
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


def translate_sofa(profile_data, terminology_entry):
    for element in profile_data["snapshot"]["element"]:
        update_termcode_to_match_pattern_coding(terminology_entry, element)
    terminology_entry.fhirMapperType = "Sofa"
    terminology_entry.selectable = True
    terminology_entry.leaf = True
    terminology_entry.terminologyType = "Quantity"


def translate_procedure(profile_data, terminology_entry):
    terminology_entry.fhirMapperType = "Procedure"
    terminology_entry.leaf = True
    terminology_entry.selectable = True
    for element in profile_data["snapshot"]["element"]:
        if "id" in element and element["id"] == "Procedure.code.coding:sct" \
                and not terminology_entry.display == "ECMO therapy":
            if "patternCoding" in element:
                parse_term_code(terminology_entry, element, "Procedure.code.coding")
                break
            if "binding" in element:
                value_set = element["binding"]["valueSet"]
                terminology_entry.children += (get_termentries_from_onto_server(value_set))
                terminology_entry.leaf = False
                break
        elif "id" in element and element["id"] == "Procedure.code.coding:ops" and \
                terminology_entry.display == "Prozedur":
            if "patternCoding" in element:
                parse_term_code(terminology_entry, element, "Procedure.code.coding")
                break
            if "binding" in element:
                value_set = element["binding"]["valueSet"]
                terminology_entry.children += (get_termentries_from_onto_server(value_set))
                terminology_entry.leaf = False
                break


def translate_immunization(profile_data, terminology_entry):
    terminology_entry.fhirMapperType = "Immunization"
    for element in profile_data["snapshot"]["element"]:
        if "id" in element and element["id"] == "Immunization.vaccineCode.coding:snomed":
            # and element["slicingName"] == "atc":
            if "binding" in element:
                value_set = element["binding"]["valueSet"]
                terminology_entry.children += (get_termentries_from_onto_server(value_set))
                terminology_entry.leaf = False
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
    for element in profile_data["snapshot"]["element"]:
        parse_term_code(terminology_entry, element, "DiagnosticReport.code.coding")
        if element["path"] == "DiagnosticReport.conclusionCode" and "binding" in element:
            value_set = element["binding"]["valueSet"]
            value_definition = ValueDefinition("concept")
            value_definition.selectableConcepts += get_termcodes_from_onto_server(value_set)
            terminology_entry.valueDefinitions.append(value_definition)
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
    for element in profile_data["snapshot"]["element"]:
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
    for element in profile_data["snapshot"]["element"]:
        if element["id"] == "Observation.component:Country.value[x]":
            if "binding" in element:
                value_set = element["binding"]["valueSet"]
                value_definition = ValueDefinition("concept")
                value_definition.selectableConcepts += get_termcodes_from_onto_server(value_set)
                terminology_entry.valueDefinitions.append(value_definition)
                break


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


# TODO: We only want to use a single coding system. The different coding systems need to be prioritized
# We do not want to expand is-A relations of SNOMED or we need a tree structure , but we cant gain the information
# needed to create a tree structure
def get_termentries_from_onto_server(canonical_address_value_set):
    if canonical_address_value_set == "https://www.medizininformatik-initiative.de/fhir/core/modul-diagnose/ValueSet/diagnoses-sct":
        return []
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
# We do not want to expand is-A relations of snomed or we need a tree structure , but we cant gain the information
# needed to create a tree structure
def get_termcodes_from_onto_server(canonical_address_value_set):
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
                    terminology_entry.valueDefinitions.append(
                        get_value_description_from_top_300_loinc(child.text, element_tree))
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
