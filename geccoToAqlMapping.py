import os
import re

from lxml import etree

from ProfileAnalyzer.OpenEHRTemplateAnalyzer import extract_vs_canonical_url, get_value_sets_from_combined_definition
from TerminologService.ValueSetResolver import get_system_from_code, get_termcodes_from_onto_server
from model.Exceptions import UnknownHandlingException
from model.MappingDataModel import MapEntryList
from model.UiDataModel import TermCode
from model.AQLMappingDatatModel import AQLMapEntry, ValuePathElement

COLOGNE_ONTO_SERVER = "https://ontoserver.imi.uni-luebeck.de/koeln/fhir/"


def get_term_codes_from_annotations(template, path):
    results = []
    for annotation in template.xpath("/xmlns:template/xmlns:annotations",
                                     namespaces={"xmlns": "openEHR/v1/Template"}):
        if annotation.get("path") == path:
            for items in annotation:
                for item in items:
                    code = None
                    display = None
                    system = None
                    for k_or_v in item:
                        if k_or_v.tag == "{openEHR/v1/Template}key":
                            code = k_or_v.text
                        elif k_or_v.tag == "{openEHR/v1/Template}value":
                            display = k_or_v.text
                        else:
                            raise Exception(f"Unknown tag for {k_or_v}")
                        if code and display:
                            systems = get_system_from_code(code, COLOGNE_ONTO_SERVER)
                            if len(systems) == 1:
                                results.append(TermCode(systems[0], code, display))
    return results


def extract_node_ids_from_path(path):
    return re.findall(r"\[([A-Za-z0-9_]+)\]", path)


def get_open_ehr_type_attrib(element):
    return element.get("{http://www.w3.org/2001/XMLSchema-instance}type").replace("tem:", "")


def get_full_path(element, path):
    element = element.getparent()
    if archetype_id := element.get("archetype_id"):
        open_ehr_type = get_open_ehr_type_attrib(element)
        path_elem = ValuePathElement(open_ehr_type, archetype_id)
        path.insert(0, path_elem)
        return get_full_path(element, path)
    return path


def get_value_path_list(template, leaf_archetype):
    for content in template.iter("{openEHR/v1/Template}Content"):
        if content.get("archetype_id") == leaf_archetype:
            open_ehr_type = get_open_ehr_type_attrib(content)
            leaf_path = ValuePathElement(open_ehr_type, leaf_archetype)
            return get_full_path(content, [leaf_path])

    for item in template.iter("{openEHR/v1/Template}Items"):
        if item.get("archetype_id") == leaf_archetype:
            open_ehr_type = get_open_ehr_type_attrib(item)
            leaf_path = ValuePathElement(open_ehr_type, leaf_archetype)
            return get_full_path(content, [leaf_path])


def walk_nodes(element, node_id):
    if not node_id:
        return element
    else:
        element = element.xpath(f"xmlns:attributes/xmlns:children[xmlns:node_id/text()=\'{node_id[0]}\']",
                                namespaces={"xmlns": "http://schemas.openehr.org/v1"})
        if len(element) != 1:
            print(len(element))
            raise Exception("too many elements")
        node_id.pop(0)
        return walk_nodes(element[0], node_id)


def get_ref_model_type(element):
    return element.xpath(f"xmlns:rm_type_name", namespaces={"xmlns": "http://schemas.openehr.org/v1"})[0].text


def get_ref_model_attribute_type(element):
    return element.xpath("xmlns:rm_attribute_name", namespaces={"xmlns": "http://schemas.openehr.org/v1"})[
        0].text


def parse_rm_element(element):
    # FIXME: What to do if no attribute is given?
    for attribute in element.xpath(f"xmlns:attributes", namespaces={"xmlns": "http://schemas.openehr.org/v1"}):
        rm_type_name = get_ref_model_attribute_type(attribute)
        return rm_type_name, parse_value(attribute)
    else:
        return "value", "DV_QUANTITY"


def parse_value(element):
    for child in element.xpath("xmlns:children", namespaces={"xmlns": "http://schemas.openehr.org/v1"}):
        return get_ref_model_type(child)



def get_sub_element_by_path(element, path):
    nodes = extract_node_ids_from_path(path)
    defining_element = walk_nodes(element, nodes)
    rm_type_name = get_ref_model_type(element)
    return parse_rm_element(defining_element)


