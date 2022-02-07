import os
import re

from lxml import etree

from TerminologService.ValueSetResolver import get_value_set_definition
from model.OpenEHRTemplate import OpenEHRTemplate

COLOGNE_ONTO_SERVER = "https://ontoserver.imi.uni-luebeck.de/koeln/fhir/"


def get_key_value_from_annotation(annotation):
    key_value_pairs = {}
    for items in annotation:
        for item in items:
            key = None
            value = None
            for k_or_v in item:
                if k_or_v.tag == "{openEHR/v1/Template}key":
                    key = k_or_v.text
                elif k_or_v.tag == "{openEHR/v1/Template}value":
                    value = k_or_v.text
                else:
                    raise Exception(f"Unknown tag for {k_or_v}")
                if key and value:
                    key_value_pairs[key] = value
    return key_value_pairs


def get_value_sets_from_combined_definition(canonical_url):
    result = []
    value_set_definition = get_value_set_definition(canonical_url, COLOGNE_ONTO_SERVER)
    if not value_set_definition:
        print(canonical_url)
        return [canonical_url]
    if compose := value_set_definition.get("compose"):
        for include in compose.get("include", []):
            result += include.get("valueSet", [])
    if result:
        return result
    else:
        return [canonical_url]


def get_separate_value_sets(value_sets):
    result = []
    for value_set in value_sets:
        if value_set.endswith("combined"):
            get_value_set_definition(value_set)
            result += get_value_sets_from_combined_definition(value_set)
        else:
            result.append(value_set)
    return result


def extract_vs_canonical_url(expand_string):
    url = re.search("(http|https)\:\/\/[a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,3}(\/\S*)?", expand_string)
    if url:
        return url.group(0)
    else:
        print(f"no_url_found in {expand_string}")


def get_value_sets_from_definition(definition):
    value_sets = []
    for content in definition:
        for rule in content:
            for constraint in rule:
                for term_query_id in constraint:
                    if term_query_id.tag == "{openEHR/v1/Template}termQueryId":
                        if vs_canonical_url := extract_vs_canonical_url(term_query_id.get("queryName")):
                            separated_value_sets = get_value_sets_from_combined_definition(vs_canonical_url)
                            value_sets += separated_value_sets
    return value_sets


def remove_mapping_information(key_value_annotations):
    mapping_info = {key: value for key, value in key_value_annotations.items() if "mapping" in key}
    remaining = {k: v for k, v in key_value_annotations.items() if k not in mapping_info}
    return remaining


def generate_openehr_profiles():
    result = []
    for filename in os.listdir("resources\\openehr\\templates"):
        open_ehr_template = OpenEHRTemplate(filename.split(".")[0])
        template = etree.parse(f"resources\\openehr\\templates\\{filename}")
        for annotation in template.xpath("/xmlns:template/xmlns:annotations",
                                         namespaces={"xmlns": "openEHR/v1/Template"}):
            k_v_pairs = get_key_value_from_annotation(annotation)
            k_v_pairs = remove_mapping_information(k_v_pairs)
            open_ehr_template.annotations.update(k_v_pairs)
        for definition in template.xpath("/xmlns:template/xmlns:definition",
                                         namespaces={"xmlns": "openEHR/v1/Template"}):
            open_ehr_template.valueSets = get_value_sets_from_definition(definition)
        result.append(open_ehr_template)
    return result


def get_archetype(element):
    data_path = element.get("path")
    element = element.getParent()
    template_type = element.get("{http://www.w3.org/2001/XMLSchema-instance}type").split(":")[-1]
    archetype_id = element.get("archetype_id")
    element = element.getParent()


if __name__ == "__main__":
    generate_openehr_profiles()
