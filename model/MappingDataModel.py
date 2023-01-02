from __future__ import annotations

from typing import List

from sortedcontainers import SortedSet
from model.helper import del_none, str_to_class
from model.UiDataModel import del_keys, TermCode
import json


class FixedCriteria:
    def __init__(self, criteria_type, search_parameter, fhir_path, value=None):
        if value is None:
            value = []
        self.type = criteria_type
        self.value = value
        self.fhirPath = fhir_path
        self.searchParameter = search_parameter


class AttributeSearchParameter:
    """
    AttributeSearchParameter the information how to translate the attribute part of a criteria to a FHIR query snippet
    :param attribute_code defines the code of the attribute and acts as unique identifier within the ui_profile
    (Required)
    :param attribute_search_parameter defines the search parameter of the attribute. (Required)
    :param fhir_path defines the path to the attribute defining element. (Required)
    """

    def __init__(self, criteria_type, attribute_code: TermCode, attribute_search_parameter: str, fhir_path: str):
        self.attributeKey = attribute_code
        self.attributeSearchParameter = attribute_search_parameter
        self.attributeType = criteria_type
        self.attributeFhirPath = fhir_path


class MapEntry:
    DO_NOT_SERIALIZE = ["DO_NOT_SERIALIZE"]
    """
    MapEntry stores all necessary information to translate the criteria in a structured query to a FHIR query snippet.
    :param term_code defines the identifying term code of the criteria. (Required)
    :param context defines the context of the criteria. 
    """

    def __init__(self, term_code: TermCode, context: TermCode = None):
        self.context = context
        self.key = term_code
        self.termCodeSearchParameter: str | None = None
        self.valueSearchParameter: str | None = None
        self.timeRestrictionParameter: str | None = None
        self.timeRestrictionPath: str | None = None
        self.fhirResourceType: str | None = None
        # self.fixedCriteria = []
        self.valueFhirPath: str | None = None
        self.attributeSearchParameters: List[AttributeSearchParameter] = []

    def __eq__(self, other):
        return self.key == other.key

    def __ne__(self, other):
        return not self.__eq__(other)

    def __lt__(self, other):
        return self.key < other.key

    def __hash__(self):
        return hash(self.key)

    def to_json(self):
        return json.dumps(self, default=lambda o: del_none(
            del_keys(o.__dict__, self.DO_NOT_SERIALIZE)), sort_keys=True, indent=4)


class MapEntryList:
    def __init__(self):
        self.entries = SortedSet()

    def to_json(self):
        self.entries = list(self.entries)
        return json.dumps(self.entries, default=lambda o: del_none(o.__dict__), sort_keys=True, indent=4)

    def get_code_systems(self):
        code_systems = SortedSet()
        for entry in self.entries:
            code_systems.add(entry.key.system)
            for fixed_criteria in entry.fixedCriteria:
                if fixed_criteria.type == "coding":
                    for value in fixed_criteria.value:
                        code_systems.add(value.system)
        return code_systems


class AgeMapEntry(MapEntry):
    def __init__(self, term_code):
        super().__init__(term_code)
        self.valueSearchParameter = "codex-age"
        self.valueFhirPath = "extension.where(url='https://www.netzwerk-universitaetsmedizin.de/fhir" \
                             "/StructureDefinition/age').extension.where(url='age').value.first() "
        self.fhirResourceType = "Patient"


# FIXME: component-code-value-quantity
class BloodPressureMapEntry(MapEntry):
    def __init__(self, term_code):
        super().__init__(term_code)
        self.valueSearchParameter = "component-code-value-quantity"
        self.termCodeSearchParameter = "component-code-value-concept"
        self.fhirResourceType = "Observation"
        self.valueFhirPath = f"component.where(code.coding.exists(system = '{term_code.system}' and " \
                             f"code = '{term_code.code}')).value.first() "
        self.timeRestrictionParameter = "effective"
        self.timeRestrictionPath = "date"
        # blood_pressure_loinc = TermCode("http://loinc.org", "85354-9",
        #                                 "Blood pressure panel with all children optional")
        # blood_pressure_snomed = TermCode("http://snomed.info/sct", "75367002", "Blood pressure (observable entity)")
        # self.fixedCriteria = [FixedCriteria("coding", "code", "code", [blood_pressure_loinc, blood_pressure_snomed])]


# FIXME: component-code-value-quantity
class ConceptObservationMapEntry(MapEntry):
    def __init__(self, term_code):
        super().__init__(term_code)
        self.termCodeSearchParameter = "code"
        self.valueSearchParameter = "value-concept"
        self.valueFhirPath = "value"
        self.fhirResourceType = "Observation"
        # self.fixedCriteria = []
        self.timeRestrictionParameter = "date"
        self.timeRestrictionPath = "effective"