def get_open_ehr_type(value_of_interest_archetype, value_of_interest_path):
    for archetype_file_name in os.listdir("resources/openehr/archetypes"):
        if value_of_interest_archetype == archetype_file_name.replace('.xml', ''):
            archetype = etree.parse(f"resources/openehr/archetypes/{archetype_file_name}")

            for definition in archetype.xpath("/xmlns:archetype/xmlns:definition",
                                              namespaces={"xmlns": "http://schemas.openehr.org/v1"}):
                path, open_ehr_type = get_sub_element_by_path(definition, value_of_interest_path)
                return path, open_ehr_type


def generate_annotation_based_mapping(template, term_code_defining_annotation, value_of_interest_archetype,
                                      value_of_interest_path):
    result = []
    path, open_ehr_type = get_open_ehr_type(value_of_interest_archetype, value_of_interest_path)
    value_path_list = get_value_path_list(template, value_of_interest_archetype)
    value_path = value_of_interest_path + f"/{path}"
    for term_code in get_term_codes_from_annotations(template, term_code_defining_annotation):
        entry = AQLMapEntry(term_code, open_ehr_type, None, None, value_path, value_path_list)
        result.append(entry)
    return result


def generate_value_set_based_mapping(template, value_of_interest_archetype, value_of_interest_path):
    result = []

    for vs in get_vs_from_rule(template, value_of_interest_path):
        if vs == "http://fhir.de/ValueSet/bfarm/alpha-id":
            continue
        path, open_ehr_type = get_open_ehr_type(value_of_interest_archetype, value_of_interest_path)
        value_path_list = get_value_path_list(template, value_of_interest_archetype)
        value_path = value_of_interest_path + f"/{path}"
        for term_code in get_termcodes_from_onto_server(vs, COLOGNE_ONTO_SERVER):
            entry = AQLMapEntry(term_code, open_ehr_type, value_path, value_path_list, None, None)
            result.append(entry)
    return result


def generate_value_set_based_mapping_with_value(template, term_code_archetype, term_code_path, value_archetype,
                                                value_path):
    result = []
    for vs in get_vs_from_rule(template, term_code_path):
        tc_path, tc_open_ehr_type = get_open_ehr_type(term_code_archetype, term_code_path)
        tc_path_list = get_value_path_list(template, term_code_archetype)
        tc_value_path = term_code_path + f"/{tc_path}"
        path, value_open_ehr_type = get_open_ehr_type(value_archetype, value_path)
        value_path_list = get_value_path_list(template, value_archetype)
        value_value_path = value_path + f"/{path}"
        for term_code in get_termcodes_from_onto_server(vs, COLOGNE_ONTO_SERVER):
            entry = AQLMapEntry(term_code, tc_open_ehr_type, tc_value_path, tc_path_list, value_value_path,
                                value_path_list)
            result.append(entry)
    return result


def get_vs_from_rule(template, path):
    value_sets = []
    for rule in template.iter("{openEHR/v1/Template}Rule"):
        if rule.get("path") == path:
            for constraint in rule:
                for term_query_id in constraint:
                    if term_query_id.tag == "{openEHR/v1/Template}termQueryId":
                        if vs_canonical_url := extract_vs_canonical_url(term_query_id.get("queryName")):
                            separated_value_sets = get_value_sets_from_combined_definition(vs_canonical_url)
                            value_sets += separated_value_sets
    print(value_sets)
    return value_sets


def generate_atemfrequenz_mapping(template):
    return generate_annotation_based_mapping(template, "[openEHR-EHR-COMPOSITION.registereintrag.v1]",
                                      "openEHR-EHR-OBSERVATION.respiration.v2",
                                      "/data[at0001]/events[at0002]/data[at0003]/items[at0004]")


def generate_beatmungswerte_mapping(template):
    return []


def generate_befundderblutgasanalyse_mapping(template):
    return []


def generate_blutdruck_mapping(template):
    # Systolic
    systolic_mapping = generate_annotation_based_mapping(template,
                                      "[openEHR-EHR-COMPOSITION.registereintrag.v1]/content["
                                      "openEHR-EHR-OBSERVATION.blood_pressure.v2]/data[at0001]/events[at0006]/data["
                                      "at0003]/items[at0004]",
                                      "openEHR-EHR-OBSERVATION.blood_pressure.v2",
                                      "/data[at0001]/events[at0006]/data[at0003]/items[at0004]")
    # Diastolic
    diastolic_mapping = generate_annotation_based_mapping(template,
                                      "[openEHR-EHR-COMPOSITION.registereintrag.v1]/content["
                                      "openEHR-EHR-OBSERVATION.blood_pressure.v2]/data[at0001]/events[at0006]/data["
                                      "at0003]/items[at0005]",
                                      "openEHR-EHR-OBSERVATION.blood_pressure.v2",
                                      "/data[at0001]/events[at0006]/data[at0003]/items[at0005]")

    return [*systolic_mapping, *diastolic_mapping]

