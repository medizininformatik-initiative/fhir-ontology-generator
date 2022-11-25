import copy
import json

from TerminologService.ValueSetResolver import get_term_codes_by_path, get_termcodes_from_onto_server, \
    get_term_codes_by_id, get_answer_list_vs
from model.UiDataModel import TermCode

UI_PROFILES = set()


class ValueDefinition:
    def __init__(self, value_type):
        self.type = value_type
        self.selectableConcepts = []
        self.allowedUnits = []
        self.precision = 1
        self.min = None
        self.max = None


class AttributeDefinition(ValueDefinition):
    def __init__(self, attribute_code, value_type):
        super().__init__(value_type)
        self.attributeCode = attribute_code
        self.optional = True


class Unit:
    def __init__(self, display, code):
        self.display = display
        self.code = code


def del_none(dictionary):
    """
    Delete keys with the value ``None`` in a dictionary, recursively.

    This alters the input so you may wish to ``copy`` the dict first.
    """
    for key, value in list(dictionary.items()):
        if value is None:
            del dictionary[key]
        elif isinstance(value, dict):
            del_none(value)
        elif isinstance(value, list):
            if not value:
                del dictionary[key]
            for element in value:
                del_none(element.__dict__)
    return dictionary


def del_keys(dictionary, keys):
    result = copy.deepcopy(dictionary)
    for k in keys:
        result.pop(k, None)
    return result


class UIProfile(object):
    DO_NOT_SERIALIZE = []

    def __init__(self, name):
        self.name = name
        self.timeRestrictionAllowed = True
        self.valueDefinition = None
        self.attributeDefinitions = []

    def to_json(self):
        return json.dumps(self, default=lambda o: del_none(
            del_keys(o.__dict__, self.DO_NOT_SERIALIZE)), sort_keys=True, indent=4)

    def __eq__(self, other):
        return self.name == other.name

    def __hash__(self):
        return hash(self.name)


def generate_concept_observation_ui_profile(profile_data, _logical_element):
    ui_profile = UIProfile(profile_data["name"])
    value_definition = ValueDefinition("concept")
    if selectable_concepts := get_term_codes_by_path("Observation.value[x]", profile_data):
        value_definition.selectableConcepts = selectable_concepts
    else:
        value_definition.selectableConcepts = get_term_codes_by_path("Observation.value[x].coding", profile_data)
    ui_profile.valueDefinition = value_definition
    UI_PROFILES.add(ui_profile)
    return ui_profile


def generate_consent_ui_profile(profile_data, _logical_element):
    ui_profile = UIProfile(profile_data["name"])
    for element in profile_data["snapshot"]["element"]:
        if element["id"] == "Consent.provision.code":
            if "binding" in element:
                value_set = element["binding"]["valueSet"]
                value_definition = ValueDefinition("concept")
                value_definition.selectableConcepts += get_termcodes_from_onto_server(value_set)
                ui_profile.valueDefinition = value_definition
                UI_PROFILES.add(ui_profile)
                return ui_profile
    UI_PROFILES.add(ui_profile)
    return ui_profile


def generate_default_ui_profile(name, _logical_element):
    ui_profile = UIProfile(name)
    UI_PROFILES.add(ui_profile)
    return ui_profile


def generate_diagnosis_covid_19_ui_profile(profile_data, _logical_element):
    ui_profile = UIProfile(profile_data["name"])
    stage_code = TermCode("mii.abide", "stage", "Stadium")
    stage_attribute = AttributeDefinition(stage_code, "concept")
    stage_attribute.selectableConcepts = get_term_codes_by_path("Condition.stage.summary.coding", profile_data)
    ui_profile.attributeDefinitions.append(stage_attribute)
    UI_PROFILES.add(ui_profile)
    return ui_profile


def generate_diagnostic_report_ui_profile(profile_data, _logical_element):
    ui_profile = UIProfile(profile_data["name"])
    value_definition = ValueDefinition("concept")
    value_definition.selectableConcepts = get_term_codes_by_path("DiagnosticReport.conclusionCode", profile_data)
    ui_profile.valueDefinition = value_definition
    UI_PROFILES.add(ui_profile)
    return ui_profile


# TODO
def generate_ethnic_group_ui_profile(profile_data, _logical_element):
    ui_profile = UIProfile(profile_data["name"])
    value_definition = ValueDefinition("concept")
    value_definition.selectableConcepts += get_term_codes_by_path("Extension.value[x]", profile_data)
    ui_profile.valueDefinition = value_definition
    UI_PROFILES.add(ui_profile)
    return ui_profile


# TODO: generate patient ui_profile and add gender and age attribute definition
def generate_gender_ui_profile(profile_data, _logical_element):
    # The gender profile is derived from the patient profile as the age profile therefore different names are required
    ui_profile = UIProfile(profile_data["name"] + "_gender")
    ui_profile.timeRestrictionAllowed = False
    gender_attribute_code = TermCode("mii.abide", "gender", "Geschlecht")
    gender_attribute = AttributeDefinition(gender_attribute_code, "concept")
    gender_attribute.selectableConcepts = (get_term_codes_by_path("Patient.gender", profile_data))
    gender_attribute.optional = False
    ui_profile.attributeDefinitions.append(gender_attribute)
    UI_PROFILES.add(ui_profile)
    return ui_profile


