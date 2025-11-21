import copy
import json
import os
import re
from pathlib import Path
from typing import List, Optional, Generator, Tuple, Any, Set

from fhir.resources.R4B.elementdefinition import (
    ElementDefinition,
    ElementDefinitionType,
)
from typing_extensions import deprecated

from cohort_selection_ontology.core.terminology.client import (
    CohortSelectionTerminologyClient as TerminologyClient,
)
from cohort_selection_ontology.model.ui_data import (
    TermCode,
    TranslationDisplayElement,
    Translation,
)
from cohort_selection_ontology.model.ui_profile import VALUE_TYPE_OPTIONS, ValueSet
from common.exceptions.translation import MissingTranslationException
from common.exceptions.typing import InvalidValueTypeException
from common.model.fhir.structure_definition import (
    StructureDefinitionSnapshot,
    ProcessedElementResult,
)
from common.util.collections.functions import flatten
from common.util.fhir.enums import FhirDataType
from common.util.log.functions import get_class_logger

UCUM_SYSTEM = "http://unitsofmeasure.org"
translation_map_default = {
    "de-DE": {"language": "de-DE", "value": ""},
    "en-US": {"language": "en-US", "value": ""},
}


logger = get_class_logger("structure_definition_functions")


def find_polymorphic_value(
    data: ElementDefinition, polymorphic_elem_prefix: str
) -> Optional[Any]:
    """
    Attempts to find the value of a polymorphic element by iterating over all possible data type-specific names

    :param data: FHIR structure to find the value of a contained polymorphic element in
    :param polymorphic_elem_prefix: name of the polymorphic element in the structure
    :return: Value of the contained element or `None` if no such element exists/it has no value
    """
    if data is None:
        return None
    for field_name in data.model_fields.keys():
        if field_name.startswith(polymorphic_elem_prefix):
            v = getattr(data, field_name)
            if v:
                return v
    return None


def parse(chained_fhir_element_id) -> List[str] | str:
    """
    Parses a chained fhir element id with the given Grammar:
    chained_fhir_element_id ::= "(" chained_fhir_element_id ")" ( "." fhir_element_id )* | fhir_element_id
    :param chained_fhir_element_id: the chained fhir element id
    :return: the parsed fhir element id
    """
    if ".where" in chained_fhir_element_id:
        main_part, condition_and_rest = chained_fhir_element_id.split(".where", 1)
        condition_part, rest_part = condition_and_rest.split(")", 1)
        condition_part = condition_part.strip("(")
        rest_part = rest_part.strip(":")
        return [
            parse(f"{main_part.strip()}:{rest_part.strip()}"),
            parse(condition_part.strip()),
        ]
    tokens = tokenize(chained_fhir_element_id)
    result = parse_tokens(tokens)
    return result


def parse_tokens(tokens: List[str]) -> List[str] | str:
    """
    returns the parsed syntax node of the tokens
    :param tokens: the syntax tokens
    :return: the parsed syntax node represented as a list of child nodes or a string
    """
    if not tokens:
        raise ValueError("Empty string")

    token = tokens.pop(0)

    if token == ".where":
        return parse_tokens(tokens)
    elif token == "(":
        sub_tree = []
        while tokens and tokens[0] != ")":
            sub_tree.append(parse_tokens(tokens))
        if not tokens:
            raise ValueError("Missing closing parenthesis")
        tokens.pop(0)  # Remove the closing parenthesis
        if tokens and tokens[0] != ")":
            sub_tree.append(parse_tokens(tokens))
        return sub_tree
    elif token == ")":
        raise ValueError("Unexpected )")
    else:
        if tokens and tokens[0] != ")":
            return [token, parse_tokens(tokens)]
        else:
            return token


def tokenize(chained_fhir_element_id):
    """
    Tokenizes a chained fhir element id with the given Grammar:
    chained_fhir_element_id ::= "(" chained_fhir_element_id ")" ( "." fhir_element_id )* | fhir_element_id
    :param chained_fhir_element_id: the chained fhir element id
    :return: the tokenized fhir element id
    """
    return (
        chained_fhir_element_id.replace("(", " ( ")
        .replace(")", " ) ")
        .replace(".where", " .where ")
        .split()
    )


def is_structure_definition(file: Path) -> bool:
    """
    Checks if a file is a structured definition
    :param file: potential structured definition
    :return: true if the file is a structured definition else false
    """
    with open(file, encoding="UTF-8") as json_file:
        try:
            json_data = json.load(json_file)
        except json.decoder.JSONDecodeError:
            logger.warning(f"Could not decode {file}")
            return False
        if json_data.get("resourceType") == "StructureDefinition":
            return True
        return False


def is_element_in_snapshot(
    profile_snapshot: StructureDefinitionSnapshot, element_id: str
) -> bool:
    """
    Returns true if the given element id is in the given FHIR profile snapshot
    :param profile_snapshot:  of FHIR profile in which the element should be
    :param element_id: element id
    :return: true if the given element id is in the given FHIR profile snapshot
    """
    if profile_snapshot.get_element_by_id(element_id) is not None:
        return True
    return False


