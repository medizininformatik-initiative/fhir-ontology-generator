# TODO:
- Ensure all valueSet that are bound to are available on the TermServer of choice.
- Evaluate if all attributes are defined in the QueryMetaData.
- Add Person Module from MII Core. The profile of TodesUrsache is very lackluster in the dktk profile. Use the MII one instead.
- IF TNM-cpu Prefix is needed for the Query, add SearchParameters and add them as attributes to the QueryMetaData.
- The ResidualStatus Profile references by the MedicationStatement is not available in the dktk profile. If it is needed, get in contact with the dktk team and ask them to add it.


````json
{
    "name": "Strahlentherapie",
    "resource_type": "Procedure",
    "context": {
        "system": "bzkf.dktk.oncology",
        "code": "Strahlentherapie",
        "display": "Strahlentherapie"
    },
    "term_code_defining_id": "Procedure.category",
    "attribute_defining_id_type_map": {
        "(Procedure.extension:Intention).value[x]": "",
        "(Procedure.extension:StellungZurOp).value[x]": "",
        "(Procedure.reasonReference).code.coding:icd10-gm": "reference"
    },
    "time_restriction_defining_id": "Procedure.performed[x]"
}
````

Currently, there are uses a reference to the Primärdiagnose as we do not support "double references" this needs to be 
adjusted, to resolve to some yet to be defined Condtion Profile that has the element: Condition.coding:icd-10-gm-cancer 
that binds to the minimum valueSet of icd-10-gm codes that are relevant for the use case. Ensure to add the Profile 
differential, generate its snapshot and also add it to profile_to_query_meta_data_resolver_mapping.json as key without 
value. After creating the needed profile update the QueryMetaData accordingly:
````json
{
    "name": "Strahlentherapie",
    "resource_type": "Procedure",
    "context": {
        "system": "bzkf.dktk.oncology",
        "code": "Strahlentherapie",
        "display": "Strahlentherapie"
    },
    "term_code_defining_id": "Procedure.category",
    "attribute_defining_id_type_map": {
        "(Procedure.extension:Intention).value[x]": "",
        "(Procedure.extension:StellungZurOp).value[x]": "",
        "(Procedure.reasonReference).code.coding:icd10-gm-cancer": ""
    },
    "time_restriction_defining_id": "Procedure.performed[x]"
}
````

- Set up a FHIR Server with the SearchParameters (probably want to bundle them).
- Create and add test data to said FHIR Server
- Ensure the created Ontology fits your needs and works as intended.
- If you need help ask!