def generate_age_kds_ui_profile(profile_data, _logical_element):
    # The age profile is derived from the patient profile as the gender profile therefore different names are required
    ui_profile = UIProfile(profile_data["name"] + "_age")
    ui_profile.timeRestrictionAllowed = False
    age_attribute_code = TermCode("mii.abide", "age", "Alter")
    age_attribute = AttributeDefinition(age_attribute_code, "quantity")
    age_attribute.allowedUnits = [Unit('a', 'a'), Unit('mo', 'mo'), Unit('wk', 'wk')]
    age_attribute.optional = False
    ui_profile.attributeDefinitions.append(age_attribute)
    UI_PROFILES.add(ui_profile)
    return ui_profile


def generate_history_of_travel_ui_profile(profile_data, _logical_element):
    ui_profile = UIProfile(profile_data["name"])
    value_definition = ValueDefinition("concept")
    value_definition.selectableConcepts = get_term_codes_by_id("Observation.component:Country.value[x]", profile_data)
    ui_profile.valueDefinition = value_definition
    UI_PROFILES.add(ui_profile)
    return ui_profile


def generate_quantity_observation_ui_profile(profile_data, logical_element):
    ui_profile = UIProfile(profile_data["name"])
    ui_profile.valueDefinition = get_value_definition(logical_element)
    UI_PROFILES.add(ui_profile)
    return ui_profile


def generate_age_ui_profile(profile_data, _logical_element):
    ui_profile = UIProfile(profile_data["name"])
    value_definition = ValueDefinition("quantity")
    value_definition.allowedUnits = [Unit('a', 'a'), Unit('mo', 'mo'), Unit('wk', 'wk')]
    ui_profile.valueDefinition = value_definition
    UI_PROFILES.add(ui_profile)
    return ui_profile


def generate_specimen_ui_profile(profile_data, _logical_element):
    ui_profile = UIProfile(profile_data["name"])
    # status_attribute_code = TermCode("mii.abide", "status", "Status")
    # status_attribute_code = AttributeDefinition(attribute_code=status_attribute_code, value_type="concept")
    # status_attribute_code.selectableConcepts = get_term_codes_by_path("Specimen.status", profile_data)
    # ui_profile.attributeDefinitions.append(status_attribute_code)
    body_site_attribute_code = TermCode("mii.module_specimen", "Specimen.collection.bodySite", "Entnahmeort")
    body_site_attribute = AttributeDefinition(attribute_code=body_site_attribute_code, value_type="concept")
    body_site_attribute.selectableConcepts = get_term_codes_by_id("Specimen.collection.bodySite.coding:icd-o-3",
                                                                  profile_data)
    ui_profile.attributeDefinitions.append(body_site_attribute)
    UI_PROFILES.add(ui_profile)
    return ui_profile


def generate_symptom_ui_profile(profile_data, _logical_element):
    ui_profile = UIProfile(profile_data["name"])
    severity_attribute_code = TermCode("mii.abide", "severity", "Schweregrad")
    severity_attribute = AttributeDefinition(severity_attribute_code, "concept")
    severity_attribute.optional = False
    # TODO: Refactor not hardcoded!
    severity_vs = "https://www.netzwerk-universitaetsmedizin.de/fhir/ValueSet/condition-severity"
    severity_attribute.selectableConcepts += get_termcodes_from_onto_server(severity_vs)
    ui_profile.attributeDefinitions.append(severity_attribute)
    UI_PROFILES.add(ui_profile)
    return ui_profile


def generate_top300_loinc_ui_profile(terminology_entry, element_id, element_tree):
    ui_profile = UIProfile(terminology_entry.display)
    # We don't know if a value definition exists, as the MIRACUM is incomplete for qualitative lab values.
    if quantity_value_description := get_quantity_value_description_from_top_300_loinc(element_id, element_tree):
        ui_profile.valueDefinition = quantity_value_description
    elif concept_value_description := get_concept_value_description_for_loinc_code(terminology_entry):
        ui_profile.valueDefinition = concept_value_description
    else:
        print(terminology_entry.termCode.display)
    UI_PROFILES.add(ui_profile)
    return ui_profile


def get_value_definition(element):
    value_definition = ValueDefinition("quantity")
    if element:
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


def get_quantity_value_description_from_top_300_loinc(element_id, element_tree):
    value_definition = ValueDefinition("quantity")
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
                    value_definition.allowedUnits.append(unit)
    if not value_definition.allowedUnits:
        return None
    return value_definition


def get_concept_value_description_for_loinc_code(terminology_entry):
    value_definition = ValueDefinition("concept")
    value_set_url = get_answer_list_vs(terminology_entry.termCode)
    if value_set_url:
        value_definition.selectableConcepts = get_termcodes_from_onto_server(value_set_url)
        return value_definition
    return None


def get_ui_profiles():
    return UI_PROFILES