def structure_definition_from_path(path: Path) -> StructureDefinitionSnapshot:
    with open(path, "r", encoding="UTF-8") as f:
        snapshot = StructureDefinitionSnapshot.model_validate_json(f.read())
        return snapshot


def get_profiles_with_base_definition(
    modules_dir_path: str | Path, base_definition: str
) -> Generator[Tuple[StructureDefinitionSnapshot, str], None, None]:
    """
    Returns the profiles that have the given base definition
    :param modules_dir_path: Path to the modules directory
    :param base_definition: Base definition
    :return: Generator of profiles that have the given base definition
    """
    for module_dir in [
        folder for folder in os.scandir(modules_dir_path) if folder.is_dir()
    ]:
        logger.debug(f"Searching in {module_dir.path}")
        files = list(
            Path(module_dir.path, "differential", "package").rglob("*snapshot.json")
        )
        logger.debug(
            f"Found {len(files)} snapshot file(s) in module @ '{module_dir.path}'"
        )
        for file in files:
            with open(file, mode="r", encoding="utf8") as f:
                profile = StructureDefinitionSnapshot.model_validate_json(f.read())
                if profile.baseDefinition == base_definition:
                    yield profile, module_dir.path
                elif profile.type == base_definition.split("/")[-1]:
                    yield profile, module_dir.path
                elif profile.url == base_definition:
                    yield profile, module_dir.path


def get_extension_definition(
    module_dir: str, extension_profile_url: str
) -> StructureDefinitionSnapshot:
    """
    Returns the FHIR extension definition for the given extension profile url,
        the extension has to be located in
    {module_dir}/package/extension
    :param module_dir: path to the module directory
    :param extension_profile_url:  extension profile url
    :return: extension definition
    """
    files = [
        file
        for file in os.scandir(
            os.path.join(module_dir, "differential", "package", "extension")
        )
        if file.is_file() and file.name.endswith("snapshot.json")
    ]
    for file in files:
        with open(file.path, "r", encoding="utf8") as f:
            profile = StructureDefinitionSnapshot.model_validate_json(f.read())
            if profile.url == extension_profile_url:
                return profile
    else:
        raise FileNotFoundError(
            f"Could not find extension definition for extension profile url: {extension_profile_url}"
        )


def get_element_defining_elements(
    profile_snapshot: StructureDefinitionSnapshot,
    chained_element_id: str,
    start_module_dir: str,
    data_set_dir: str | Path,
) -> List[ElementDefinition] | None:
    return [
        element_with_source_snapshot.element
        for element_with_source_snapshot in get_element_defining_elements_with_source_snapshots(
            profile_snapshot, chained_element_id, start_module_dir, data_set_dir
        )
    ]


def resolve_defining_id(
    profile_snapshot: StructureDefinitionSnapshot,
    defining_id: str,
    modules_dir_path: str | Path,
    module_dir_name: str,
) -> ElementDefinition | None:
    """
    :param profile_snapshot: StructureDefinition which the defining id belongs to
    :param defining_id: defining id
    :param module_dir_name: name of the module directory like 'Bioprobe' or 'Diagnose'
    :param modules_dir_path: path to the FHIR dataset directory
    :return: resolved defining id
    """
    return get_element_defining_elements(
        profile_snapshot, defining_id, module_dir_name, modules_dir_path
    )[-1]


def get_element_defining_elements_with_source_snapshots(
    profile_snapshot: StructureDefinitionSnapshot,
    chained_element_id,
    start_module_dir: str | Path,
    data_set_dir: str | Path,
) -> List[ProcessedElementResult]:
    parsed_list = list(flatten(parse(chained_element_id)))
    return process_element_id(
        profile_snapshot, parsed_list, start_module_dir, data_set_dir
    )


def process_element_id(
    profile_snapshot: StructureDefinitionSnapshot,
    element_ids,
    module_dir_name: str,
    modules_dir_path: str | Path,
) -> List[ProcessedElementResult] | None:
    results = []

    while element_ids:
        element_id = element_ids.pop(0)
        if element_id.startswith("."):
            raise ValueError("Element id must start with a resource type")
        element: ElementDefinition = profile_snapshot.get_element_by_id(element_id)
        result = [
            ProcessedElementResult(
                element=element,
                profile_snapshot=profile_snapshot,
                module_dir=module_dir_name,
                last_short_desc=None,
            )
        ]

        for elem in (
            element.type if element is not None and element.type is not None else []
        ):
            if elem.code == "Extension":
                profile_urls = elem.profile
                if len(profile_urls) > 1:
                    raise Exception("Extension with multiple types not supported")
                extension: StructureDefinitionSnapshot = get_extension_definition(
                    os.path.join(modules_dir_path, module_dir_name), profile_urls[0]
                )
                element_ids.insert(0, f"Extension" + element_ids.pop(0))
                result.extend(
                    process_element_id(
                        profile_snapshot=extension,
                        element_ids=element_ids,
                        module_dir_name=module_dir_name,
                        modules_dir_path=modules_dir_path,
                    )
                )
            elif elem.code == "Reference":
                target_profiles = elem.targetProfile
                if len(target_profiles) > 1:
                    logger.warning(
                        f"Reference element '{element_id}' supports multiple profiles => Using first"
                    )
                target_resource_type = elem.targetProfile[0]
                partial_id = element_ids.pop(0)
                profiles = list(
                    get_profiles_with_base_definition(
                        modules_dir_path, target_resource_type
                    )
                )
                if len(profiles) == 0:
                    raise Exception(
                        f"No profile could be found that matches target profile '{target_resource_type}' and contains "
                        f"element with ID '{partial_id}' [ref_element_id='{element_id}']"
                    )
                for referenced_profile, ref_module_dir_name in profiles:
                    new_element_id = referenced_profile.type + partial_id
                    if not is_element_in_snapshot(referenced_profile, new_element_id):
                        continue
                    element_ids.insert(0, new_element_id)
                    result.extend(
                        process_element_id(
                            profile_snapshot=referenced_profile,
                            element_ids=element_ids,
                            module_dir_name=ref_module_dir_name,
                            modules_dir_path=modules_dir_path,
                        )
                    )
                    break
        results.extend(result)
    return results


