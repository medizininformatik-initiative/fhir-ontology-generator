from UiDataModel import del_keys, del_none, TermCode
import json
import sys


class FixedCriteria:
    def __init__(self, criteria_type, search_parameter, fhir_path, value=None):
        if value is None:
            value = []
        self.type = criteria_type
        self.value = value
        self.fhirPath = fhir_path
        self.searchParameter = search_parameter


class AttributeSearchParameter:
    def __init__(self, criteria_type, attribute_code, attribute_search_parameter, fhir_path):
        self.attributeKey = attribute_code
        self.attributeSearchParameter = attribute_search_parameter
        self.attributeType = criteria_type
        self.attributeFhirPath = fhir_path


class MapEntry:
    DO_NOT_SERIALIZE = ["DO_NOT_SERIALIZE"]

    def __init__(self, term_code):
        self.key = term_code
        self.termCodeSearchParameter = None
        self.valueSearchParameter = None
        self.timeRestrictionParameter = None
        self.fhirResourceType = None
        self.fixedCriteria = []
        self.valueFhirPath = None
        self.attributeSearchParameters = []

    def __eq__(self, other):
        return self.key == other.key

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self.key)

    def to_json(self):
        return json.dumps(self, default=lambda o: del_none(
            del_keys(o.__dict__, self.DO_NOT_SERIALIZE)), sort_keys=True, indent=4)


class MapEntryList:
    def __init__(self):
        self.entries = set()

    def to_json(self):
        self.entries = list(self.entries)
        return json.dumps(self.entries, default=lambda o: del_none(o.__dict__), sort_keys=True, indent=4)

    def get_code_systems(self):
        code_systems = set()
        for entry in self.entries:
            code_systems.add(entry.key.system)
            for fixed_criteria in entry.fixedCriteria:
                if fixed_criteria.type == "coding":
                    for value in fixed_criteria.value:
                        code_systems.add(value.system)
        return code_systems


class QuantityObservationMapEntry(MapEntry):
    def __init__(self, term_code):
        super().__init__(term_code)
        self.termCodeSearchParameter = "code"
        self.valueSearchParameter = "value-quantity"
        self.valueFhirPath = "value"
        self.fhirResourceType = "Observation"
        self.fixedCriteria = []


class ConceptObservationMapEntry(MapEntry):
    def __init__(self, term_code):
        super().__init__(term_code)
        self.termCodeSearchParameter = "code"
        self.valueSearchParameter = "value-concept"
        self.valueFhirPath = "valueConcept"
        self.fhirResourceType = "Observation"
        self.fixedCriteria = []


class ConditionMapEntry(MapEntry):
    def __init__(self, term_code):
        super().__init__(term_code)
        self.termCodeSearchParameter = "code"
        self.valueSearchParameter = None
        self.fhirResourceType = "Condition"
        confirmed = TermCode("http://terminology.hl7.org/CodeSystem/condition-ver-status", "confirmed", "confirmed")
        self.fixedCriteria = [FixedCriteria("coding", "verification-status", "verificationStatus", [confirmed])]


class ProcedureMapEntry(MapEntry):
    def __init__(self, term_code):
        super().__init__(term_code)
        self.termCodeSearchParameter = "code"
        self.valueSearchParameter = None
        self.fhirResourceType = "Procedure"
        completed = TermCode("http://hl7.org/fhir/event-status", "completed", "completed")
        in_progress = TermCode("http://hl7.org/fhir/event-status", "in-progress", "in-progress")
        self.fixedCriteria = [FixedCriteria("code", "status", "status", [completed, in_progress])]


