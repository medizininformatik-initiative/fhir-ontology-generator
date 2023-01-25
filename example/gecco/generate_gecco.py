from __future__ import annotations

import argparse
import json
import os
import uuid
from typing import List, ValuesView, Dict

from FHIRProfileConfiguration import *
from api.CQLMappingGenerator import CQLMappingGenerator
from api.FHIRSearchMappingGenerator import FHIRSearchMappingGenerator
from api.ResourceQueryingMetaDataResolver import ResourceQueryingMetaDataResolver
from api.UIProfileGenerator import UIProfileGenerator
from api.UITreeGenerator import UITreeGenerator
from helper import download_simplifier_packages, generate_snapshots, write_object_as_json, generate_result_folder, \
    to_upper_camel_case
from model.MappingDataModel import CQLMapping, FhirMapping
from model.ResourceQueryingMetaData import ResourceQueryingMetaData
from model.UIProfileModel import UIProfile
from model.UiDataModel import TermEntry, TermCode, CategoryEntry

core_data_sets = [GECCO, MII_LAB]
WINDOWS_RESERVED_CHARACTERS = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']


class GeccoDataSetQueryingMetaDataResolver(ResourceQueryingMetaDataResolver):
    def __init__(self):
        super().__init__()

    def get_query_meta_data(self, fhir_profile_snapshot: dict, _context: TermCode) -> List[ResourceQueryingMetaData]:
        """
        Implementation as simple look up table.
        :param fhir_profile_snapshot:
        :param _context:
        :return: List of ResourceQueryingMetaData
        """
        result = []
        key = fhir_profile_snapshot.get("name")
        mapping = self._get_query_meta_data_mapping()
        for value in mapping[key]:
            with open(f"resources/QueryingMetaData/{value}QueryingMetaData.json", "r") as file:
                result.append(ResourceQueryingMetaData.from_json(file))
        return result

    @staticmethod
    def _get_query_meta_data_mapping():
        with open("resources/profile_to_query_meta_data_resolver_mapping.json", "r") as f:
            return json.load(f)


def generate_term_code_mapping(_entries: List[TermEntry]):
    """
    Generates the term code mapping for the given entries and saves it in the mapping folder
    :param _entries: TermEntries to generate the mapping for
    """
    pass


def generate_term_code_tree(_entries: List[TermEntry]):
    """
    Generates the term code tree for the given entries and saves it in the mapping folder
    :param _entries:
    :return:
    """
    pass


def validate_ui_profile(_profile_name: str):
    """
    Validates the ui profile with the given name against the ui profile schema
    :param _profile_name: name of the ui profile
    :raises: jsonschema.exceptions.ValidationError if the ui profile is not valid
             jsonschema.exceptions.SchemaError if the ui profile schema is not valid
    """
    pass
    # f = open("ui-profiles/" + profile_name + ".json", 'r')
    # validate(instance=json.load(f), schema=json.load(open("resources/schema/ui-profile-schema.json")))


def write_ui_trees_to_files(trees: List[TermEntry], result_folder: str = "ui_trees"):
    """
    Writes the ui trees to the ui-profiles folder
    :param trees: ui trees to write
    :param result_folder: folder to write the ui trees to
    """
    for tree in trees:
        write_object_as_json(tree, f"{result_folder}/{remove_reserved_characters(tree.display)}.json")


# Todo: this should be an abstract method that has to be implemented for each use-case
# Todo: move this concrete implementation elsewhere


def write_ui_profile(module_category_entry):
    """
    Writes the ui profile for the given module category entry to the ui-profiles folder
    :param module_category_entry: name of the module category entry
    """
    f = open("ui-profiles/" + module_category_entry.display + ".json", 'w', encoding="utf-8")
    if len(module_category_entry.children) == 1:
        f.write(module_category_entry.children[0].to_json())
    else:
        f.write(module_category_entry.to_json())
    f.close()


def move_back_other(entries):
    """
    Entries are sorted alphabetically. This method moves the entries that express "Other" to the end of the list
    :param entries: list of entries
    """
    entries_copy = entries.copy()
    for entry in entries_copy:
        for other_naming in ["Sonstige", "sonstige", "andere", "Andere", "Weitere", "Other"]:
            if entry.termCode.display.startswith(other_naming):
                entries.remove(entry)
                entries.append(entry)
        if entry.children:
            move_back_other(entry.children)


def configure_args_parser():
    """
    Configures the argument parser
    :return: the configured argument parser
    """
    arg_parser = argparse.ArgumentParser(description='Generate the UI-Profile of the core data set for the MII-FDPG')
    arg_parser.add_argument('--download_packages', action='store_true')
    arg_parser.add_argument('--generate_snapshot', action='store_true')
    arg_parser.add_argument('--generate_csv', action='store_true')
    arg_parser.add_argument('--generate_ui_trees', action='store_true')
    arg_parser.add_argument('--generate_ui_profiles', action='store_true')
    arg_parser.add_argument('--generate_mapping', action='store_true')
    arg_parser.add_argument('--generate_old_format', action='store_true')
    return arg_parser


