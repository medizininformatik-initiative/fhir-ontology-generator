# In theory every term_code has a ui_profile and a mapping. But in FHIR every FHIR Profile defines a set of termCodes
# which all have the same ui_profile and mapping profile. Typically this set of termCodes is defined by a valueSet.
# We store the information of the all term_codes within a value_set that have the same mapping and ui profile in the
# profile class. This serves two purposes. One the one hand this is the fundamental structure if we decide to use an
# terminology server in the future to resolve the term_codes.
# On the other hand we can use the identified value_sets to create a stitching between GECCO FHIR and GECCO AQL.
# In particular this is necessary to reduce the amount of compares between the datasets. The number of valueSets
# compares are << the number of termCode compares.
# Finally the Profile class could also be used to load profiles. All that needs to be defined is the mapping, the
# ui profile and the valueSet
import json

from TerminologService.ValueSetResolver import get_value_sets_by_path, get_term_codes_by_path
from model.UiDataModel import del_none, del_keys

profile_term_code_defining_path = {
    "Age": "",
    "Condition": "Condition.code.coding",
    "Consent": "Consent.provision.code",
    "DependencyOnVentilator": "Condition.code.coding",
    "DiagnosisCovid19": "Condition.code.coding",  # path
    "DiagnosticReport": "DiagnosticReport.conclusionCode",
    "EthnicGroup": "",
    "Observation": "Observation.code.coding",  # path
    "Immunization": "Immunization.vaccineCode.coding",
    "MedicationAdministration": "Medication.code.coding",  # path
    "MedicationStatement": "MedicationStatement.medication[x].coding",  # path
    "Patient": "",
    "Procedure": "Procedure.code.coding",
    "ResuscitationStatus": "Consent.category.coding.system",  # path
    "SmokingStatus": "Observation.code",  # modeled different...
    "Specimen": "",  # explicit vs...
    "Symptom": "Condition.code.coding:sct"
}


class Profile:
    DO_NOT_SERIALIZE = ["DO_NOT_SERIALIZE"]

    def __init__(self, name, term_codes, mapping, ui_profile, value_set):
        self.name = name
        self.termCodesDefiningId = None
        self.valueSet = value_set
        self.termCodes = term_codes
        self.mappingProfile = mapping
        self.uiProfile = ui_profile

    def __repr__(self):
        return self.name + " " + self.termCodes.__repr__() + " " + self.valueSet.__repr__()

    def to_json(self):
        return json.dumps(self, default=lambda o: del_none(
            del_keys(o.__dict__, self.DO_NOT_SERIALIZE)), sort_keys=True, indent=4)

    @staticmethod
    def generate_profile(terminology_entry, profile_data):
        element_id = profile_term_code_defining_path[profile_data["name"]] \
            if (profile_data["name"] in profile_term_code_defining_path) \
            else profile_term_code_defining_path[profile_data["type"]]
        name = profile_data["name"]
        ui_profile = profile_data["name"]
        mapping = profile_data["type"] if profile_data["type"] in profile_term_code_defining_path else profile_data[
            "name"]
        value_sets = get_value_sets_by_path(element_id, profile_data)
        term_codes = []
        # only collect specific term_codes if no value_set is found
        # as this only triggers for empty vs path should be "good enough"
        if not value_sets:
            term_codes = get_term_codes_by_path(element_id, profile_data)
        # Each Profile has to have at least one term_code. If none is defined in the profile directly or indirectly via
        # a value set we add our own.
        if not term_codes:
            term_codes.append(terminology_entry.termCode)
        return Profile(name, term_codes, ui_profile, mapping, value_sets)