class ConditionMapEntry(MapEntry):
    def __init__(self, term_code):
        super().__init__(term_code)
        self.termCodeSearchParameter = "code"
        self.valueSearchParameter = None
        self.fhirResourceType = "Condition"
        # confirmed = TermCode("http://terminology.hl7.org/CodeSystem/condition-ver-status", "confirmed", "confirmed")
        # self.fixedCriteria = [FixedCriteria("coding", "verification-status", "verificationStatus", [confirmed])]
        self.timeRestrictionParameter = "recorded-date"
        self.timeRestrictionPath = "onset"


class ConsentMapEntry(MapEntry):
    def __init__(self, term_code):
        super().__init__(term_code)
        self.termCodeSearchParameter = "mii-provision-provision-code-type"
        self.valueSearchParameter = "mii-provision-provision-code-type"
        self.valueFhirPath = "mii-provision-provision-code-type"
        self.valueTypeFhir = "code"
        self.fhirResourceType = "Consent"
        self.timeRestrictionParameter = "date"
        self.timeRestrictionPath = "dateTime"


class DiagnosisCovid19MapEntry(MapEntry):
    def __init__(self, term_code):
        super().__init__(term_code)
        self.termCodeSearchParameter = "code"
        self.fhirResourceType = "Condition"
        stage_attribute_code = TermCode("mii.abide", "stage", "Stadium")
        stage_attribute_search_parameter = AttributeSearchParameter("code", stage_attribute_code, "stage", "stage")
        self.attributeSearchParameters = [stage_attribute_search_parameter]
        # self.fixedCriteria = []
        self.timeRestrictionParameter = "recorded-date"
        self.timeRestrictionPath = "onset"


class DiagnosticReportMapEntry(MapEntry):
    def __init__(self, term_code):
        super().__init__(term_code)
        self.termCodeSearchParameter = "code"
        self.fhirResourceType = "DiagnosticReport"
        self.valueSearchParameter = "conclusion"
        self.valueFhirPath = "conclusion"
        # self.fixedCriteria = []
        self.timeRestrictionParameter = "date"
        self.timeRestrictionPath = "effective"


class EthnicGroupMapEntry(MapEntry):
    def __init__(self, term_code):
        super().__init__(term_code)
        self.valueSearchParameter = "codex-ethnicity"
        self.valueFhirPath = "extension.where(url='https://www.netzwerk-universitaetsmedizin.de/fhir" \
                             "/StructureDefinition/ethnic-group').value.first()"
        self.fhirResourceType = "Patient"
        self.valueType = "Coding"


class HistoryOfTravelMapEntry(MapEntry):
    def __init__(self, term_code):
        super().__init__(term_code)
        self.termCodeSearchParameter = "code"
        self.valueSearchParameter = "component-value-concept"
        self.fhirResourceType = "Observation"
        # country_of_travel = TermCode("http://loinc.org", "94651-7", "Country of travel")
        # self.fixedCriteria = [FixedCriteria("coding", "component-code", "component-code", [country_of_travel])]
        self.timeRestrictionParameter = "date"
        self.timeRestrictionPath = "effective"
        self.valueFhirPath = "component.where(code.coding.exists(system = 'http://loinc.org' and code = '" \
                             "94651-7')).value.first() "


class ImmunizationMapEntry(MapEntry):
    def __init__(self, term_code):
        super().__init__(term_code)
        self.termCodeSearchParameter = "vaccine-code"
        self.valueFhirPath = "vaccineCode"
        self.fhirResourceType = "Immunization"
        self.valueSearchParameter = None
        # completed = TermCode("http://hl7.org/fhir/event-status", "completed", "completed")
        # self.fixedCriteria = [FixedCriteria("code", "status", "status", [completed])]
        self.timeRestrictionParameter = "date"
        self.timeRestrictionPath = "occurrence"


class MedicationAdministrationMapEntry(MapEntry):
    def __init__(self, term_code):
        super().__init__(term_code)
        # FIXME: medication.code is not part of MedicationAdministration
        self.termCodeSearchParameter = "medication.code"
        self.fhirResourceType = "MedicationAdministration"

        self.valueSearchParameter = None
        # active = TermCode("http://hl7.org/fhir/CodeSystem/medication-admin-status", "active", "active")
        # completed = TermCode("http://hl7.org/fhir/CodeSystem/medication-admin-status", "completed", "completed")
        # self.fixedCriteria = [FixedCriteria("code", "status", "status", [active, completed])]
        self.timeRestrictionParameter = "date"
        self.timeRestrictionPath = "occurence"
        self.valueFhirPath = "medication.reference"


class MedicationStatementMapEntry(MapEntry):
    def __init__(self, term_code):
        super().__init__(term_code)
        self.termCodeSearchParameter = "medication.code"
        self.fhirResourceType = "MedicationAdministration"
        self.valueSearchParameter = None
        # active = TermCode("http://hl7.org/fhir/CodeSystem/medication-statement-status", "active", "active")
        # completed = TermCode("http://hl7.org/fhir/CodeSystem/medication-statement-status", "completed", "completed")
        # self.fixedCriteria = [FixedCriteria("code", "status", "status", [active, completed])]
        self.timeRestrictionParameter = "date"
        self.timeRestrictionPath = "occurence"
        self.valueFhirPath = "medication.reference"


