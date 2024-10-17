import bisect
import json
import logging
import os.path
from typing import List
import locale

from model.TreeMap import TermEntryNode, TreeMap
from sortedcontainers import SortedSet

from TerminologService.TermServerConstants import TERMINOLOGY_SERVER_ADDRESS, SERVER_CERTIFICATE, PRIVATE_KEY, REQUESTS_SESSION
from model.UiDataModel import TermCode
from util.LoggingUtil import init_logger

locale.setlocale(locale.LC_ALL, 'de_DE')

logger = init_logger("valueSetToRoots", logging.DEBUG)


def get_value_set_expansion(url: str, onto_server: str = TERMINOLOGY_SERVER_ADDRESS):
    """
    Retrieves the value set expansion from the terminology server.
    :param url: canonical url of the value set
    :param onto_server: address of the terminology server
    :return: json data of the value set expansion
    """
    if '|' in url:
        url = url.replace('|', '&version=')
    response = REQUESTS_SESSION.get(f"{onto_server}ValueSet/$expand?url={url}", cert=(SERVER_CERTIFICATE, PRIVATE_KEY))
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(response.status_code, response.content, url)


def expand_value_set(url: str, onto_server: str = TERMINOLOGY_SERVER_ADDRESS):
    """
    Expands a value set and returns a set of term codes contained in the value set.
    :param url: canonical url of the value set
    :param onto_server: address of the terminology server
    :return: sorted set of the term codes contained in the value set
    """
    term_codes = SortedSet()
    value_set_data = get_value_set_expansion(url, onto_server)
    if "expansion" in value_set_data:
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
        print(f"Error expanding {url}")
        return []
        # raise Exception(response.status_code, response.content)
    return term_codes


def create_vs_tree_map(canonical_url: str) -> TreeMap:
    """
    Creates a tree of the value set hierarchy utilizing the closure operation.
    :param canonical_url:
    :return: TreeMap of the value set hierarchy
    """
    create_concept_map()
    vs = expand_value_set(canonical_url)
    treemap: TreeMap = TreeMap({}, None, None, None)
    treemap.entries = {term_code.code: TermEntryNode(term_code) for term_code in vs}
    treemap.system = vs[0].system
    treemap.version = vs[0].version
    try:
        closure_map_data = get_closure_map(vs)
        if groups := closure_map_data.get("group"):
            if len(groups) > 1:
                raise Exception("Multiple groups in closure map. Currently not supported.")
            for group in groups:
                treemap.system = group["source"]
                treemap.version = group["sourceVersion"]
                subsumption_map = group["element"]
                subsumption_map = {item['code']: [target['code'] for target in item['target']] for item in subsumption_map}
                for code, parents in subsumption_map.items():
                    remove_non_direct_ancestors(parents, subsumption_map)
                for node, parents, in subsumption_map.items():
                    treemap.entries[node].parents += parents
                    for parent in parents:
                        treemap.entries[parent].children.append(node)
    except Exception as e:
        print(e)
        
    return treemap


def create_concept_map(name: str = "closure-test"):
    """
    Creates an empty concept map for closure operation on the ontology server.
    :param name: identifier of the concept map for closure invocation
    """
    body = {
        "resourceType": "Parameters",
        "parameter": [{
            "name": "name",
            "valueString": name
        }]
    }
    headers = {"Content-type": "application/fhir+json"}
    REQUESTS_SESSION.post(TERMINOLOGY_SERVER_ADDRESS + "$closure", json=body, headers=headers,
                  cert=(SERVER_CERTIFICATE, PRIVATE_KEY))


def get_closure_map(term_codes, closure_name: str = "closure-test"):
    """
    Returns the closure map of a set of term codes.
    :param term_codes: set of term codes with potential hierarchical relations among them
    :param closure_name: identifier of the closure table to invoke closure operation on
    :return: closure map of the term codes
    """
    body = {"resourceType": "Parameters",
            "parameter": [{"name": "name", "valueString": closure_name}]}
    for term_code in term_codes:
        # FIXME: Workaround for gecco. ValueSets with multiple versions are not supported in closure.
        #  Maybe split by version? Or change Profile to reference ValueSet with single version?
        if term_code.system == "http://fhir.de/CodeSystem/bfarm/atc" and term_code.version != "2022":
            continue

        value_coding = {
            "system": f"{term_code.system}",
            "code": f"{term_code.code}",
            "display": f"{term_code.display}"
        }
        if term_code.version:
            value_coding['version'] = term_code.version
        body["parameter"].append({"name": "concept",
                                  "valueCoding": value_coding})
    headers = {"Content-type": "application/fhir+json"}
    response = REQUESTS_SESSION.post(TERMINOLOGY_SERVER_ADDRESS + "$closure", json=body, headers=headers,
                             cert=(SERVER_CERTIFICATE, PRIVATE_KEY))
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