def process_element_definition(
    snapshot_element: ElementDefinition,
    default: str = None,
) -> (TermCode, TranslationDisplayElement):
    """
    Uses the provided ElementDefinition instance to determine the
    attribute code as well as associated display values
    (primary value and - if present - language variants)

    :param snapshot_element: ElementDefinition instance to be processed
    :param default: value to use as fallback if there is no 'id' in the ElementDefinition
    :return: the attribute code and suitable display values
    """
    if snapshot_element.id is None:
        key = default
    else:
        key = get_attribute_key(str(snapshot_element.id))

    display = get_display_from_element_definition(snapshot_element, default=key)

    return (
        TermCode(
            system="http://hl7.org/fhir/StructureDefinition",
            code=str(key),
            display=display.original,
        ),
        display,
    )


def get_types_supported_by_element(
    element: ElementDefinition,
) -> List[ElementDefinitionType]:
    """
    Retrieves the `type` element of an `ElementDefinition` instance
    :param element: `ElementDefinition` instance to retrieve supported types for
    :return: List of `ElementDefinition.type` `BackboneElement` instances representing the supported types
    """
    return element.type or []


def find_type_element(
    element: ElementDefinition, fhir_type: FhirDataType
) -> Optional[ElementDefinitionType]:
    """
    Searches for the `ElementDefinition.type` element matching the provided FHIR data type
    :param element: `ElementDefinition` instance through which supported types to search
    :param fhir_type: FHIR data type to search for
    :return: Matching `ElementDefinition.type` element or `None` of the type is not supported
    """
    for t in get_types_supported_by_element(element):
        if t.code == fhir_type.value:
            return t
    return None


def supports_type(element: ElementDefinition, fhir_type: FhirDataType) -> bool:
    """
    Determined if the given `ElementDefinition` instance supports the provided FHIR data type
    :param element: `ElementDefinition` instance to check
    :param fhir_type: FHIR data type for which to determine whether it is support by the `ElementDefinition` instance
    :return: Boolean indicating support
    """
    return find_type_element(element, fhir_type) is not None


def extract_value_type(
    value_defining_element: ElementDefinition,
    profile_name: str = "",
) -> VALUE_TYPE_OPTIONS:
    """
    Extracts the value type for the given FHIR profile snapshot at the value defining element id
    :param value_defining_element: element that defines the value
    :param profile_name: name of the FHIR profile for debugging purposes. Can be omitted
    :return: value type
    """
    if not value_defining_element:
        logger.warning(f"Could not find value defining element for {profile_name}")
    fhir_value_types = value_defining_element.type
    if not fhir_value_types:
        raise InvalidValueTypeException(
            f"No value type defined in element: {str(value_defining_element)}"
            f" in profile: {profile_name}"
        )
    if len(fhir_value_types) > 1:
        raise InvalidValueTypeException(
            f"More than one value type defined in element: "
            f"{str(value_defining_element)} refine the profile: " + profile_name
        )
    return fhir_value_types[0].code


def get_selectable_concepts(
    concept_defining_element: ElementDefinition,
    profile_name: str = "",
    client: TerminologyClient = None,
) -> ValueSet:
    # TODO: still needs test. Not yet tested because of internet shortage
    """
    Returns the answer options for the given concept defining element
    :param concept_defining_element: ``ElementDefinition`` that defines the concept
    :param profile_name: name of the FHIR profile for debugging purposes. Can be omitted
    :param client: Client to perform terminology server operations with
    :return: answer options as term codes
    :raises InvalidValueTypeException: if no valueSet is defined for the concept defining element
    """
    if binding := concept_defining_element.binding:
        if value_set_url := binding.valueSet:
            if "|" in value_set_url:
                value_set_url = value_set_url.split("|")[0]
            return ValueSet(
                url=value_set_url,
                valueSet=client.get_value_set_expansion(value_set_url),
            )
        else:
            raise InvalidValueTypeException(
                f"No value set defined in element: {str(binding)}"
                f" in profile: {profile_name}"
            )
    else:
        raise InvalidValueTypeException(
            f"No binding defined in element: {str(concept_defining_element.id)}"
            f" in profile: {profile_name}"
        )


