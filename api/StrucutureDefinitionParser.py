from __future__ import annotations

import json
import os
from typing import List

from TerminologService.ValueSetResolver import get_termcodes_from_onto_server, get_term_code_display_from_onto_server
from model.UIProfileModel import VALUE_TYPE_OPTIONS
from model.UiDataModel import TermCode

UCUM_SYSTEM = "http://unitsofmeasure.org"
FHIR_TYPES_TO_VALUE_TYPES = {
    "code": "concept",
    "Quantity": "quantity",
    "Reference": "reference",
    "CodeableConcept": "concept"
}


class InvalidValueTypeException(Exception):
    pass


def get_element_from_snapshot(profile_snapshot, element_id) -> dict:
    """
    Returns the element from the given FHIR profile snapshot at the given element id
    :param profile_snapshot: FHIR profile snapshot
    :param element_id: element id
    :return: element
    """
    try:
        for element in profile_snapshot["snapshot"]["element"]:
            if "id" in element and element["id"] == element_id:
                return element
    except KeyError:
        print(
            f"KeyError the element id: {element_id} is not in the snapshot or the snapshot has no snapshot "
            f"elements")
    else:
        return {}


def get_profiles_with_base_definition(fhir_dataset_dir: str, base_definition: str) -> dict:
    """
    Returns the profiles that have the given base definition
    :param fhir_dataset_dir: path to the FHIR dataset directory
    :param base_definition: base definition
    :return: generator of profiles that have the given base definition
    """
    for module_dir in [folder for folder in os.scandir(fhir_dataset_dir) if folder.is_dir()]:
        files = [file for file in os.scandir(f"{module_dir.path}/package") if file.is_file()
                 and file.name.endswith("snapshot.json")]
        for file in files:
            with open(file.path, "r", encoding="utf8") as f:
                profile = json.load(f)
                if profile.get("baseDefinition") == base_definition:
                    return profile
                elif profile.get("type") == base_definition.split("/")[-1]:
                    return profile


def get_extension_definition(module_dir: str, extension_profile_url: str) -> dict:
    """
    Returns the FHIR extension definition for the given extension profile url, the extension has to be located in
    {module_dir}/package/extension
    :param module_dir: path to the module directory
    :param extension_profile_url:  extension profile url
    :return: extension definition
    """
    files = [file for file in os.scandir(f"{module_dir}/package/extension") if file.is_file()
             and file.name.endswith("snapshot.json")]
    for file in files:
        with open(file.path, "r", encoding="utf8") as f:
            profile = json.load(f)
            if profile.get("url") == extension_profile_url:
                return profile


def resolve_defining_id(profile_snapshot: dict, defining_id: str, data_set_dir: str, module_dir: str) \
        -> dict | str:
    """
    Basic compiler for the following syntax:
    implicitPathExpression:
    : resolveExpression '.' FHIRElementId
    ;
    castExpression:
    : implicitPathExpression 'as' FHIRType
    ;
    FHIRType:
    'ValueSetUrl', 'Reference'
    ;
    example: ((Specimen.extension:festgestellteDiagnose as Reference).value[x] as Reference).code.coding:icd10-gm as
    ValueSet
    -> lookup extension url defined at Specimen.extension:festgestellteDiagnose -> Profile with this url
    -> lookup value[x] at the extension profile -> Reference type with value Condition -> lookup Condition profile
    -> lookup code.coding:icd-10-gm at the Condition profile -> extraction as ValueSet
    Resolves the given expression to the specified FHIR type by resolving the element ids to the referenced
    extensions and profiles and then applying the FHIRElementId to the resolved profile or extension and finally
    casting the result to the specified FHIR type. Currently only the ValueSet type is supported.
    :param profile_snapshot: FHIR profile snapshot
    :param defining_id: defining id
    :param module_dir: path to the module directory
    :param data_set_dir: path to the FHIR dataset directory
    :return: resolved defining id
    """
    print(f"Resolving: {defining_id}")
    statement = defining_id
    full_statement = statement[statement.rfind('('): statement.find(')') + 1]
    if "ext:" in full_statement:
        extension_url = statement[statement.find("ext:") + 4:statement.find(")")]
        extension_profile = get_extension_definition(module_dir, extension_url)
        if extension_profile is not None:
            extension_type = extension_profile.get("type")
            defining_id = defining_id.replace(full_statement, extension_type)
            return resolve_defining_id(extension_profile, defining_id, data_set_dir,
                                       module_dir)
        else:
            raise Exception(f"Extension profile not found for {statement}")
    elif "ref:" in full_statement:
        base_definition = statement[statement.find("ref:") + 4:statement.find(")")]
        reference_profile = get_profiles_with_base_definition(data_set_dir, base_definition)
        if reference_profile is not None:
            reference_type = reference_profile.get("type")
            defining_id = defining_id.replace(full_statement, reference_type)
            return resolve_defining_id(reference_profile, defining_id, data_set_dir,
                                       module_dir)
        else:
            raise Exception(f"Reference profile not found for {statement}")
    full_statement = full_statement[1:-1]
    if "as Reference" in statement:
        statement = full_statement.split(' as Reference')[0]
        print(f"Resolving: {statement}")
        resolved_element = get_element_from_snapshot(profile_snapshot, statement)
        if value_types := resolved_element.get("type"):
            if len(value_types) > 1:
                raise Exception(f"Could not resolve {defining_id} too many value types" + value_types)
            for value_type in value_types:
                if value_type.get("code") == "Reference":
                    reference_url = "ref:" + value_type.get("targetProfile")[0]
                    defining_id = defining_id.replace(full_statement, reference_url)
                    print(f"Resolved reference: {defining_id}")
                    return resolve_defining_id(profile_snapshot, defining_id, data_set_dir,
                                               module_dir)
                elif value_type.get("code") == "Extension":
                    extension_url = "ext:" + value_type.get("profile")[0]
                    defining_id = defining_id.replace(full_statement, extension_url)
                    print(f"Resolving extension: {defining_id}")
                    return resolve_defining_id(profile_snapshot, defining_id, data_set_dir,
                                               module_dir)
                else:
                    return resolved_element
    elif "as ValueSetUrl" in statement:
        statement = statement.replace(" as ValueSetUrl", "")
        value_set_element = get_element_from_snapshot(profile_snapshot, statement)
        return get_value_set_defining_url(value_set_element, profile_snapshot.get("name"))
    return get_element_from_snapshot(profile_snapshot, statement)


