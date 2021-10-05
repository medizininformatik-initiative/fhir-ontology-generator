import json
import sys
import requests
import locale
import networkx as nx
from UiDataModel import TermCode, TerminologyEntry

ONTOSERVER = "https://ontoserver.imi.uni-luebeck.de/fhir/"
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


def direct_parents(parents, input_map):
    parents_copy = parents.copy()
    for parent in parents_copy:
        if parent in input_map:
            parent_parents = input_map[parent]
            for elem in parents_copy:
                if elem in parent_parents and elem in parents:
                    parents.remove(elem)


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
                    vs_dict[parent].children.append(vs_dict[node])
                    vs_dict[node].root = False
                    vs_dict[parent].leaf = False
    return [term_code for term_code in vs_dict.values() if term_code.root]


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


def create_dag(input_map: dict):
    for code, parents in input_map.items():
        if len(parents) == 0:
            continue
        else:
            direct_parents(parents, input_map)
    dag = nx.DiGraph(directed=True)
    for node, parents in input_map.items():
        for parent in parents:
            dag.add_edge(parent, node)
    return dag


def get_roots(dag):
    roots = []
    for component in nx.weakly_connected_components(dag):
        sub_graph = dag.subgraph(component)
        roots.extend([n for n, d in sub_graph.in_degree() if d == 0])
    return roots


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


def expand_root_based_vs(roots):
    result = roots.copy()
    body = {"resourceType": "ValueSet",
            "compose": {
                "include": [
                    {
                        "system": f"{term_code.system}",
                        "version": f"{term_code.version}",
                        "filter": [
                            {
                                "property": "concept",
                                "op": "descendent-of",
                                "value": f"{term_code.code}",
                            }
                        ]
                    } for term_code in roots]
            }
            }
    headers = {"Content-type": "application/fhir+json"}
    response = requests.post(ONTOSERVER + "ValueSet/$expand", json=body, headers=headers)
    result.update(value_set_json_to_term_code_set(response))
    return result


def look_up_display(code_system, version, code):
    response = requests.get(ONTOSERVER + f"CodeSystem/$lookup?system={code_system}&version={version}&code={code}")
    if response.status_code == 200:
        look_up_response = response.json()
        for parameter in look_up_response.get("parameter"):
            if name := parameter.get("name"):
                if name == "designation":
                    next_is_display = False
                    for part in parameter.get("part"):
                        if next_is_display:
                            if "valueString" in part:
                                return part["valueString"]

                            else:
                                raise Exception("valueString not found")
                        if "valueCoding" in part:
                            if code := part["valueCoding"].get("code"):
                                if code == "display":
                                    next_is_display = True


def get_root_and_node_concepts(canonical_address_value_set):
    roots_and_node_entries = []
    # FIXME this is a performance workaround, if a ValueSet is defined by is-a relationships only use them as roots
    #  directly.
    if canonical_address_value_set == "https://www.medizininformatik-initiative.de/fhir/core/modul-diagnose/ValueSet" \
                                      "/diagnoses-sct":
        roots_and_node_entries = [
            TerminologyEntry([TermCode("http://snomed.info/sct", "404684003", "Clinical finding")], "Concept", False,
                             True),
            TerminologyEntry([TermCode("http://snomed.info/sct", "272379006", "Events")], "Concept", False, True),
            TerminologyEntry([TermCode("http://snomed.info/sct", "243796009", "Situation with explicit context")],
                             "Concept", False, True)]
        return roots_and_node_entries
    create_concept_map()
    original_vs = expand_value_set(canonical_address_value_set)
    json_data = get_closure_map(original_vs)
    if json_data and "group" in json_data:
        for group in json_data["group"]:
            subsumes_map = group["element"]
            subsumes_map = {item['code']: [target['code'] for target in item['target']] for item in subsumes_map}
            dag = create_dag(subsumes_map)
            code_system = group["source"]
            system_version = group["sourceVersion"]
            root_elements = set(
                [TermCode(code_system, root, look_up_display(code_system, system_version, root), system_version) for
                 root in
                 get_roots(dag)])
            rooted_vs = expand_root_based_vs(root_elements)
            nodes = original_vs.difference(rooted_vs)
            roots_and_node_entries += [TerminologyEntry([root], "Concept", leaf=False, selectable=True)
                                       for root in root_elements]
            roots_and_node_entries += [TerminologyEntry([node], "Concept", leaf=True, selectable=True)
                                       for node in nodes]
    # else:
    #     roots_and_node_entries = original_vs
    # local is needed to ensure german umlauts are sorted as expected and not listed at the end.
    return sorted(roots_and_node_entries, key=lambda x: locale.strxfrm(x.display))


if __name__ == "__main__":
    print(get_root_and_node_concepts(
        "https://www.netzwerk-universitaetsmedizin.de/fhir/ValueSet/chronic-lung-diseases-icd-with-parent"))
