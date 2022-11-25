import json
import os

from lxml import etree

from Helper import get_term_selectable_leaf_codes_from_ui_profile
from geccoToAqlMapping import get_open_ehr_type, get_value_path_list
from model.AQLMappingDatatModel import AQLMapEntry
from model.MappingDataModel import MapEntryList
from model.UiDataModel import TermCode


def generate_specimen_mapping(term_code):
    pass


def generate_diagnose_mapping(term_code):
    ehr_template = etree.parse(f"resources\\openehr\\templates\\KDS\\KDS_Diagnose.oet")
    term_code_archetype = "openEHR-EHR-EVALUATION.problem_diagnosis.v1"
    term_code_path = "/data[at0001]/items[at0002]"
    tc_path, tc_open_ehr_type = get_open_ehr_type(term_code_archetype, term_code_path)
    tc_path_list = get_value_path_list(ehr_template, term_code_archetype)
    tc_value_path = term_code_path + f"/{tc_path}"
    return AQLMapEntry(term_code, tc_open_ehr_type, tc_value_path, tc_path_list, None, None)


def generate_consent_mapping(term_code):
    pass


def generate_lab_mapping(term_code):
    ehr_template = etree.parse(f"resources\\openehr\\templates\\KDS\\KDS_Laborbericht.oet")
    term_code_archetype = "openEHR-EHR-CLUSTER.laboratory_test_analyte.v1"
    term_code_path = "/items[at0024]"
    value_archetype = "openEHR-EHR-CLUSTER.laboratory_test_analyte.v1"
    value_path = "/items[at0001]"
    tc_path, tc_open_ehr_type = get_open_ehr_type(term_code_archetype, term_code_path)
    tc_path_list = get_value_path_list(ehr_template, term_code_archetype)
    tc_value_path = term_code_path + f"/{tc_path}"
    path, value_open_ehr_type = get_open_ehr_type(value_archetype, value_path)
    value_path_list = get_value_path_list(ehr_template, value_archetype)
    value_value_path = value_path + f"/{path}"
    return AQLMapEntry(term_code, value_open_ehr_type, tc_value_path, tc_path_list, value_value_path,
                       value_path_list)


def generate_medication_mapping(term_code):
    ehr_template = etree.parse(f"resources\\openehr\\templates\\KDS\\KDS_Medikamentenverabreichungen.oet")
    term_code_archetype = "openEHR-EHR-CLUSTER.drug_class.v0"
    term_code_path = "/items[at0001]"
    tc_path, tc_open_ehr_type = get_open_ehr_type(term_code_archetype, term_code_path)
    tc_path_list = get_value_path_list(ehr_template, term_code_archetype)
    tc_value_path = term_code_path + f"/{tc_path}"
    return AQLMapEntry(term_code, tc_open_ehr_type, tc_value_path, tc_path_list, None, None)


def generate_procedure_mapping(term_code):
    ehr_template = etree.parse(f"resources\\openehr\\templates\\KDS\\KDS_Prozedur.oet")
    term_code_archetype = "openEHR-EHR-ACTION.procedure.v1"
    term_code_path = "/description[at0001]/items[at0002]"
    tc_path, tc_open_ehr_type = get_open_ehr_type(term_code_archetype, term_code_path)
    tc_path_list = get_value_path_list(ehr_template, term_code_archetype)
    tc_value_path = term_code_path + f"/{tc_path}"
    return AQLMapEntry(term_code, tc_open_ehr_type, tc_value_path, tc_path_list, None, None)


def generate_demographic_mapping(term_code):
    ehr_template = etree.parse(f"resources\\openehr\\templates\\KDS\\KDS_Person.oet")
    term_code_archetype = "openEHR-EHR-EVALUATION.gender.v1"
    term_code_path = "/data[at0002]/items[at0022]"
    path, open_ehr_type = get_open_ehr_type(term_code_archetype, term_code_path)
    value_path_list = get_value_path_list(ehr_template, term_code_archetype)
    value_value_path = term_code_path + f"/{path}"
    return AQLMapEntry(term_code, open_ehr_type, None, None, value_value_path, value_path_list)


# TODO: This should be done using vs lookups, but that is to slow in the development phase
def generate_aql_mapping(term_code: TermCode):
    if term_code.system == "http://snomed.info/sct":
        return generate_specimen_mapping(term_code)
    elif term_code.system == "http://loinc.org":
        return generate_lab_mapping(term_code)
    elif term_code.system == "http://fhir.de/CodeSystem/bfarm/icd-10-gm":
        return generate_diagnose_mapping(term_code)
    elif term_code.system == "http://fhir.de/CodeSystem/bfarm/atc":
        return generate_medication_mapping(term_code)
    elif term_code.system == "http://fhir.de/CodeSystem/bfarm/ops":
        return generate_procedure_mapping(term_code)
    elif term_code.system == "urn:oid:2.16.840.1.113883.3.1937.777.24.5.1":
        return generate_consent_mapping(term_code)
    elif term_code.system == "mii.abide":
        return generate_demographic_mapping(term_code)
    else:
        print(f"no mapping generated for: {term_code}")


if __name__ == "__main__":
    map_entries = MapEntryList()
    for ui_profile_name in [f.name for f in os.scandir("ui-profiles/") if f.name != "GECCO.json"]:
        with open("ui-profiles/" + ui_profile_name, 'r', encoding="utf-8") as ui_profile_json:
            ui_profile = json.load(ui_profile_json)
            entries_requiring_map_entry = get_term_selectable_leaf_codes_from_ui_profile(ui_profile)
            for termCode in entries_requiring_map_entry:
                if entry := generate_aql_mapping(termCode):
                    map_entries.entries.add(entry)
    map_entries_file = open("mapping/" + "kds-aql-mapping.json", 'w')
    map_entries_file.write(map_entries.to_json())