class SymptomMapEntry(MapEntry):
    def __init__(self, term_code):
        super().__init__(term_code)
        self.termCodeSearchParameter = "code"
        severity_attribute_code = TermCode("num.abide", "severity", "Schweregrad")
        severity_attribute_search_parameter = AttributeSearchParameter("code", severity_attribute_code,
                                                                       "severity", "severity")
        self.attributeSearchParameters = [severity_attribute_search_parameter]
        self.fhirResourceType = "Condition"
        confirmed = TermCode("http://terminology.hl7.org/CodeSystem/condition-ver-status", "confirmed", "confirmed")
        self.fixedCriteria = [FixedCriteria("coding", "verification-status", "verificationStatus", [confirmed])]


class MedicationStatementMapEntry(MapEntry):
    def __init__(self, term_code):
        super().__init__(term_code)
        self.termCodeSearchParameter = "code"
        self.fhirResourceType = "MedicationStatement"
        self.valueSearchParameter = None
        active = TermCode("http://hl7.org/fhir/CodeSystem/medication-statement-status", "active", "active")
        completed = TermCode("http://hl7.org/fhir/CodeSystem/medication-statement-status", "completed", "completed")
        self.fixedCriteria = [FixedCriteria("code", "status", "status", [active, completed])]


class MedicationAdministrationMapEntry(MapEntry):
    def __init__(self, term_code):
        super().__init__(term_code)
        self.termCodeSearchParameter = "code"
        self.fhirResourceType = "MedicationAdministration"
        self.valueSearchParameter = None
        active = TermCode("http://hl7.org/fhir/CodeSystem/medication-admin-status", "active", "active")
        completed = TermCode("http://hl7.org/fhir/CodeSystem/medication-admin-status", "completed", "completed")
        self.fixedCriteria = [FixedCriteria("code", "status", "status", [active, completed])]


class ImmunizationMapEntry(MapEntry):
    def __init__(self, term_code):
        super().__init__(term_code)
        self.termCodeSearchParameter = "vaccine-code"
        self.valueFhirPath = "vaccineCode"
        self.fhirResourceType = "Immunization"
        self.valueSearchParameter = None
        completed = TermCode("http://hl7.org/fhir/event-status", "completed", "completed")
        self.fixedCriteria = [FixedCriteria("code", "status", "status", [completed])]


class DiagnosticReportMapEntry(MapEntry):
    def __init__(self, term_code):
        super().__init__(term_code)
        self.termCodeSearchParameter = "code"
        self.fhirResourceType = "DiagnosticReport"
        self.valueSearchParameter = "conclusion"
        self.valueFhirPath = "conclusion"
        self.fixedCriteria = []


class DiagnosisCovid19MapEntry(MapEntry):
    def __init__(self, term_code):
        super().__init__(term_code)
        self.termCodeSearchParameter = "code"
        self.fhirResourceType = "Condition"
        stage_attribute_code = TermCode("num.abide", "stage", "Stadium")
        stage_attribute_search_parameter = AttributeSearchParameter("code", stage_attribute_code, "stage", "stage")
        self.attributeSearchParameters = stage_attribute_search_parameter
        self.fixedCriteria = []


class PatientMapEntry(MapEntry):
    def __init__(self, term_code):
        super().__init__(term_code)
        self.fhirResourceType = "Patient"
        gender_attribute_term_code = TermCode("num.abide", "gender", "Geschlecht")
        gender_attribute_term_code_search_parameter = ("code", gender_attribute_term_code, "gender", "gender")
        self.attributeSearchParameters = [gender_attribute_term_code_search_parameter]


class SpecimenMapEntry(MapEntry):
    def __init__(self, term_code):
        super().__init__(term_code)
        self.termCodeSearchParameter = "type"
        self.fhirResourceType = "Specimen"
        self.valueSearchParameter = None
        # available = TermCode("http://hl7.org/fhir/ValueSet/specimen-status", "available", "Available")
        # self.fixedCriteria = [FixedCriteria("code", "status", "status", [available])]
        # FIXME: We need better handling of TermCodes used cross UI and Mapping this is error-prone!
        body_site_attribute_term_code = TermCode("mii.module_specimen", "Specimen.collection.bodySite", "Entnahmeort")
        body_site_attribute_search_parameter = AttributeSearchParameter("code", body_site_attribute_term_code,
                                                                        "bodysite", "collection.bodySite")
        status_attribute_term_code = TermCode("num.abide", "status", "status")
        status_attribute_search_parameter = AttributeSearchParameter("code", status_attribute_term_code, "status",
                                                                     "status")
        self.attributeSearchParameters = [body_site_attribute_search_parameter, status_attribute_search_parameter]
        self.timeRestrictionParameter = "collected"