def generate_dnr_anordnung_mapping(template):
    return generate_annotation_based_mapping(template,
                                      "[openEHR-EHR-COMPOSITION.registereintrag.v1]/content["
                                      "openEHR-EHR-EVALUATION.advance_care_directive.v1]",
                                      "openEHR-EHR-EVALUATION.advance_care_directive.v1",
                                      "/data[at0001]/items[at0006]")


def generate_gecco_diagnose_mapping(template):
    return generate_value_set_based_mapping(template,
                                     "openEHR-EHR-EVALUATION.problem_diagnosis.v1",
                                     "/data[at0001]/items[at0002]")


def generate_gecco_entlassungsdaten_mapping(template):
    # TODO: Template is crude nonsense
    term_code = TermCode(system="http://loinc.org", code="55128-3",
                         display="Discharge disposition")
    value_of_interest_archetype = "openEHR-EHR-ADMIN_ENTRY.discharge_summary.v0"
    value_of_interest_path = "/data[at0001]/items[at0040]"
    path, open_ehr_type = get_open_ehr_type(value_of_interest_archetype, value_of_interest_path)
    value_path_list = get_value_path_list(template, value_of_interest_archetype)
    value_of_interest_path += f"/{path}"
    entry = AQLMapEntry(term_code, open_ehr_type, None, None, value_of_interest_path, value_path_list)
    return [entry]


def generate_gecco_laborbefund_mapping(template):
    return generate_value_set_based_mapping_with_value(template, "openEHR-EHR-CLUSTER.laboratory_test_analyte.v1",
                                                "/items[at0024]",
                                                "openEHR-EHR-CLUSTER.laboratory_test_analyte.v1",
                                                "/items[at0001]")


def generate_gecco_medikation_mapping(template):
    # COVID-19 Therapie
    return generate_value_set_based_mapping(template,
                                     "openEHR-EHR-OBSERVATION.medication_statement.v0",
                                     "/data[at0001]/events[at0002]/data[at0003]/items[at0006]")


def generate_gecco_personendaten_mapping(template):
    # Age
    age = generate_annotation_based_mapping(template,
                                      "[openEHR-EHR-COMPOSITION.registereintrag.v1]/content["
                                      "openEHR-EHR-OBSERVATION.age.v0]",
                                      "openEHR-EHR-OBSERVATION.age.v0",
                                      "/data[at0001]/events[at0002]/data[at0003]/items[at0004]")
    # Ethnic Group
    ethnic_group = generate_annotation_based_mapping(template,
                                      "[openEHR-EHR-COMPOSITION.registereintrag.v1]/content["
                                      "openEHR-EHR-ADMIN_ENTRY.person_data.v0]/data[at0001]/items["
                                      "openEHR-EHR-CLUSTER.ethnischer_hintergrund.v0]",
                                      "openEHR-EHR-CLUSTER.ethnischer_hintergrund.v0",
                                      "/items[at0002]")
    # Gender at birth
    gender_at_birth = generate_annotation_based_mapping(template,
                                      "[openEHR-EHR-COMPOSITION.registereintrag.v1]/content[openEHR-EHR-EVALUATION.gender.v1]",
                                      "openEHR-EHR-EVALUATION.gender.v1",
                                      "/data[at0002]/items[at0019]")
    return [*age, *ethnic_group, *gender_at_birth]


def generate_gecco_prozedur_mapping(template):
    return generate_value_set_based_mapping(template,
                                     "openEHR-EHR-ACTION.procedure.v1",
                                     "/description[at0001]/items[at0002]")