def remove_reserved_characters(file_name):
    return file_name.translate({ord(c): None for c in WINDOWS_RESERVED_CHARACTERS})


def write_ui_profiles_to_files(profiles: List[UIProfile] | ValuesView[UIProfile]):
    for profile in profiles:
        with open(
                "ui-profiles/" + remove_reserved_characters(profile.name).replace(" ", "_").replace(".", "_") + ".json",
                'w', encoding="utf-8") as f:
            f.write(profile.to_json())
    f.close()


def write_mappings_to_files(mappings):
    for mapping in mappings:
        if isinstance(mapping, CQLMapping):
            mapping_dir = "mapping/cql/"
        elif isinstance(mapping, FhirMapping):
            mapping_dir = "mapping/fhir/"
        else:
            raise ValueError("Mapping type not supported" + str(type(mapping)))
        with open(mapping_dir + mapping.name + ".json", 'w', encoding="utf-8") as f:
            f.write(mapping.to_json())
    f.close()


def get_gecco_categories():
    # categories are BackboneElements within the LogicalModel
    with open(f"resources/de.gecco#1.0.5/package/StructureDefinition-LogicalModel-GECCO.json",
              encoding="utf-8") as json_file:
        categories = []
        data = json.load(json_file)
        for element in data["differential"]["element"]:
            try:
                # ignore Gecco base element:
                if element["base"]["path"] == "forschungsdatensatz_gecco.gecco":
                    continue
                if element["type"][0]["code"] == "BackboneElement":
                    categories += get_categories(element)
            except KeyError:
                pass
        return categories


def get_categories(element):
    result = []
    for extension in element["_short"]["extension"]:
        for nested_extension in extension["extension"]:
            if "valueMarkdown" in nested_extension:
                result.append(
                    CategoryEntry(str(uuid.uuid4()), nested_extension["valueMarkdown"], element["base"]["path"]))
    return result


def create_category_terminology_entry(category_entry):
    term_code = [TermCode("mii.abide", category_entry.display, category_entry.display)]
    result = TermEntry(term_code, "Category", leaf=False, selectable=False)
    result.path = category_entry.path
    return result


def create_terminology_definition_for(categories):
    category_terminology_entries = []
    for category_entry in categories:
        category_terminology_entries.append(create_category_terminology_entry(category_entry))
    with open(f"resources/de.gecco#1.0.5/package/StructureDefinition-LogicalModel-GECCO.json", encoding="utf-8") \
            as json_file:
        data = json.load(json_file)
        for element in data["differential"]["element"]:
            if "type" in element:
                if element["type"][0]["code"] == "BackboneElement":
                    continue
                elif element["type"][0]["code"] in ["CodeableConcept", "Quantity", "date"]:
                    add_terminology_entry_to_category(element, category_terminology_entries, element["type"][0]["code"])
                else:
                    raise Exception(f"Unknown element {element['type'][0]['code']}")
    for category_entry in category_terminology_entries:
        category_entry.children = sorted(category_entry.children)
    return category_terminology_entries


def add_terminology_entry_to_category(element, categories, terminology_type):
    for category_entry in categories:
        # same path -> sub element of that category
        if category_entry.path in element["base"]["path"]:
            terminology_entry = TermEntry(get_term_codes(element), terminology_type)
            # We use the english display to resolve after we switch to german.
            terminology_entry.display = element["short"]
            if terminology_entry.display in IGNORE_LIST:
                continue
            resolve_terminology_entry_profile(terminology_entry, element)
            terminology_entry.display = get_german_display(element) if get_german_display(element) else element["short"]
            if terminology_entry.display == category_entry.display:
                # Resolves issue like : -- Symptoms                 --Symptoms
                #                           -- Symptoms     --->      -- Coughing
                #                              -- Coughing
                category_entry.children += terminology_entry.children
            else:
                category_entry.children.append(terminology_entry)
            break


def load_logical_to_profile_mapping():
    with open(f"resources/logical_model_to_profile.json", encoding="utf-8") as json_file:
        return json.load(json_file)


def resolve_terminology_entry_profile(terminology_entry, element=None):
    querying_data_resolver = GeccoDataSetQueryingMetaDataResolver()
    tree_generator = UITreeGenerator(querying_data_resolver)
    tree_generator.data_set_dir = "resources/differential/"
    tree_generator.module_dir = "resources/differential/gecco"
    logical_to_profile_mapping = load_logical_to_profile_mapping()
    name = logical_to_profile_mapping.get(to_upper_camel_case(terminology_entry.display),
                                          to_upper_camel_case(terminology_entry.display))
    for filename in os.listdir("resources/differential/gecco/package"):
        if name in filename and "snapshot" in filename:
            with open("resources/differential/gecco/package" + "/" + filename, encoding="UTF-8") as profile_file:
                profile_data = json.load(profile_file)
                sub_trees = tree_generator.generate_ui_subtree(profile_data)
                if len(sub_trees) > 1:
                    terminology_entry.children += sub_trees
                    terminology_entry.leaf = False
                    terminology_entry.selectable = False
                else:
                    terminology_entry = sub_trees[0]
    if element:
        terminology_entry.display = get_german_display(element) if get_german_display(element) else element["short"]


