import bisect
import requests
import locale
import os
from UiDataModel import TermCode, TerminologyEntry

ONTOSERVER = os.environ.get('ONTOLOGY_SERVER_ADDRESS')
locale.setlocale(locale.LC_ALL, 'de_DE')


def expand_value_set(url):
    term_codes = set()
    response = requests.get(ONTOSERVER + f"ValueSet/$expand?url={url}")
    if response.status_code == 200:
        value_set_data = response.json()
        global_version = None
        for parameter in value_set_data["expansion"]["parameter"]:
            if parameter["name"] == "version":
                global_version = parameter["valueUri"].split("|")[-1]
        if "contains" not in value_set_data["expansion"]:
            print(f"{url} is empty")
            return term_codes
        for contains in value_set_data["expansion"]["contains"]:
            system = contains["system"]
            code = contains["code"]
            display = contains["display"]
            if "version" in contains:
                version = contains["version"]
            else:
                version = global_version
            term_code = TermCode(system, code, display, version)
            term_codes.add(term_code)
    return term_codes


def create_vs_tree(canonical_url):
    create_concept_map()
    vs = expand_value_set(canonical_url)
    vs_dict = {term_code.code: TerminologyEntry([term_code], leaf=True, selectable=True) for term_code in vs}
    closure_map_data = get_closure_map(vs)
    if "group" in closure_map_data:
        for group in closure_map_data["group"]:
            subsumption_map = group["element"]
            subsumption_map = {item['code']: [target['code'] for target in item['target']] for item in subsumption_map}
            # remove non direct parents
            for code, parents in subsumption_map.items():
                if len(parents) == 0:
                    continue
                else:
                    direct_parents(parents, subsumption_map)
            for node, parents, in subsumption_map.items():
                for parent in parents:
                    bisect.insort(vs_dict[parent].children, vs_dict[node])
                    vs_dict[node].root = False
                    vs_dict[parent].leaf = False
    return sorted([term_code for term_code in vs_dict.values() if term_code.root])


def create_concept_map():
    body = {
        "resourceType": "Parameters",
        "parameter": [{
            "name": "name",
            "valueString": "closure-test"
        }]
    }
    headers = {"Content-type": "application/fhir+json"}
    requests.post(ONTOSERVER + "$closure", json=body, headers=headers)


def get_closure_map(term_codes):
    closure_response = None
    body = {"resourceType": "Parameters",
            "parameter": [{"name": "name", "valueString": "closure-test"}]}
    for term_code in term_codes:
        body["parameter"].append({"name": "concept",
                                  "valueCoding": {
                                      "system": f"{term_code.system}",
                                      "code": f"{term_code.code}",
                                      "display": f"{term_code.display}",
                                      "version": f"{term_code.version}"
                                  }})
    headers = {"Content-type": "application/fhir+json"}
    response = requests.post(ONTOSERVER + "$closure", json=body, headers=headers)
    if response.status_code == 200:
        closure_response = response.json()
    else:
        raise Exception(response.content)
    return closure_response


def direct_parents(parents, input_map):
    parents_copy = parents.copy()
    for parent in parents_copy:
        if parent in input_map:
            parent_parents = input_map[parent]
            for elem in parents_copy:
                if elem in parent_parents and elem in parents:
                    parents.remove(elem)


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