def extract_value_type(value_defining_element: dict, profile_name: str = "") -> VALUE_TYPE_OPTIONS:
    """
    Extracts the value type for the given FHIR profile snapshot at the value defining element id
    :param value_defining_element: element that defines the value
    :param profile_name: name of the FHIR profile for debugging purposes can be omitted
    :return: value type
    """
    if not value_defining_element:
        print(f"Could not find value defining element for {profile_name}")
    fhir_value_types = value_defining_element.get("type")
    if not fhir_value_types:
        raise InvalidValueTypeException(f"No value type defined in element: {str(value_defining_element)}"
                                        f" in profile: {profile_name}")
    if len(fhir_value_types) > 1:
        raise InvalidValueTypeException(f"More than one value type defined in element: "
                                        f"{str(value_defining_element)} refine the profile: " + profile_name)
    return FHIR_TYPES_TO_VALUE_TYPES.get(fhir_value_types[0].get("code")) \
        if fhir_value_types[0].get("code") in FHIR_TYPES_TO_VALUE_TYPES else fhir_value_types[0].get("code")


def get_selectable_concepts(concept_defining_element, profile_name: str = "") -> List[TermCode]:
    """
    Returns the answer options for the given concept defining element
    :param concept_defining_element:
    :param profile_name: name of the FHIR profile for debugging purposes can be omitted
    :return: answer options as term codes
    :raises InvalidValueTypeException: if no valueSet is defined for the concept defining element
    """
    if binding := concept_defining_element.get("binding"):
        if value_set_url := binding.get("valueSet"):
            return get_termcodes_from_onto_server(value_set_url)
        else:
            raise InvalidValueTypeException(f"No value set defined in element: {str(binding)}"
                                            f" in profile: {profile_name}")
    else:
        raise InvalidValueTypeException(f"No binding defined in element: {str(concept_defining_element)}"
                                        f" in profile: {profile_name}")


def get_units(unit_defining_element, profile_name: str = "") -> List[TermCode]:
    if unit_code := unit_defining_element.get("fixedCode"):
        return [TermCode(UCUM_SYSTEM, unit_code, unit_code)]
    else:
        raise InvalidValueTypeException(f"No unit defined in element: {str(unit_defining_element)}"
                                        f" in profile: {profile_name}")


def get_value_set_defining_url(value_set_defining_element: dict, profile_name: str = "") -> str:
    """
    Returns the value set defining url for the given value set defining element
    :param value_set_defining_element: element that defines the value set
    :param profile_name: name of the FHIR profile for debugging purposes can be omitted
    :return: canonical url of the value set
    """
    if binding := value_set_defining_element.get("binding"):
        if value_set_url := binding.get("valueSet"):
            return value_set_url
        else:
            raise InvalidValueTypeException(f"No value set defined in element: {str(binding)}"
                                            f" in profile: {profile_name}")
    else:
        raise InvalidValueTypeException(f"No binding defined in element: {str(value_set_defining_element)}"
                                        f" in profile: {profile_name}")


def pattern_coding_to_term_code(element):
    """
    Converts a patternCoding to a term code
    :param element: element node from the snapshot with a patternCoding
    :return: term code
    """
    code = element["patternCoding"]["code"]
    system = element["patternCoding"]["system"]
    display = get_term_code_display_from_onto_server(system, code)
    if display.isupper():
        display = display.title()
    term_code = TermCode(system, code, display)
    return term_code


if __name__ == "__main__":
    with open("example/mii_core_data_set/resources/core_data_sets/de.medizininformatikinitiative.kerndatensatz"
              ".biobank#1.0.3/package/StructureDefinition-Specimen-snapshot.json", "r") as f:
        profile = json.load(f)
        print(resolve_defining_id(profile,
                                  "((Specimen.extension:festgestellteDiagnose as Reference).value[x] "
                                  "as Reference).code.coding:icd10-gm as ValueSetUrl",
                                  "example/mii_core_data_set/resources/core_data_sets",
                                  "example/mii_core_data_set/resources/fdpg_differential/"
                                  "Bioprobe"))