def get_units(
    unit_defining_element: ElementDefinition,
    profile_name: str = "",
    client: TerminologyClient = None,
) -> List[TermCode]:
    """

    :param profile_name: Name of the FHIR profile for debugging purposes. Can be omitted
    :param unit_defining_element: ``ElementDefinition`` that defines the unit
    :param client: Client to perform terminology server operations with
    :return: a list of term codes

    Returns:

    """
    # TODO: still needs test. Not yet tested because of internet shortage
    if unit_code := unit_defining_element.fixedCode:
        return [TermCode(system=UCUM_SYSTEM, code=unit_code, display=unit_code)]
    elif unit_code := unit_defining_element.patternCode:
        return [TermCode(system=UCUM_SYSTEM, code=unit_code, display=unit_code)]
    elif binding := unit_defining_element.binding:
        if value_set_url := binding.valueSet:
            return client.get_termcodes_for_value_set(value_set_url)
        else:
            raise InvalidValueTypeException(
                f"No value set defined in element: {str(binding)}"
                f" in profile: {profile_name}"
            )
    else:
        raise InvalidValueTypeException(
            f"No unit defined in element: {str(unit_defining_element.id)}"
            f" in profile: {profile_name}"
        )


def extract_reference_type(
    value_defining_element: ElementDefinition,
    modules_dir: str | Path,
    profile_name: str = "",
) -> str:
    """
    Extracts the reference type from the given value defining element
    :param value_defining_element: element that defines the value
    :param modules_dir: Path to the directory containing all module data
    :param profile_name: name of the FHIR profile for debugging purposes. Can be omitted
    :return: reference type
    """
    if not value_defining_element:
        logger.warning(f"Could not find value defining element for {profile_name}")
    # if len(target_profiles) > 1:
    #     raise Exception("Reference with multiple types not supported")
    if not value_defining_element.targetProfile:
        logger.warning(f"Could not find target profile for {profile_name}")
    target_resource_type = value_defining_element.targetProfile[0]
    # FIXME This should not be hardcoded to CDS_Module
    referenced_profile, _ = next(
        get_profiles_with_base_definition(modules_dir, target_resource_type)
    )
    return referenced_profile.type


def pattern_coding_to_term_code(element: ElementDefinition, client: TerminologyClient):
    # TODO: write tests
    """
    Converts a patternCoding to a term code
    :param element: Element node from the snapshot with a patternCoding
    :param client: Client instance to perform terminology server operations
    :return: Term code
    """
    code = element.patternCoding.code
    system = element.patternCoding.system
    display = client.get_term_code_display(system, code)
    version = str(element.patternCoding.version)

    if display.isupper():
        display = display.title()
    term_code = TermCode(system=system, code=code, display=display, version=version)
    return term_code


def fixed_coding_to_term_code(
    element: ElementDefinition,
    client: TerminologyClient,
):
    # TODO: unit tests
    """
    Converts a fixedCoding to a term code
    :param element: Element node from the snapshot with a patternCoding
    :param client: Client instance to perform terminology server operations
    :return: Term code
    """
    code = element.fixedCoding.code
    system = element.fixedCoding.system
    display = client.get_term_code_display(system, code)
    if display.isupper():
        display = display.title()
    term_code = TermCode(system=system, code=code, display=display)
    return term_code


def pattern_codeable_concept_to_term_code(
    element: ElementDefinition, client: TerminologyClient
):
    # TODO: unit tests

    """
    Converts a patternCodeableConcept to a term code
    :param element: Element node from the snapshot with a patternCoding
    :param client: Client instance to perform terminology server operations
    :return: Term code
    """
    code: str = element.patternCodeableConcept.coding[0].code
    system: str = element.patternCodeableConcept.coding[0].system
    display: str = client.get_term_code_display(system, code)
    version = element.patternCodeableConcept.coding[0].version
    if display.isupper():
        display = display.title()
    term_code = TermCode(system=system, code=code, display=display, version=version)
    return term_code


def fixed_codeable_concept_to_term_code(
    element: ElementDefinition, client: TerminologyClient
):
    # TODO: unit tests
    """
    Converts a fixedCodeableConcept to a term code
    :param element: Element node from the snapshot with a patternCoding:
    :param client: Client instance to perform terminology server operations
    :return: Term code
    """
    code = element.patternCodeableConcept.coding[0].code
    system = element.patternCodeableConcept.coding[0].system
    display = client.get_term_code_display(system, code)
    version = element.fixedCodeableConcept.coding[0].version
    if display.isupper():
        display = display.title()
    term_code = TermCode(system=system, code=code, display=display, version=version)
    return term_code