def generate_gecco_radiologischerbefund_mapping(template):
    # TODO: likely this should be: LOINC::18748-4::Diagnostic imaging study, double check with fhir implementation,
    #  currently matches fhir implementation
    term_code = TermCode(code="118247008",
                         display="Radiologic finding (finding)",
                         system="http://snomed.info/sct")
    value_of_interest_archetype = "openEHR-EHR-OBSERVATION.imaging_exam_result.v0"
    value_of_interest_path = "/data[at0001]/events[at0002]/data[at0003]/items[at0008]"
    path, open_ehr_type = get_open_ehr_type(value_of_interest_archetype, value_of_interest_path)
    value_path_list = get_value_path_list(template, value_of_interest_archetype)
    value_of_interest_path += f"/{path}"
    entry = AQLMapEntry(term_code, open_ehr_type, None, None, value_of_interest_path, value_path_list)
    return [entry]


def generate_gecco_serologischerbefund_mapping(template):
    return generate_value_set_based_mapping_with_value(template, "openEHR-EHR-CLUSTER.laboratory_test_analyte.v1",
                                                "/items[at0024]",
                                                "openEHR-EHR-CLUSTER.laboratory_test_analyte.v1",
                                                "/items[at0001]")


def generate_gecco_studienteilnahme_mapping(template):
    term_code_interventional = TermCode(
        system="https://www.netzwerk-universitaetsmedizin.de/fhir/CodeSystem/ecrf-parameter-codes",
        code="03",
        display="Participation in interventional clinical trials")
    value_of_interest_archetype = "openEHR-EHR-EVALUATION.gecco_study_participation.v0"
    value_of_interest_path = "/data[at0001]/items[at0002]"
    path, open_ehr_type = get_open_ehr_type(value_of_interest_archetype, value_of_interest_path)
    value_path_list = get_value_path_list(template, value_of_interest_archetype)
    value_path = value_of_interest_path + f"/{path}"
    entry_interventional = AQLMapEntry(term_code_interventional, open_ehr_type, None, None, value_path, value_path_list)

    term_code_covid = TermCode(
        system="https://www.netzwerk-universitaetsmedizin.de/fhir/CodeSystem/ecrf-parameter-codes",
        code="02",
        display="Study inclusion due to Covid-19"
    )
    value_of_interest_path = "/items[at0014]"
    value_of_interest_archetype = "openEHR-EHR-CLUSTER.study_participation.v1"
    path, open_ehr_type = get_open_ehr_type(value_of_interest_archetype, value_of_interest_path)
    value_path_list = get_value_path_list(template, value_of_interest_archetype)
    value_path = value_of_interest_path + f"/{path}"
    entry_covid = AQLMapEntry(term_code_covid, open_ehr_type, None, None, value_path, value_path_list)
    return [entry_interventional, entry_covid]


def generate_gecco_virologischerbefund_mapping(template):
    term_code = TermCode(code="94500-6",
                         display="SARS-CoV-2 (COVID-19) RNA [Presence] in Respiratory specimen by NAA with probe "
                                "detection",
                         system="http://loinc.org")
    value_of_interest_archetype = "openEHR-EHR-CLUSTER.laboratory_test_analyte.v1"
    value_of_interest_path = "/items[at0001]"
    path, open_ehr_type = get_open_ehr_type(value_of_interest_archetype, value_of_interest_path)
    value_path_list = get_value_path_list(template, value_of_interest_archetype)
    value_of_interest_path += f"/{path}"
    entry = AQLMapEntry(term_code, open_ehr_type, None, None, value_of_interest_path, value_path_list)
    return [entry]


def generate_herzfrequenz_mapping(template):
    return generate_annotation_based_mapping(template,
                                      "[openEHR-EHR-COMPOSITION.registereintrag.v1]/content["
                                      "openEHR-EHR-OBSERVATION.pulse.v2]",
                                      "openEHR-EHR-OBSERVATION.pulse.v2",
                                      "/data[at0002]/events[at0003]")


def generate_impfstatus_mapping(template):
    # snomed
    impfstatus_snomed = generate_value_set_based_mapping(template,
                                     "openEHR-EHR-ACTION.medication.v1",
                                     "/description[at0017]/items[at0020]")
    # ATC (missing in profile)
    impfstatus_atc = []
    vs = "https://www.netzwerk-universitaetsmedizin.de/fhir/ValueSet/vaccines-atc"
    value_of_interest_archetype = "openEHR-EHR-ACTION.medication.v1"
    value_of_interest_path = "/description[at0017]/items[at0020]"
    for term_code in get_termcodes_from_onto_server(vs, COLOGNE_ONTO_SERVER):
        path, open_ehr_type = get_open_ehr_type(value_of_interest_archetype, value_of_interest_path)
        value_path_list = get_value_path_list(template, value_of_interest_archetype)
        value_path = value_of_interest_path + f"/{path}"
        entry = AQLMapEntry(term_code, open_ehr_type, value_path, value_path_list, None, None)
        impfstatus_atc.append(entry)
    return [*impfstatus_snomed, *impfstatus_atc]


