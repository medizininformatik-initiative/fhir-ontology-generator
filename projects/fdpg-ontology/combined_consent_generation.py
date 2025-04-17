import csv
import json
from pathlib import Path

from cohort_selection_ontology.model.ui_data import TermCode
from cohort_selection_ontology.model.mapping import (FhirMapping, FixedFHIRCriteria, CQLTimeRestrictionParameter,
                                                     SimpleCardinality, CQLMapping, FixedCQLCriteria)
from cohort_selection_ontology.model.tree_map import TreeMap, TermEntryNode
import argparse
import os

from common.util.codec.json import JSONFhirOntoEncoder
from common.util.log.functions import get_logger
from common.util.project import Project

logger = get_logger(__file__)


def configure_args_parser():
    arg_parser = argparse.ArgumentParser(description='Generate the consent for the MII-FDPG')

    arg_parser.add_argument('--merge_mappings', action='store_true')
    arg_parser.add_argument(
         '--project',
        required=True,
        help="Project to generate for"
    )

    return arg_parser


def bool_value(value: str) -> bool:
    return value.lower() == "yes"


def generate_key(distributed_analysis, eu_gdpr, insurance_data, contact) -> str:
    return ":".join([distributed_analysis, eu_gdpr, insurance_data, contact])


def convert_bool_analysis_to_code(distributed_analysis, eu_gdpr, insurance_data, contact) -> str:
    return "-".join([distributed_analysis, eu_gdpr, insurance_data, contact])


def generate_fixed_fhir_criteria(provisions_code, provisions_display) -> list[FixedFHIRCriteria]:
    return [FixedFHIRCriteria("coding", "mii-provision-provision-code",
            [{"code": code, "display": display, "system": "urn:oid:2.16.840.1.113883.3.1937.777.24.5.3"}])
            for code, display in zip(provisions_code, provisions_display)]


def generate_fixed_cql_criteria(provisions_code, provisions_display) -> list[FixedCQLCriteria]:
    return [FixedCQLCriteria({"CodeableConcept"}, "provision.provision.code", SimpleCardinality.MANY,
            [{"code": code, "display": display, "system": "urn:oid:2.16.840.1.113883.3.1937.777.24.5.3"}])
            for code, display in zip(provisions_code, provisions_display)]


def process_csv(csv_file: str | Path):
    lookup_table = {}
    consents_fhir = []
    consents_cql = []

    context = TermCode("fdpg.mii.cds", "Einwilligung", "Einwilligung", "1.0.0")
    consent_mapping_tree = TreeMap({}, context, "fdpg.consent.combined", "1.0.0")

    with open(csv_file, mode='r', newline='', encoding='utf-8') as file:
        reader = csv.DictReader(file, delimiter=";")

        for row in reader:
            consent_code = convert_bool_analysis_to_code(
                row['distributed-analysis'], row['eu-gdpr'], row['insurance-data'], row['contact']
            )

            fhir_mapping = FhirMapping(name=row['analysis'])
            cql_mapping = CQLMapping(name=row['analysis'])

            term_code = TermCode(system="fdpg.consent.combined", code=consent_code, display=row['analysis'])

            fhir_mapping.key = term_code
            fhir_mapping.context = context
            fhir_mapping.fhirResourceType = "Consent"
            fhir_mapping.timeRestrictionParameter = "date"
            cql_mapping.key = term_code
            cql_mapping.context = context
            cql_mapping.timeRestriction = CQLTimeRestrictionParameter("datetime", {"dateTime"})
            cql_mapping.resourceType = "Consent"
            cql_mapping.primaryCode= {
                            "code": "57016-8",
                            "display": "Privacy policy acknowledgment Document",
                            "system": "http://loinc.org"
                        }

            provisions_code = [code.strip() for code in row['provisions-code'].split('|')]
            provisions_display = [display.strip() for display in row['provisions-display'].split('|')]

            fhir_mapping.fixedCriteria = generate_fixed_fhir_criteria(provisions_code, provisions_display)
            cql_mapping.fixedCriteria = generate_fixed_cql_criteria(provisions_code, provisions_display)

            consents_fhir.append(fhir_mapping)
            consents_cql.append(cql_mapping)

            key = generate_key(
                row['distributed-analysis'],
                row['eu-gdpr'],
                row['insurance-data'],
                row['contact']
            )
            lookup_table[key] = fhir_mapping.key
            consent_mapping_tree.entries[consent_code] = TermEntryNode(term_code)

    return consents_fhir, consents_cql, consent_mapping_tree, lookup_table


def save_json(file: str | Path, data):
    os.makedirs(os.path.dirname(file), exist_ok=True)
    with open(file, mode="w+", encoding='UTF-8') as f:
        json.dump(data, f, cls=JSONFhirOntoEncoder)


def append_to_json(output_file: str | Path, input_file: str | Path, data):
    with open(input_file, mode="r", encoding='UTF-8') as f:
        existing_data = json.load(f)
        existing_data.extend(data)
    save_json(output_file, existing_data)


def generate_js_lookup_table(lookup_table: dict) -> str:
    js_lookup_table = "const lookupTable = {\n"
    js_lookup_table += "".join(f'  "{key.lower()}": {json.dumps(value.to_dict())},\n' for key, value in lookup_table.items())
    js_lookup_table += "};"
    return js_lookup_table


if __name__ == "__main__":
    args = configure_args_parser().parse_args()

    project = Project(name=args.project)

    logger.info(f"Running combined consent generation for project '{project.name}'")

    consent_input_dir = project.input("consent")
    consent_output_dir = project.output("consent")
    output_dir = project.output("merged_ontology", "mapping")

    input_file = consent_input_dir / "csv-consent.csv"
    logger.info(f"Processing input data @ {input_file}")
    consents_fhir, consents_cql, consent_mapping_tree, lookup_table = process_csv(input_file)

    logger.info("Storing generated consent mappings")
    save_json(consent_output_dir / "consent-mappings_fhir.json", consents_fhir)
    save_json(consent_output_dir / "consent-mappings_cql.json", consents_cql)
    save_json(consent_output_dir / "consent-mappings-tree.json", consent_mapping_tree.to_dict())

    logger.info("Generating lookup table")
    with open(consent_output_dir / "consent-js-lookup-table.js", mode="w+", encoding='UTF-8') as f:
        f.write(generate_js_lookup_table(lookup_table))

    if args.merge_mappings:
        logger.info("Merging consent mappings")
        append_to_json(output_dir / "cql" / "mapping_cql.json", output_dir / "cql" / "mapping_cql.json",
                       consents_cql)
        append_to_json(output_dir / "fhir" / "mapping_fhir.json", output_dir / "fhir" / "mapping_fhir.json",
                       consents_fhir)
        append_to_json(output_dir / "mapping_tree.json", output_dir / "mapping_tree.json",
                       [consent_mapping_tree.to_dict()])