def get_value_set_defining_url(
    value_set_defining_element: ElementDefinition, profile_name: str = ""
) -> str:
    # TODO: decide to keep and test? no usage in project found.
    #  Everywhere where i could be used its skipping this function using binding.valueSet directly
    """
    Returns the value set defining url for the given value set defining element
    :param value_set_defining_element: ``ElementDefinition`` that defines the value set
    :param profile_name: Name of the FHIR profile for debugging purposes. Can be omitted
    :raises InvalidValueTypeException: if no valueSet or binding is defined
    :return: Canonical URL of the value set
    """
    if binding := value_set_defining_element.binding:
        if value_set_url := binding.valueSet:
            return value_set_url
        raise InvalidValueTypeException(
            f"No value set defined in element: {str(binding)}"
            f" in profile: {profile_name}"
        )
    else:
        raise InvalidValueTypeException(
            f"No binding defined in element: {str(value_set_defining_element)}"
            f" in profile: {profile_name}"
        )


def get_element_type(element: ElementDefinition) -> str:
    # TODO: unit tests
    """
    Returns the type of the given element
    :param element: Parent element
    :return: Type of the element
    """
    element_types = element.type
    if len(element_types) > 1:
        types = [element_type.code for element_type in element_types]
        if "dateTime" in types and "Period" in types:
            return "dateTime"
        # FIXME: Currently hard coded should be generalized
        if "Reference" in types and "CodeableConcept" in types:
            return "CodeableConcept"
        else:
            raise Exception("Multiple types are currently not supported")
    elif not element_types:
        raise Exception(
            "No type found for element "
            + element.id
            + " in profile element \n"
            + element.id
        )
    return element_types[0].code


def get_extension_url(element: ElementDefinition):
    # TODO: unit tests

    extension_profiles = element.type[0].profile
    if len(extension_profiles) > 1:
        raise Exception("More than one extension found")
    if not extension_profiles:
        raise Exception("No extension profile url found in element: \n" + element.id)
    return extension_profiles[0]


def replace_x_with_cast_expression(element_path: str, element_type: str):
    # TODO: unit tests

    # Regular expression to capture [x] and [x]:arbitrary_slicing
    match = re.search(r"(\[x](?::\w+)?)", element_path)
    if match:
        pre_match = element_path[: match.start()]
        post_match = element_path[match.end() :]
        # TODO: Rework handling of FHIRPath-like expressions. We currently only use string manipulation when working
        #       with such expressions which leads to a lot of edge case handling and double checking. Instead strings
        #       should be tokenized somewhat so that information about the expression is readily available throughout
        #       the processing chain
        # Always add parenthesis for now to avoid functions agnostic to the actual structure of the expression to
        # generate invalid FHIRPath expressions accidentally
        replacement = f"({pre_match} as {element_type}){post_match}"
        return replacement
    return element_path


def try_get_term_code_from_sub_elements(
    profile_snapshot: StructureDefinitionSnapshot,
    parent_coding_id,
    data_set_dir,
    module_dir,
    client: TerminologyClient,
) -> Optional[TermCode]:
    """"""
    if profile_snapshot.get_element_by_id(parent_coding_id + ".code") is not None:
        return None
    code_element = resolve_defining_id(
        profile_snapshot, parent_coding_id + ".code", data_set_dir, module_dir
    )
    system_element = resolve_defining_id(
        profile_snapshot,
        parent_coding_id + ".system",
        data_set_dir,
        module_dir,
    )
    if code_element and system_element:
        if "patternCode" in code_element and "patternUri" in system_element:
            return TermCode(
                system=system_element["patternUri"],
                code=code_element["patternCode"],
                display=client.get_term_code_display(
                    system_element["patternUri"], code_element["patternCode"]
                ),
            )
        if "fixedCode" in code_element and "fixedUri" in system_element:
            return TermCode(
                system=system_element["fixedUri"],
                code=code_element["fixedCode"],
                display=client.get_term_code_display(
                    system_element["fixedUri"], code_element["fixedCode"]
                ),
            )

    return None


def get_fixed_term_codes(
    profile_snapshot: StructureDefinitionSnapshot,
    element: ElementDefinition,
    module_dir,
    data_set_dir,
    client: TerminologyClient,
) -> List[TermCode]:
    """
    Returns the fixed term codes of the given element
    """
    if element.fixedCodeableConcept is not None:
        return [fixed_codeable_concept_to_term_code(element, client)]
    elif element.patternCodeableConcept is not None:
        return [pattern_codeable_concept_to_term_code(element, client)]
    elif element.fixedCoding is not None and element.fixedCoding.code is not None:
        return [fixed_coding_to_term_code(element, client)]
    elif element.patternCoding is not None and element.patternCoding.code is not None:
        return [pattern_coding_to_term_code(element, client)]
    else:
        if tc := try_get_term_code_from_sub_elements(
            profile_snapshot, element.id, module_dir, data_set_dir, client
        ):
            return [tc]
    return []