class EthnicGroupMapEntry(MapEntry):
    def __init__(self, term_code):
        super().__init__(term_code)
        self.valueSearchParameter = "codex-ethnicity"
        self.valueFhirPath = "extension.ethnicGroup"
        self.fhirResourceType = "Patient"


class AgeMapEntry(MapEntry):
    def __init__(self, term_code):
        super().__init__(term_code)
        self.valueSearchParameter = "codex-age"
        self.valueFhirPath = "extension.age"
        self.fhirResourceType = "Patient"


# FIXME: component-code-value-quantity
class BloodPressureMapEntry(MapEntry):
    def __init__(self, term_code):
        super().__init__(term_code)
        self.termCodeSearchParameter = "component-code-value-quantity"
        self.valueSearchParameter = "component-code-value-concept"
        self.fhirResourceType = "Observation"
        blood_pressure_loinc = TermCode("http://loinc.org", "85354-9",
                                        "Blood pressure panel with all children optional")
        blood_pressure_snomed = TermCode("http://snomed.info/sct", "75367002", "Blood pressure (observable entity)")
        self.fixedCriteria = [FixedCriteria("coding", "code", "code", [blood_pressure_loinc, blood_pressure_snomed])]


# FIXME: component-code-value-quantity
class HistoryOfTravelMapEntry(MapEntry):
    def __init__(self, term_code):
        super().__init__(term_code)
        self.termCodeSearchParameter = "code"
        self.valueSearchParameter = "component-value-concept"
        self.fhirResourceType = "Observation"
        country_of_travel = TermCode("http://loinc.org", "94651-7", "Country of travel")
        self.fixedCriteria = [FixedCriteria("coding", "component-code", "component-code", [country_of_travel])]


class ResuscitationStatusMapEntry(MapEntry):
    def __init__(self, term_code):
        super().__init__(term_code)
        self.termCodeSearchParameter = "category"
        self.valueSearchParameter = "mii-provision-code"
        self.valueFhirPath = "provision.code"
        self.fhirResourceType = "Consent"


class ConsentMapEntry(MapEntry):
    def __init__(self, term_code):
        super().__init__(term_code)
        self.termCodeSearchParameter = "mii-provision-provision-code-type"
        self.valueSearchParameter = "mii-provision-provision-code-type"
        self.valueFhirPath = "mii-provision-provision-code-type"
        self.fhirResourceType = "Consent"


class SofaMapEntry(MapEntry):
    def __init__(self, term_code):
        super().__init__(term_code)
        self.termCodeSearchParameter = "code"
        self.valueSearchParameter = "mii-value-integer"
        self.fhirResourceType = "Observation"
        self.valueFhirPath = "valueInteger"


def generate_child_entries(children, class_name):
    result = set()
    for child in children:
        result.add(str_to_class(class_name)(child.termCode))
        result = result.union(generate_child_entries(child.children, class_name))
    return result


def generate_map(categories):
    result = MapEntryList()
    for category in categories:
        for terminology in category.children:
            if terminology.fhirMapperType:
                class_name = terminology.fhirMapperType + "MapEntry"
                result.entries.add(str_to_class(class_name)(terminology.termCode))
                result.entries = result.entries.union(generate_child_entries(terminology.children, class_name))
            else:
                print(terminology)
    return result


def str_to_class(class_name):
    return getattr(sys.modules[__name__], class_name)