def get_term_codes(element):
    # Do not use code once using an Ontoserver to resolve the children.
    term_codes = []
    if "code" in element:
        for code in element["code"]:
            term_codes.append(TermCode(code["system"], code["code"], code["display"],
                                       code["version"] if "version" in code else None))
    if not term_codes:
        term_codes.append(TermCode("fdpg.mii.gecco", element["short"], element["short"]))
    return term_codes


def get_german_display(element):
    for extension in element["_short"]["extension"]:
        next_value_is_german_display_content = False
        for nested_extension in extension["extension"]:
            if nested_extension["url"] == "lang":
                next_value_is_german_display_content = nested_extension["valueCode"] == "de-DE"
                continue
            elif next_value_is_german_display_content:
                return nested_extension["valueMarkdown"]
    return None


def generate_gecco_tree():
    return create_terminology_definition_for(get_gecco_categories())


def denormalize_ui_profile_to_old_format(ui_tree: List[TermEntry], term_code_to_profile_name: Dict[TermCode, str],
                                         ui_profile_name_to_profile: Dict[str, UIProfile]):
    """
    Denormalizes the ui tree and ui profiles to the old format

    :param ui_tree: entries to denormalize
    :param term_code_to_profile_name: mapping from term codes to profile names
    :param ui_profile_name_to_profile: ui profiles to use
    :return: denormalized entries
    """
    for entry in ui_tree:
        if entry.selectable:
            try:
                ui_profile = ui_profile_name_to_profile[term_code_to_profile_name[entry.termCode]]
                entry.to_v1_entry(ui_profile)
            except KeyError:
                print("No profile found for term code " + entry.termCode.code)
        for child in entry.children:
            denormalize_ui_profile_to_old_format([child], term_code_to_profile_name, ui_profile_name_to_profile)


if __name__ == '__main__':

    parser = configure_args_parser()
    args = parser.parse_args()

    generate_result_folder()

    # Download the packages
    if args.download_packages:
        download_simplifier_packages(core_data_sets)
    # ----Time consuming: Only execute initially or on changes----
    if args.generate_snapshot:
        # generate_snapshots("resources/core_data_sets")
        generate_snapshots("resources/differential", core_data_sets)
    # -------------------------------------------------------------

    # You shouldn't need different implementations for the different generators
    resolver = GeccoDataSetQueryingMetaDataResolver()

    if args.generate_ui_trees:
        trees = generate_gecco_tree()
        write_ui_trees_to_files(trees, "ui_trees")

    if args.generate_ui_profiles:
        profile_generator = UIProfileGenerator(resolver)
        ui_profiles = profile_generator.generate_ui_profiles("resources/differential")[1].values()
        write_ui_profiles_to_files(ui_profiles)

    if args.generate_mapping:
        cql_generator = CQLMappingGenerator(resolver)
        cql_concept_mappings = cql_generator.generate_mapping("resources/differential")[1].values()
        write_mappings_to_files(cql_concept_mappings)

        fhir_search_generator = FHIRSearchMappingGenerator(resolver)
        fhir_search_mappings = fhir_search_generator.generate_mapping("resources/differential")[1].values()
        write_mappings_to_files(fhir_search_mappings)

    if args.generate_old_format:
        ui_trees = generate_gecco_tree()
        profile_generator = UIProfileGenerator(resolver)
        ui_profiles = profile_generator.generate_ui_profiles("resources/differential")
        term_code_to_ui_profile_name = {context_tc[1]: profile_name for context_tc, profile_name in
                                        ui_profiles[0].items()}
        denormalize_ui_profile_to_old_format(ui_trees, term_code_to_ui_profile_name, ui_profiles[1])
        write_ui_trees_to_files(ui_trees, "ui-profiles-old")

    # move_back_other(category_entries)
    #
    # category_entries += core_data_category_entries
    # dbw = DataBaseWriter()
    # dbw.add_ui_profiles_to_db(category_entries)
    # generate_term_code_mapping(category_entries)
    # generate_term_code_tree(category_entries)
    # if args.generate_csv:
    #     to_csv(category_entries)

    # dump data from db with
    # docker exec -t 7ac5bfb77395 pg_dump --dbname="codex_ui" --username=codex-postgres
    # --table=UI_PROFILE_TABLE > ui_profile_dump_230822