def get_term_code_by_id(
    profile_snapshot: StructureDefinitionSnapshot,
    term_code_defining_id: str,
    data_set_dir,
    module_dir,
    client: TerminologyClient,
) -> List[TermCode]:
    """
    Returns the term entries for the given term code defining id
    :param profile_snapshot: StructureDefinitionSnapshot which the term_code_defining_id belong to
    :param term_code_defining_id: ID of the element that defines the term code
    :param data_set_dir: Data set directory of the FHIR profile
    :param module_dir: Module directory of the FHIR profile
    :param client: Client instance to perform terminology server operations
    :return: Term entries
    """
    if not term_code_defining_id:
        raise Exception(
            f"No term code defining id given print for {profile_snapshot.name}"
        )

    term_code_defining_element = resolve_defining_id(
        profile_snapshot, term_code_defining_id, data_set_dir, module_dir
    )
    if not term_code_defining_element:
        raise Exception(
            f"Could not resolve term code defining id {term_code_defining_id} "
            f"in {profile_snapshot.name}"
        )
    if term_code_defining_element.patternCoding is not None:
        if term_code_defining_element.patternCoding.code is not None:
            term_code = pattern_coding_to_term_code(term_code_defining_element, client)
            return [term_code]
    if term_code_defining_element.patternCodeableConcept is not None:
        if term_code_defining_element.patternCodeableConcept.coding is not None:
            term_code = pattern_codeable_concept_to_term_code(
                term_code_defining_element, client
            )
            return [term_code]
    if term_code_defining_element.binding:
        value_set = term_code_defining_element.binding.valueSet
        return client.get_termcodes_for_value_set(value_set)
    else:
        tc = try_get_term_code_from_sub_elements(
            profile_snapshot,
            term_code_defining_id,
            data_set_dir,
            module_dir,
            client,
        )
        if tc:
            return [tc]
        raise Exception(
            f"Could not resolve term code defining element: {term_code_defining_id}"
        )


def get_binding_value_set_url(element: ElementDefinition) -> str | None:
    """
    Returns the value set url of the given element
    :param element: element with binding
    :return: value set url
    """
    if element.binding is not None:
        return element.binding.valueSet
    return None


def get_attribute_key(element_id: str) -> str:
    """
    Generates the attribute key from the given element id (`ElementDefinition.id`)
    :param element_id: Element ID the key will be based on
    :return: Attribute key
    """
    if "(" and ")" in element_id:
        element_id = element_id[element_id.rfind("(") + 1 : element_id.find(")")]

    if ":" in element_id:
        element_id = element_id.split(":")[-1]
        key = element_id.split(".")[0]
    else:
        key = element_id.split(".")[-1]

    if not key:
        raise ValueError(f"Could not find key for {element_id}")

    return key


@deprecated("Switch over to process_element_definition to obtain better display values")
def generate_attribute_key(element_id: str) -> TermCode:
    key = get_attribute_key(element_id)
    return TermCode(
        system="http://hl7.org/fhir/StructureDefinition", code=key, display=key
    )


def get_display_from_element_definition(
    snapshot_element: ElementDefinition, default: str = None
) -> TranslationDisplayElement:
    """
    Extracts the display and translations from the descriptive elements within the ElementDefinition instance. If the
    identified `ElementDefinition` instance in the provided snapshot features translations for the elements short
    description, they will be provided as translations of the display value. The `original` display value is determined
    as follows:

    If a snapshot element with the provided if exists:

    - Use the `short` element value of the snapshot element if it exists
    - Otherwise use the `sliceName` element value of the snapshot element if it exists

    Else use the attribute key code

    :param snapshot_element: the element to extract (display) translations from
    :param default: value used as display if there is no other valid source in the element definition
    :return: TranslationDisplayElement instance holding the display value and all language variants
    """

    translations_map = copy.deepcopy(translation_map_default)
    display = default
    try:
        if snapshot_element is None:
            raise MissingTranslationException(
                f"No translations can be extracted since an empty element was passed"
            )
        if snapshot_element.short:
            display = snapshot_element.short
        elif snapshot_element.sliceName:
            logger.info(
                f"Falling back to value of 'sliceName' for original display value of element. A short "
                f"description via 'short' element should be added"
            )
            display = snapshot_element.sliceName

        if (
            snapshot_element.short__ext is None
            or snapshot_element.short__ext.extension is None
        ):
            raise MissingTranslationException(
                f"No translations can be extracted since no ._short element was found"
            )

        for lang_container in snapshot_element.short__ext.extension:
            if (
                lang_container.url
                != "http://hl7.org/fhir/StructureDefinition/translation"
            ):
                continue
            language = next(
                filter(
                    lambda x: x.url == "lang",
                    lang_container.extension,
                )
            ).valueCode
            language_value = next(
                filter(
                    lambda x: x.url == "content",
                    lang_container.extension,
                )
            ).valueString
            translations_map[language] = {
                "language": language,
                "value": language_value,
            }

        if translations_map == translation_map_default:
            logger.warning(
                f"No translation could be identified for element '{snapshot_element.id}' since no "
                f"language extensions are present => Defaulting"
            )

    except MissingTranslationException as exc:
        logger.warning(exc)
    except Exception as exc:
        logger.warning(
            f"Something went wrong when trying to extract translations from element '{snapshot_element.id}'. "
            f"Reason: {exc}",
            exc_info=exc,
        )

    translations_list: List[Translation] = [
        Translation(language=lang, value=translation.get("value"))
        for lang, translation in translations_map.items()
    ]
    return TranslationDisplayElement(original=display, translations=translations_list)


