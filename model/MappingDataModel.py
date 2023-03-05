import sys

from sortedcontainers import SortedSet

from model.UiDataModel import del_keys, del_none, TermCode
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
        self.timeRestrictionPath = None
        self.codeFhirPath = None
        self.fhirResourceType = None
        self.fixedCriteria = []
        self.valueFhirPath = None
        self.attributeSearchParameters = []
        self.primaryCode = None
        self.valueType = None

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
        self.valueFhirPath = f"component.where(code.coding.exists(system = '{term_code.system}' and code = '{term_code.code}')).value.first() "
        self.timeRestrictionParameter = "effective"
        self.timeRestrictionPath = "date"
        blood_pressure_loinc = TermCode("http://loinc.org", "85354-9",
                                        "Blood pressure panel with all children optional")
        blood_pressure_snomed = TermCode("http://snomed.info/sct", "75367002", "Blood pressure (observable entity)")
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
        confirmed = TermCode("http://terminology.hl7.org/CodeSystem/condition-ver-status", "confirmed", "confirmed")
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


class MIIConsentMapEntry(MapEntry):
    def __init__(self, term_code):
        super().__init__(term_code)
        self.termCodeSearchParameter = "provisionCode"
        self.codeFhirPath = "provision.provision.code"
        self.primaryCode = TermCode("http://loinc.org", "54133-1", "Consent Document")
        self.fhirResourceType = "Consent"
        self.timeRestrictionParameter = "date"
        self.timeRestrictionPath = "dateTime"
        active = TermCode("http://hl7.org/fhir/consent-state-codes", "active", "Active")
        active_fixed_criteria = FixedCriteria("code", "status", "status", [active])
        self.fixedCriteria = [active_fixed_criteria]