def generate_klinischefrailty_skala_mapping(template):
    return generate_annotation_based_mapping(template,
                                      "[openEHR-EHR-COMPOSITION.registereintrag.v1]/content[openEHR-EHR-OBSERVATION.clinical_frailty_scale.v1]",
                                      "openEHR-EHR-OBSERVATION.clinical_frailty_scale.v1",
                                      "/data[at0001]/events[at0002]/data[at0003]/items[at0004]")


def generate_koerpertemperatur_mapping(template):
    return generate_annotation_based_mapping(template,
                                      "[openEHR-EHR-COMPOSITION.registereintrag.v1]/content[openEHR-EHR-OBSERVATION.body_temperature.v2]",
                                      "openEHR-EHR-OBSERVATION.body_temperature.v2",
                                      "/data[at0002]/events[at0003]/data[at0001]/items[at0004]")


def generate_körpergewicht_mapping(template):
    # Using any event at birth is not supported!
    return generate_annotation_based_mapping(template,
                                      "[openEHR-EHR-COMPOSITION.registereintrag.v1]/content["
                                      "openEHR-EHR-OBSERVATION.body_weight.v2]",
                                      "openEHR-EHR-OBSERVATION.body_weight.v2",
                                      "/data[at0002]/events[at0003]/data[at0001]/items[at0004]")


def generate_körpergröße_mapping(template):
    # No clear rule in oet
    return generate_annotation_based_mapping(template,
                                      "[openEHR-EHR-COMPOSITION.registereintrag.v1]/content["
                                      "openEHR-EHR-OBSERVATION.height.v2]",
                                      "openEHR-EHR-OBSERVATION.height.v2",
                                      "/data[at0001]/events[at0002]/data[at0003]/items[at0004]")


def generate_patientauficu_mapping(template):
    return generate_annotation_based_mapping(template,
                                      "[openEHR-EHR-COMPOSITION.registereintrag.v1]/content["
                                      "openEHR-EHR-OBSERVATION.management_screening.v0]",
                                      "openEHR-EHR-OBSERVATION.management_screening.v0",
                                      "/data[at0001]/events[at0002]/data[at0003]/items[at0022]/items[at0005]")


def generate_pulsoxymetrie_mapping(template):
    return generate_annotation_based_mapping(template,
                                      "[openEHR-EHR-COMPOSITION.registereintrag.v1]/content["
                                      "openEHR-EHR-OBSERVATION.pulse_oximetry.v1]",
                                      "openEHR-EHR-OBSERVATION.pulse_oximetry.v1",
                                      "/data[at0001]/events[at0002]/data[at0003]/items[at0006]")


def generate_raucherstatus_mapping(template):
    return generate_annotation_based_mapping(template,
                                      "[openEHR-EHR-COMPOSITION.registereintrag.v1]/content["
                                      "openEHR-EHR-EVALUATION.tobacco_smoking_summary.v1]",
                                      "openEHR-EHR-EVALUATION.tobacco_smoking_summary.v1",
                                      "/data[at0001]/items[at0043]")


def generate_reisehistorie_mapping(template):
    return generate_annotation_based_mapping(template,
                                      "[openEHR-EHR-COMPOSITION.registereintrag.v1]/content["
                                      "openEHR-EHR-ADMIN_ENTRY.travel_event.v0]",
                                      "openEHR-EHR-ADMIN_ENTRY.travel_event.v0",
                                      "/data[at0001]/items[at0010]/items[at0011]"
                                      )


def generate_sars_cov_2exposition_mapping(template):
    return generate_annotation_based_mapping(template, "[openEHR-EHR-COMPOSITION.registereintrag.v1]",
                                      "openEHR-EHR-EVALUATION.infectious_exposure.v0",
                                      "/data[at0001]/items[at0003]")