def get_parent_element_type(
    profile_snapshot: StructureDefinitionSnapshot, element_id: str
) -> str:
    # TODO: unit tests

    """
    If the path indicates an arbitrary type [x] the parent element can give insight on its type. This function
    returns the type of the parent element. By searching the element at [x] or at its slicing.
    """
    if "[x]:" not in element_id:
        # remove everything after the [x]
        element_id = re.sub(r"(\[x\]).*", r"\1", element_id)
    else:
        # remove everything after the [x] and the slicing -> everything until the next . after [x]:
        element_id = re.sub(r"(\[x\]).*?(?=\.)", r"\1", element_id)
    if (parent_element := profile_snapshot.get_element_by_id(element_id)) is None:
        element_id = re.sub(r"(\[x\]).*", r"\1", element_id)
        parent_element = profile_snapshot.get_element_by_id(element_id)
    return get_element_type(parent_element)


def translate_element_to_fhir_path_expression(
    profile_snapshot: StructureDefinitionSnapshot,
    elements: List[ElementDefinition],
    is_composite: bool = False,
) -> List[str]:
    # TODO: unit tests

    """
    Translates an element to a fhir search parameter. Be aware not every element is translated alone to a
    fhir path expression. I.E. Extensions elements are translated together with the prior element.
    :param elements: Elements for which the fhir path expressions should be obtained
    :param profile_snapshot: Snapshot of the profile
    :param is_composite: special case for when its composite attribute.  .value.ofType(<valueType>)
    :return: FHIR path expressions
    """
    element = elements.pop(0)
    element_path = element.path
    element_type = get_element_type(element)
    if element_type == "Extension":
        if elements[0].id == "Extension.value[x]":
            element_type = get_element_type(elements[0])
            element_path = (
                f"{element_path}.where(url='{get_extension_url(element)}').value[x]"
            )
            element_path = replace_x_with_cast_expression(element_path, element_type)
        # FIXME: Currently hard coded should be generalized
        elif elements[0].id == "Extension.extension:age.value[x]":
            element_path = f"{element_path}.where(url='{get_extension_url(element)}').extension.where(url='age').value[x]"
            element_path = replace_x_with_cast_expression(element_path, element_type)
    if "[x]" in element_path and "Extension" not in element_path:
        element_type = get_parent_element_type(profile_snapshot, element.id)
        element_path = replace_x_with_cast_expression(element_path, element_type)
        if is_composite:
            element_path = f"value.ofType({element_type})"
    result = [element_path]
    if elements:
        result.extend(
            translate_element_to_fhir_path_expression(profile_snapshot, elements)
        )
    return result


def get_slice_owning_element_id(element_id: str) -> str:
    """
    Returns the parent element id of the provided slice ID
    :param element_id: the slice id
    :return: the parent element id of the provided ID

    Example:
        get_slice_owning_element_id("Observation.component:Diastolic")  => "Observation.component" \n
        get_slice_owning_element_id("Observation.component:Diastolic.code")  => "Observation.component" \n
        get_slice_owning_element_id("Observation.component:Diastolic.code.coding:sct") => "Observation.component:Diastolic.code.coding" \n
    """
    return (
        get_parent_slice_id(element_id).rsplit(":", 1)[0]
        if ":" in element_id
        else element_id
    )


def get_slice_name(element_id: str) -> str | None:
    """
    Return the name of the slice on the lowest level
    :param element_id: the element id
    :return: the name of the slice on the lowest level
    Example:
        get_slice_name("Observation.component:Diastolic")  => "Diastolic" \n
        get_slice_name("Observation.component:Diastolic.code")  => "Diastolic" \n
        get_slice_name("Observation.component:Diastolic.code.coding:sct")  => "sct" \n
    """
    return (
        get_parent_slice_id(element_id).rsplit(":")[-1] if ":" in element_id else None
    )


def get_available_slices(
    element_id: str, profile_snapshot: StructureDefinitionSnapshot
) -> List[str]:
    """
    Returns a list of available slice ids
    :param element_id: str
    :param profile_snapshot: snapshot which should be scanned for slices
    :return available_slices: List of available slices for given element

    Example:
        get_available_slices("Specimen.collection.bodySite.coding") => ["sct", "icd-o-3"]
    """
    found_slices: Set[str] = set()

    for elem in profile_snapshot.snapshot.element:
        snapshot_elem_id = elem.id
        if ":" in snapshot_elem_id and element_id in get_parent_slice_id(
            snapshot_elem_id
        ):
            found_slices.add(get_slice_name(snapshot_elem_id))

    return list(found_slices)


def get_parent_element(
    profile_snapshot: StructureDefinitionSnapshot, element: ElementDefinition
) -> Optional[ElementDefinition]:
    element_id = element.id
    if not element_id:
        raise KeyError(
            f"'ElementDefinition.id' is missing in element [path='{element.path}']"
        )
    # We can determine the parent elements ID using the child elements path the FHIR spec requires the ID to align close
    # to the elements path and be hierarchical
    split = element_id.split(".")
    element_name = split[-1]
    parent_id = ".".join(split[:-1])
    # Handle slices
    if ":" in element_name:
        parent_id += "." + element_name.split(":")[0]

    return profile_snapshot.get_element_by_id(parent_id)