class MIIConsentCombinedMapEntry(MapEntry):
    def __init__(self, term_code):
        super().__init__(term_code)
        self.fhirResourceType = "Consent"
        self.timeRestrictionParameter = "date"
        self.timeRestrictionPath = "dateTime"
        self.primaryCode = TermCode("http://loinc.org", "54133-1", "Consent Document")

        active = TermCode("http://hl7.org/fhir/consent-state-codes", "active", "Active")
        active_fixed_criteria = FixedCriteria("code", "status", "status", [active])

        consent_system = "urn:oid:2.16.840.1.113883.3.1937.777.24.5.3"
        idat_bereitstellen_eu_dsgvo_niveau_code = "2.16.840.1.113883.3.1937.777.24.5.3.5"
        idat_bereitstellen_eu_dsgvo_niveau_display = "IDAT bereitstellen EU DSGVO NIVEAU"
        idat_bereitstellen_eu_dsgvo_niveau = TermCode(consent_system, idat_bereitstellen_eu_dsgvo_niveau_code,
                                                      idat_bereitstellen_eu_dsgvo_niveau_display)
        idat_bereitstellen_eu_dsgvo_niveau_fixed_critiera = FixedCriteria("coding", "mii-provision-provision-code",
                                                                          "provision.provision.code",
                                                                          [idat_bereitstellen_eu_dsgvo_niveau])
        idat_erheben_code = "2.16.840.1.113883.3.1937.777.24.5.3.2"
        idat_erheben_display = "IDAT erheben"
        idat_erhben = TermCode(consent_system, idat_erheben_code, idat_erheben_display)
        idat_erheben_fixed_critiera = FixedCriteria("coding", "mii-provision-provision-code",
                                                    "provision.provision.code", [idat_erhben])
        idat_speichern_verarbeiten_code = "2.16.840.1.113883.3.1937.777.24.5.3.3"
        idat_speichern_verarbeiten_display = "IDAT speichern/verarbeiten"
        idat_speichern_verarbeiten = TermCode(consent_system, idat_speichern_verarbeiten_code,
                                              idat_speichern_verarbeiten_display)
        idat_speichern_verarbeiten_fixed_critiera = FixedCriteria("coding", "mii-provision-provision-code",
                                                                  "provision.provision.code",
                                                                  [idat_speichern_verarbeiten])
        idat_zusammenfuehren_dritte_code = "2.16.840.1.113883.3.1937.777.24.5.3.4"
        idat_zusammenfuehren_dritte_display = "IDAT zusammenfuehren mit Dritte"
        idat_zusammenfuehren_dritte = TermCode(consent_system, idat_zusammenfuehren_dritte_code,
                                               idat_zusammenfuehren_dritte_display)
        idat_zusammenfuehren_dritte_fixed_critiera = FixedCriteria("coding", "mii-provision-provision-code",
                                                                   "provision.provision.code",
                                                                   [idat_zusammenfuehren_dritte])
        mdat_erheben_code = "2.16.840.1.113883.3.1937.777.24.5.3.6"
        mdat_erheben_display = "MDAT erheben"
        mdat_erheben = TermCode(consent_system, mdat_erheben_code, mdat_erheben_display)
        mdat_erheben_fixed_critiera = FixedCriteria("coding", "mii-provision-provision-code",
                                                    "provision.provision.code", [mdat_erheben])

        mdat_speichern_verarbeiten_code = "2.16.840.1.113883.3.1937.777.24.5.3.7"
        mdat_speichern_verarbeiten_display = "MDAT speichern/verarbeiten"
        mdat_speichern_verarbeiten = TermCode(consent_system, mdat_speichern_verarbeiten_code,
                                              mdat_speichern_verarbeiten_display)
        mdat_speichern_verarbeiten_fixed_critiera = FixedCriteria("coding", "mii-provision-provision-code",
                                                                  "provision.provision.code",
                                                                  [mdat_speichern_verarbeiten])
        mdat_wissenschaftlich_nutzen_eu_dsgvo_niveau_code = "2.16.840.1.113883.3.1937.777.24.5.3.8"
        mdat_wissenschaftlich_nutzen_eu_dsgvo_niveau_display = "MDAT wissenschaftlich nutzen EU DSGVO NIVEAU"
        mdat_wissenschaftlich_nutzen_eu_dsgvo_niveau = TermCode(consent_system,
                                                                mdat_wissenschaftlich_nutzen_eu_dsgvo_niveau_code,
                                                                mdat_wissenschaftlich_nutzen_eu_dsgvo_niveau_display)
        mdat_wissenschaftlich_nutzen_eu_dsgvo_niveau_fixed_critiera = FixedCriteria("coding",
                                                                                    "mii-provision-provision-code",
                                                                                    "provision.provision.code",
                                                                                    [
                                                                                        mdat_wissenschaftlich_nutzen_eu_dsgvo_niveau])

        mdat_zusammenfuehren_dritte_code = "2.16.840.1.113883.3.1937.777.24.5.3.9"
        mdat_zusammenfuehren_dritte_display = "MDAT zusammenfuehren mit Dritte"
        mdat_zusammenfuehren_dritte = TermCode(consent_system, mdat_zusammenfuehren_dritte_code,
                                               mdat_zusammenfuehren_dritte_display)
        mdat_zusammenfuehren_dritte_fixed_critiera = FixedCriteria("coding", "mii-provision-provision-code",
                                                                   "provision.provision.code",
                                                                   [mdat_zusammenfuehren_dritte])

        patdat_erheben_speichern_nutzen_code = "2.16.840.1.113883.3.1937.777.24.5.3.1"
        patdat_erheben_speichern_nutzen_display = "PATDAT erheben/speichern/nutzen"
        patdat_erheben_speichern_nutzen = TermCode(consent_system, patdat_erheben_speichern_nutzen_code,
                                                   patdat_erheben_speichern_nutzen_display)
        patdat_erheben_speichern_nutzen_fixed_critiera = FixedCriteria("coding", "mii-provision-provision-code",
                                                                       "provision.provision.code",
                                                                       [patdat_erheben_speichern_nutzen])
        rekontaktierung_ergaenzungen_code = "2.16.840.1.113883.3.1937.777.24.5.3.26"
        rekontaktierung_ergaenzungen_display = "Rekontaktierung/Ergaenzungen"
        rekontaktierung_ergaenzungen = TermCode(consent_system, rekontaktierung_ergaenzungen_code,
                                                rekontaktierung_ergaenzungen_display)
        rekontaktierung_ergaenzungen_fixed_critiera = FixedCriteria("coding", "mii-provision-provision-code",
                                                                    "provision.provision.code",
                                                                    [rekontaktierung_ergaenzungen])

        self.fixedCriteria = [active_fixed_criteria, idat_bereitstellen_eu_dsgvo_niveau_fixed_critiera,
                              idat_erheben_fixed_critiera,
                              idat_speichern_verarbeiten_fixed_critiera,
                              idat_zusammenfuehren_dritte_fixed_critiera, mdat_erheben_fixed_critiera,
                              mdat_speichern_verarbeiten_fixed_critiera,
                              mdat_wissenschaftlich_nutzen_eu_dsgvo_niveau_fixed_critiera,
                              mdat_zusammenfuehren_dritte_fixed_critiera,
                              patdat_erheben_speichern_nutzen_fixed_critiera,
                              rekontaktierung_ergaenzungen_fixed_critiera]


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
        country_of_travel = TermCode("http://loinc.org", "94651-7", "Country of travel")
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
        completed = TermCode("http://hl7.org/fhir/event-status", "completed", "completed")
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
        active = TermCode("http://hl7.org/fhir/CodeSystem/medication-admin-status", "active", "active")
        completed = TermCode("http://hl7.org/fhir/CodeSystem/medication-admin-status", "completed", "completed")
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
        active = TermCode("http://hl7.org/fhir/CodeSystem/medication-statement-status", "active", "active")
        completed = TermCode("http://hl7.org/fhir/CodeSystem/medication-statement-status", "completed", "completed")
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


class MIIAgeMapEntry(MapEntry):
    def __init__(self, term_code):
        super().__init__(term_code)
        self.fhirResourceType = "Patient"
        self.valueSearchParameter = "birthDate"
        self.valueFhirPath = "birthDate"
        self.valueType = "Age"


class MIIGenderMapEntry(MapEntry):
    def __init__(self, term_code):
        super().__init__(term_code)
        self.fhirResourceType = "Patient"
        self.valueSearchParameter = "gender"
        self.valueFhirPath = "gender"
        self.valueType = "code"
        self.valueTypeFhir = "code"


class ProcedureMapEntry(MapEntry):
    def __init__(self, term_code):
        super().__init__(term_code)
        self.termCodeSearchParameter = "code"
        self.valueSearchParameter = None
        self.fhirResourceType = "Procedure"
        completed = TermCode("http://hl7.org/fhir/event-status", "completed", "completed")
        in_progress = TermCode("http://hl7.org/fhir/event-status", "in-progress", "in-progress")
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
        confirmed = TermCode("http://terminology.hl7.org/CodeSystem/condition-ver-status", "confirmed", "confirmed")
        # self.fixedCriteria = [FixedCriteria("coding", "verification-status", "verificationStatus", [confirmed])]
        self.timeRestrictionParameter = "recorded-date"
        self.timeRestrictionPath = "onset"


def str_to_class(class_name):
    return getattr(sys.modules[__name__], class_name)


def generate_child_entries(children, class_name):
    result = SortedSet()
    for child in children:
        if child.fhirMapperType:
            class_name = child.fhirMapperType + "MapEntry"
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
