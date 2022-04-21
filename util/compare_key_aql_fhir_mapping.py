import json

from model.UiDataModel import TermCode

if __name__ == "__main__":
    fhir = open("mapping/codex-term-code-mapping.json", 'r')
    aql = open("mapping/gecco-aql-mapping.json", 'r')

    fhir_mapping = json.load(fhir)
    aql_mapping = json.load(aql)

    fhir_term_codes = [TermCode(key["key"]["system"], key["key"]["code"], key["key"]["display"]) for key in
                       fhir_mapping]
    aql_term_codes = [TermCode(key["key"]["system"], key["key"]["code"], key["key"]["display"]) for key in aql_mapping]
    print(len(fhir_term_codes))
    remaining = (set(fhir_term_codes).difference(set(aql_term_codes)))
    without_icd_10 = {term_code for term_code in remaining if term_code.system !=
                      "http://fhir.de/CodeSystem/bfarm/icd-10-gm"}
    print(without_icd_10)
    print({term_code for term_code in remaining if term_code.system ==
           "http://snomed.info/sct"})
