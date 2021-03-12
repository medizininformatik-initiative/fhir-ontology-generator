from UiDataModel import TermCode, del_keys, del_none
import json
import sys


class FixedCriteria:
    def __init__(self, search_parameter, value=[]):
        self.value = value
        self.searchParameter = search_parameter


class MapEntry:
    DO_NOT_SERIALIZE = ["DO_NOT_SERIALIZE"]

    def __init__(self, term_code, fhir_resource_type, term_code_target, value_target=None, fixed_criteria=[]):
        self.termCode = term_code
        self.termCodeSearchParameter = term_code_target
        self.valueSearchParameter = value_target
        self.fhirResourceType = fhir_resource_type
        self.fixedCriteria = fixed_criteria

    def to_json(self):
        return json.dumps(self, default=lambda o: del_none(
            del_keys(o.__dict__, self.DO_NOT_SERIALIZE)), sort_keys=True, indent=4)


class QuantityObservationMapEntry(MapEntry):
    def __init__(self, term_code):
        self.termCodeSearchParameter = "code"
        self.valueSearchParameter = "value-quantity"
        self.fhirResourceType = "Observation"
        self.termCode = term_code
        self.fixedCriteria = []


class ConceptObservationMapEntry(MapEntry):
    def __init__(self, term_code):
        self.termCodeSearchParameter = "code"
        self.valueSearchParameter = "value-concept"
        self.fhirResourceType = "Observation"
        self.termCode = term_code
        self.fixedCriteria = []


class ConditionMapEntry(MapEntry):
    def __init__(self, term_code):
        self.termCodeSearchParameter = "code"
        self.valueSearchParameter = None
        self.fhirResourceType = "Condition"
        self.fixedCriteria = [FixedCriteria("verification-status", ["confirmed"])]
        self.termCode = term_code


class ProcedureMapEntry(MapEntry):
    def __init__(self, term_code):
        self.termCodeSearchParameter = "code"
        self.valueSearchParameter = None
        self.fhirResourceType = "Procedure"
        self.fixedCriteria = [FixedCriteria("status", ["completed", "in-progress"])]
        self.termCode = term_code


class SymptomMapEntry(MapEntry):
    def __init__(self, term_code):
        self.termCodeSearchParameter = "code"
        self.valueSearchParameter = "severity"
        self.fhirResourceType = "Condition"
        self.fixedCriteria = [FixedCriteria("verification-status", ["confirmed"])]
        self.termCode = term_code


class MedicationStatementMapEntry(MapEntry):
    def __init__(self, term_code):
        self.termCodeSearchParameter = "code"
        self.fhirResourceType = "MedicationStatement"
        self.valueSearchParameter = None
        self.fixedCriteria = [FixedCriteria("status", ["active", "completed"])]
        self.termCode = term_code


class ImmunizationMapEntry(MapEntry):
    def __init__(self, term_code):
        self.termCodeSearchParameter = "vaccine-code"
        self.fhirResourceType = "Immunization"
        self.valueSearchParameter = None
        self.fixedCriteria = [FixedCriteria("status", ["completed"])]
        self.termCode = term_code


class DiagnosticReportMapEntry(MapEntry):
    def __init__(self, term_code):
        self.termCodeSearchParameter = "code"
        self.fhirResourceType = "DiagnosticReport"
        self.valueSearchParameter = None
        self.fixedCriteria = []
        self.termCode = term_code


def generate_child_entries(children, class_name):
    result = []
    for child in children:
        result.append(str_to_class(class_name)(child.termCode))
        result += generate_child_entries(child.children, class_name)
    return result


def generate_map(categories):
    result = []
    for category in categories:
        for terminology in category.children:
            if terminology.fhirMapperType:
                class_name = terminology.fhirMapperType + "MapEntry"
                result.append(str_to_class(class_name)(terminology.termCode))
                result += generate_child_entries(terminology.children, class_name)
            else:
                print(terminology)
    return result


def str_to_class(class_name):
    return getattr(sys.modules[__name__], class_name)
