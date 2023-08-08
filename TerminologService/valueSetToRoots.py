import bisect
from typing import List

import requests
import locale

from sortedcontainers import SortedSet

from TerminologService.TermServerConstants import TERMINOLOGY_SERVER_ADDRESS
from model.UiDataModel import TermCode, TermEntry

locale.setlocale(locale.LC_ALL, 'de_DE')


def expand_value_set(url: str, onto_server: str = TERMINOLOGY_SERVER_ADDRESS):
    """
    Expands a value set and returns a set of term codes contained in the value set.
    :param url: canonical url of the value set
    :return: sorted set of the term codes contained in the value set
    """
    if '|' in url:
        url = url.replace('|', '&version=')
    term_codes = SortedSet()
    response = requests.get(onto_server + f"ValueSet/$expand?url={url}")
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
            if display.isupper():
                display = display.title()
            if "version" in contains:
                version = contains["version"]
            else:
                version = global_version
            term_code = TermCode(system, code, display, version)
            term_codes.add(term_code)
    else:
        return []
        print(f"Error expanding {url}")
        # raise Exception(response.status_code, response.content)
    return term_codes


def create_vs_tree(canonical_url: str):
    """
    Creates a tree of the value set hierarchy utilizing the closure operation.
    :param canonical_url:
    :return: Sorted term_entry roots of the value set hierarchy
    """
    create_concept_map()
    vs = expand_value_set(canonical_url)
    vs_dict = {term_code.code: TermEntry([term_code], leaf=True, selectable=True) for term_code in vs}
    closure_map_data = get_closure_map(vs)
    if groups := closure_map_data.get("group"):
        for group in groups:
            subsumption_map = group["element"]
            subsumption_map = {item['code']: [target['code'] for target in item['target']] for item in subsumption_map}
            for code, parents in subsumption_map.items():
                remove_non_direct_ancestors(parents, subsumption_map)
            for node, parents, in subsumption_map.items():
                for parent in parents:
                    bisect.insort(vs_dict[parent].children, vs_dict[node])
                    vs_dict[node].root = False
                    vs_dict[parent].leaf = False
    return sorted([term_entry for term_entry in vs_dict.values() if term_entry.root])


def create_concept_map():
    """
    Creates an empty concept map for closure operation on the ontology server.
    """
    body = {
        "resourceType": "Parameters",
        "parameter": [{
            "name": "name",
            "valueString": "closure-test"
        }]
    }
    headers = {"Content-type": "application/fhir+json"}
    requests.post(TERMINOLOGY_SERVER_ADDRESS + "$closure", json=body, headers=headers)


def get_closure_map(term_codes):
    """
    Returns the closure map of a set of term codes.
    :param term_codes: set of term codes with potential hierarchical relations among them
    :return: closure map of the term codes
    """
    body = {"resourceType": "Parameters",
            "parameter": [{"name": "name", "valueString": "closure-test"}]}
    for term_code in term_codes:
        # FIXME: Workaround for gecco. ValueSets with multiple versions are not supported in closure.
        #  Maybe split by version? Or change Profile to reference ValueSet with single version?
        if term_code.system == "http://fhir.de/CodeSystem/bfarm/atc" and term_code.version != "2022":
            continue

        body["parameter"].append({"name": "concept",
                                  "valueCoding": {
                                      "system": f"{term_code.system}",
                                      "code": f"{term_code.code}",
                                      "display": f"{term_code.display}",
                                      "version": f"{term_code.version}"
                                  }})
    headers = {"Content-type": "application/fhir+json"}
    response = requests.post(TERMINOLOGY_SERVER_ADDRESS + "$closure", json=body, headers=headers)
    if response.status_code == 200:
        closure_response = response.json()
    else:
        raise Exception(response.content)
    return closure_response


def remove_non_direct_ancestors(parents: List[str], input_map: dict):
    """
    Removes all ancestors of a node that are not direct ancestors.
    :param parents: list of parents of a concept
    :param input_map: closure map of the value set
    """
    if len(parents) < 2:
        return
    parents_copy = parents.copy()
    for parent in parents_copy:
        if parent in input_map:
            parent_parents = input_map[parent]
            for elem in parents_copy:
                if elem in parent_parents and elem in parents:
                    parents.remove(elem)


def value_set_json_to_term_code_set(response):
    """
    Converts a json response from the ontology server to a set of term codes.
    :param response: json response from the ontology server
    :return: Sorted set of term codes
    """
    term_codes = SortedSet()
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