def generate_schwangerschaftsstatus_mapping(template):
    return generate_annotation_based_mapping(template,
                                      "[openEHR-EHR-COMPOSITION.registereintrag.v1]/content["
                                      "openEHR-EHR-OBSERVATION.pregnancy_status.v0]",
                                      "openEHR-EHR-OBSERVATION.pregnancy_status.v0",
                                      "/data[at0001]/events[at0002]/data[at0003]/items[at0011]")


def generate_sofa_mapping(template):
    term_code = TermCode(code="06",
                         display="SOFA-Score",
                         system="https://www.netzwerk-universitaetsmedizin.de/fhir/CodeSystem/ecrf-parameter-codes")
    value_of_interest_archetype = "openEHR-EHR-OBSERVATION.sofa_score.v0"
    value_of_interest_path = "/data[at0001]/events[at0002]/data[at0003]/items[at0041]"
    path, open_ehr_type = get_open_ehr_type(value_of_interest_archetype, value_of_interest_path)
    value_path_list = get_value_path_list(template, value_of_interest_archetype)
    value_of_interest_path += f"/{path}"
    entry = AQLMapEntry(term_code, open_ehr_type, None, None, value_of_interest_path, value_path_list)
    return [entry]


def generate_symptom_mapping(template):
    return generate_value_set_based_mapping_with_value(template, "openEHR-EHR-OBSERVATION.symptom_sign.v0",
                                                "/data[at0190]/events[at0191]/data[at0192]/items[at0001]",
                                                "openEHR-EHR-OBSERVATION.symptom_sign.v0",
                                                "/data[at0190]/events[at0191]/data[at0192]/items[at0021]")


def generate_aql_mapping():
    result = MapEntryList()
    for filename in os.listdir("resources/openehr/templates"):
        ehr_template = etree.parse(f"resources\\openehr\\templates\\{filename}")
        name = ehr_template.xpath("/xmlns:template/xmlns:name", namespaces={"xmlns": "openEHR/v1/Template"})[
            0].text
        if name in template_translation_mapping:
            entries = template_translation_mapping.get(name)(ehr_template)
            for entry in entries:
                result.entries.add(entry)
        else:
            raise UnknownHandlingException(name)
    return result


template_translation_mapping = {
    "Atemfrequenz": generate_atemfrequenz_mapping,
    "Beatmungswerte": generate_beatmungswerte_mapping,
    "Befund der Blutgasanalyse": generate_befundderblutgasanalyse_mapping,
    "Blutdruck": generate_blutdruck_mapping,
    "DNR-Anordnung": generate_dnr_anordnung_mapping,
    "GECCO_Diagnose": generate_gecco_diagnose_mapping,
    "GECCO_Entlassungsdaten": generate_gecco_entlassungsdaten_mapping,
    "GECCO_Laborbefund": generate_gecco_laborbefund_mapping,
    "GECCO_Medikation": generate_gecco_medikation_mapping,
    "GECCO_Personendaten": generate_gecco_personendaten_mapping,
    "GECCO_Prozedur": generate_gecco_prozedur_mapping,
    "GECCO_Radiologischer Befund": generate_gecco_radiologischerbefund_mapping,
    "GECCO_Serologischer Befund": generate_gecco_serologischerbefund_mapping,
    "GECCO_Studienteilnahme": generate_gecco_studienteilnahme_mapping,
    "GECCO_Virologischer Befund": generate_gecco_virologischerbefund_mapping,
    "Herzfrequenz": generate_herzfrequenz_mapping,
    "Impfstatus": generate_impfstatus_mapping,
    "Klinische Frailty-Skala": generate_klinischefrailty_skala_mapping,
    "Koerpertemperatur": generate_koerpertemperatur_mapping,
    "Körpergewicht": generate_körpergewicht_mapping,
    "Körpergröße": generate_körpergröße_mapping,
    "Patient auf ICU": generate_patientauficu_mapping,
    "Pulsoxymetrie": generate_pulsoxymetrie_mapping,
    "Raucherstatus": generate_raucherstatus_mapping,
    "Reisehistorie": generate_reisehistorie_mapping,
    "SARS-CoV-2 Exposition": generate_sars_cov_2exposition_mapping,
    "Schwangerschaftsstatus": generate_schwangerschaftsstatus_mapping,
    "SOFA": generate_sofa_mapping,
    "Symptom": generate_symptom_mapping
}

if __name__ == "__main__":
    map_entries = generate_aql_mapping()
    map_entries_file = open("mapping/" + "gecco-aql-mapping.json", 'w')
    map_entries_file.write(map_entries.to_json())