class PatientMapEntry(MapEntry):
    def __init__(self, term_code):
        super().__init__(term_code)
        self.fhirResourceType = "Patient"
        gender_attribute_term_code = TermCode("mii.abide", "gender", "Geschlecht")
        gender_attribute_term_code_search_parameter = AttributeSearchParameter("code", gender_attribute_term_code,
                                                                               "gender", "gender")
        age_attribute_term_code = TermCode("mii.abide", "age", "Alter")
        age_attribute_term_code_search_parameter = AttributeSearchParameter("quantity", age_attribute_term_code, "age",
                                                                            "")
        self.attributeSearchParameters = [age_attribute_term_code_search_parameter,
                                          gender_attribute_term_code_search_parameter]


class ProcedureMapEntry(MapEntry):
    def __init__(self, term_code):
        super().__init__(term_code)
        self.termCodeSearchParameter = "code"
        self.valueSearchParameter = None
        self.fhirResourceType = "Procedure"
        # completed = TermCode("http://hl7.org/fhir/event-status", "completed", "completed")
        # in_progress = TermCode("http://hl7.org/fhir/event-status", "in-progress", "in-progress")
        # self.fixedCriteria = [FixedCriteria("code", "status", "status", [completed, in_progress])]
        self.timeRestrictionParameter = "date"
        self.timeRestrictionPath = "performed"


class QuantityObservationMapEntry(MapEntry):
    def __init__(self, term_code):
        super().__init__(term_code)
        self.termCodeSearchParameter = "code"
        self.valueSearchParameter = "value-quantity"
        self.valueFhirPath = "value"
        self.fhirResourceType = "Observation"
        # self.fixedCriteria = []
        self.timeRestrictionParameter = "date"
        self.timeRestrictionPath = "effective"


class ResuscitationStatusMapEntry(MapEntry):
    def __init__(self, term_code):
        super().__init__(term_code)
        self.termCodeSearchParameter = "category"
        self.valueSearchParameter = "mii-provision-code"
        self.valueFhirPath = "provision.code"
        self.fhirResourceType = "Consent"
        self.timeRestrictionParameter = "date"
        self.timeRestrictionPath = "dateTime"


class SofaMapEntry(MapEntry):
    def __init__(self, term_code):
        super().__init__(term_code)
        self.termCodeSearchParameter = "code"
        self.valueSearchParameter = "mii-value-integer"
        self.fhirResourceType = "Observation"
        self.valueFhirPath = "valueInteger"
        self.timeRestrictionParameter = "date"
        self.timeRestrictionPath = "effective"


class SpecimenMapEntry(MapEntry):
    def __init__(self, term_code):
        super().__init__(term_code)
        self.termCodeSearchParameter = "type"
        self.fhirResourceType = "Specimen"
        self.valueSearchParameter = None
        # available = TermCode("http://hl7.org/fhir/ValueSet/specimen-status", "available", "Available")
        # # self.fixedCriteria = [FixedCriteria("code", "status", "status", [available])]
        # FIXME: We need better handling of TermCodes used cross UI and Mapping this is error-prone!
        body_site_attribute_term_code = TermCode("mii.module_specimen", "Specimen.collection.bodySite", "Entnahmeort")
        body_site_attribute_search_parameter = AttributeSearchParameter("code", body_site_attribute_term_code,
                                                                        "bodysite", "collection.bodySite")
        # status_attribute_term_code = TermCode("mii.abide", "status", "status")
        # status_attribute_search_parameter = AttributeSearchParameter("code", status_attribute_term_code, "status",
        #                                                              "status")
        self.attributeSearchParameters = [body_site_attribute_search_parameter]
        self.timeRestrictionParameter = "collected"
        self.timeRestrictionPath = "collection.collected"


class SymptomMapEntry(MapEntry):
    def __init__(self, term_code):
        super().__init__(term_code)
        self.termCodeSearchParameter = "code"
        severity_attribute_code = TermCode("mii.abide", "severity", "Schweregrad")
        severity_attribute_search_parameter = AttributeSearchParameter("code", severity_attribute_code,
                                                                       "severity", "severity")
        self.attributeSearchParameters = [severity_attribute_search_parameter]
        self.fhirResourceType = "Condition"
        # confirmed = TermCode("http://terminology.hl7.org/CodeSystem/condition-ver-status", "confirmed", "confirmed")
        # self.fixedCriteria = [FixedCriteria("coding", "verification-status", "verificationStatus", [confirmed])]
        self.timeRestrictionParameter = "recorded-date"
        self.timeRestrictionPath = "onset"


def generate_child_entries(children, class_name):
    result = SortedSet()
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
                for termCode in terminology.termCodes:
                    if terminology.selectable:
                        result.entries.add(str_to_class(class_name)(termCode))
                    result.entries = result.entries.union(generate_child_entries(terminology.children, class_name))
            else:
                print(terminology)
    return result