def get_common_ancestor_id(element_id_1: str, element_id_2: str) -> str:
    """
    Extracts the nearest common ancestor from two element IDs
    :param element_id_1: the first element ID
    :param element_id_2: the second element ID
    :return: the common ancestor ID

    Example
        id1 = "Observation.component:Systolic.short" \n
        id2 = "Observation.component:Diastolic.code.short" \n
        get_common_ancestor_id(id1, id2) => "Observation.component" \n
    """
    last_common_ancestor = []
    parts_1 = re.split(r"([.:])", element_id_1)
    parts_2 = re.split(r"([.:])", element_id_2)

    for sec_el_1, sec_el_2 in zip(parts_1, parts_2):
        if sec_el_1 != sec_el_2:
            if last_common_ancestor[-1] == "." or last_common_ancestor[-1] == ":":
                last_common_ancestor.pop()
            break
        last_common_ancestor.append(sec_el_1)
    return "".join(last_common_ancestor)


def get_common_ancestor(
    profile_snapshot: StructureDefinitionSnapshot, element_id_1: str, element_id_2: str
) -> ElementDefinition | None:
    """
    Wrapper for ``get_common_ancestor_id()`` returning the ``ElementDefinition``.
    :param profile_snapshot:
    :param element_id_1: first element ID
    :param element_id_2: second element ID
    :return: ``ElementDefinition`` of common ancestors for provided element ids
    """
    return profile_snapshot.get_element_by_id(
        get_common_ancestor_id(element_id_1, element_id_2)
    )


def is_element_slice_base(element_id: str) -> bool:
    """
    Is the specified element id a slice base

    Example:
        is_element_slice_base("Observation.component:Diastolic")  => TRUE \n
        is_element_slice_base("Observation.component:Diastolic.code")  => FALSE \n

    :param element_id:
    :return: bool
    """
    return get_parent_slice_id(element_id) == element_id


def get_parent_slice_element(
    profile_snapshot: StructureDefinitionSnapshot, element_id: str
) -> ElementDefinition:
    """
    Wrapper for ``get_parent_slice_id()`` returning the ``ElementDefinition``.
    See ``get_parent_slice_id()`` for examples
    :param profile_snapshot:
    :param element_id: the element id
    :return: ``ElementDefinition`` of parent slice for element id
    """
    parent_slice_id = get_parent_slice_id(element_id)
    return profile_snapshot.get_element_by_id(parent_slice_id)


def get_parent_slice_id(element_id: str) -> str | None:
    """
    Extracts the ID of the slice on the highest level
    :param element_id: the element id
    :return: the ID of the slice on the highest level

    Example:
        get_parent_slice_id("Observation.component:Diastolic.code.coding:sct")
        => "Observation.component:Diastolic.code.coding:sct" \n

        get_parent_slice_id("Observation.component:Diastolic.code")
        => 'Observation.component:Diastolic' \n

        get_parent_slice_id("Observation.component")
        => None \n
    """
    if ":" not in element_id:
        return None
    parent_slice_name = element_id.split(":")[-1].split(".")[0]
    parent_slice_id = element_id.rsplit(":", 1)[0] + ":" + parent_slice_name
    return parent_slice_id


def select_element_compatible_with_cql_operations(
    element: ElementDefinition, snapshot: StructureDefinitionSnapshot
) -> (ElementDefinition, Set[str]):
    """
    Uses the given element to determine - if necessary - an element which is more suitable for generating the CQL
    mapping
    :param element: ElementDefinition instance to possibly replace
    :param snapshot: StructureDefinition instance in snapshot form to which the element belongs
    :return: Alternative element and targeted type if a more compatible element could be identified or the given
             element and its type if not
    """
    ### Select element were the slicing is defined and is of type Coding
    if element.sliceName is not None and "Coding" in {t.code for t in element.type}:
        return select_element_compatible_with_cql_operations(
            get_parent_element(snapshot, element), snapshot
        )

    element_types = element.type if element.type else []
    element_type_codes = {t.code for t in element_types}
    compatible_element = element
    targeted_types = element_type_codes
    ### Coding -> CodeableConcept
    if len(element_types) == 1 and "Coding" in element_type_codes:
        # If the given element has type Coding which is part of the CodeableConcept type, the parent element is
        # returned to allow the CQL generation to use this information for query optimization
        # element_base_path = element.base.path
        if element.base and (element_base_path := element.base.path):
            targeted_type = element_base_path.split(".")[0]
            if targeted_type in {"CodeableConcept", "Reference"}:
                parent_element = get_parent_element(snapshot, element)
                if parent_element:
                    # Recurse until the actual ancestor element is reached. Slicing element definitions do not have
                    # such an element as their parent (direct ancestor)
                    compatible_element, _ = (
                        select_element_compatible_with_cql_operations(
                            parent_element, snapshot
                        )
                    )
                    targeted_types = {targeted_type}
        else:
            raise KeyError(
                f"Element [id='{element.id}'] is missing required 'ElementDefinition.base.path' "
                f"element which is required in snapshots"
            )
    return compatible_element if compatible_element else element, targeted_types
