from __future__ import annotations

import re
from functools import reduce
from importlib.resources import files
from typing import Tuple, List, Dict, Set

from fhir.resources.R4B.elementdefinition import ElementDefinition
from lxml import etree
from typing_extensions import LiteralString

import cohort_selection_ontology.resources.cql as cql_resources
from cohort_selection_ontology.core.resolvers.querying_metadata import (
    ResourceQueryingMetaDataResolver,
)
from cohort_selection_ontology.core.terminology.client import (
    CohortSelectionTerminologyClient,
)
from cohort_selection_ontology.model.mapping import (
    CQLMapping,
    CQLAttributeSearchParameter,
    CQLTimeRestrictionParameter,
    CQLTypeParameter,
    SimpleCardinality,
)
from cohort_selection_ontology.model.query_metadata import ResourceQueryingMetaData
from cohort_selection_ontology.model.ui_data import TermCode
from cohort_selection_ontology.model.ui_profile import VALUE_TYPE_OPTIONS
from common.exceptions.typing import UnsupportedTypingException
from common.model.fhir.structure_definition import (
    StructureDefinitionSnapshot,
    CQL_TYPES_TO_VALUE_TYPES,
)
from common.typing.fhir import FHIRPathlike
from common.util.log.functions import get_class_logger
from common.util.project import Project
from common.util.structure_definition.functions import (
    extract_value_type,
    extract_reference_type,
    get_element_type,
    get_element_defining_elements,
    get_element_defining_elements_with_source_snapshots,
    resolve_defining_id,
    get_parent_element,
    translate_element_to_fhir_path_expression,
    generate_attribute_key,
    get_term_code_by_id,
    is_element_in_snapshot,
    get_fixed_term_codes,
)


class CQLMappingGenerator(object):
    __allowed_time_restriction_fhir_types = {"date", "dateTime", "Period"}
    __allowed_defining_code_fhir_types = {"Coding", "CodeableConcept", "Reference"}
    __allowed_defining_value_fhir_types = {
        "code",
        "date",
        "Coding",
        "CodeableConcept",
        "Quantity",
    }
    __logger = get_class_logger("CQLMappingGenerator")

    def __init__(
        self,
        project: Project,
        querying_meta_data_resolver: ResourceQueryingMetaDataResolver,
    ):
        """
        :param project: Project to operate on
        :param querying_meta_data_resolver: resolves the for the query relevant metadata for a given FHIR profile
        snapshot
        """
        self.__project = project
        self.__client = CohortSelectionTerminologyClient(self.__project)
        self.querying_meta_data_resolver = querying_meta_data_resolver
        self.primary_paths = self.get_primary_paths_per_resource()
        self.generated_mappings = []

    @staticmethod
    def get_primary_paths_per_resource() -> Dict[str, str]:
        primary_paths = {}
        with (
            files(cql_resources)
            .joinpath("elm-modelinfo.xml")
            .open(mode="r", encoding="utf-8") as f
        ):
            root = etree.parse(f)
            namespace_map = {"elm": "urn:hl7-org:elm-modelinfo:r1"}
            for type_info in root.xpath(".//elm:typeInfo", namespaces=namespace_map):
                resource_type = type_info.get("name")
                primary_path = type_info.get("primaryCodePath")
                if resource_type and primary_path:
                    primary_paths[resource_type] = primary_path
        return primary_paths

    @classmethod
    def __select_element_compatible_with_cql_operations(
        cls, element: ElementDefinition, snapshot: StructureDefinitionSnapshot
    ) -> (ElementDefinition, Set[str]):
        """
        Uses the given element to determine - if necessary - an element which is more suitable for generating the CQL
        mapping
        :param element: ElementDefinition instance to possibly replace
        :param snapshot: StructureDefinition instance in snapshot form to which the element belongs
        :return: Alternative element and targeted type if a more compatible element could be identified or the given
                 element and its type if not
        """
        ### Select element were the slicing is defined
        if element.sliceName is not None:
            return cls.__select_element_compatible_with_cql_operations(
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
                            cls.__select_element_compatible_with_cql_operations(
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

    def generate_mapping(
        self, module_name: str
    ) -> Tuple[Dict[Tuple[TermCode, TermCode], str], Dict[str, CQLMapping]]:
        """
        Generates the CQL mappings for the given module
        :param module_name: Name of the module to generate the mapping for
        :return: normalized term code CQL mapping
        """
        snapshot_dir = self.__project.input.cso.mkdirs(
            "modules", module_name, "differential", "package"
        )
        full_context_term_code_cql_mapping_name_mapping: (
            Dict[Tuple[TermCode, TermCode]] | dict
        ) = {}
        full_cql_mapping_name_cql_mapping: Dict[str, CQLMapping] | dict = {}
        files = [
            file for file in snapshot_dir.rglob("*-snapshot.json") if file.is_file()
        ]
        for file in files:
            with open(file, mode="r", encoding="utf8") as f:
                snapshot = StructureDefinitionSnapshot.model_validate_json(f.read())
                context_tc_to_mapping_name, cql_mapping_name_to_mapping = (
                    self.generate_normalized_term_code_cql_mapping(
                        snapshot, module_name
                    )
                )
                full_context_term_code_cql_mapping_name_mapping.update(
                    context_tc_to_mapping_name
                )
                full_cql_mapping_name_cql_mapping.update(cql_mapping_name_to_mapping)
        return (
            full_context_term_code_cql_mapping_name_mapping,
            full_cql_mapping_name_cql_mapping,
        )

    def generate_normalized_term_code_cql_mapping(
        self, profile_snapshot: StructureDefinitionSnapshot, module_name: str
    ) -> Tuple[Dict[Tuple[TermCode, TermCode], str], Dict[str, CQLMapping]]:
        """
        Generates the normalized term code to CQL mapping for the given FHIR profile snapshot
        :param profile_snapshot: FHIR profile snapshot
        :param module_name: name of the module the profile belongs to
        :return: normalized term code to CQL mapping
        """
        modules_dir = self.__project.input.cso / "modules"
        querying_meta_data: List[ResourceQueryingMetaData] = (
            self.querying_meta_data_resolver.get_query_meta_data(
                profile_snapshot, module_name
            )
        )
        term_code_mapping_name_mapping: Dict[Tuple[TermCode, TermCode], str] | dict = {}
        mapping_name_cql_mapping: Dict[str, CQLMapping] | dict = {}
        for querying_meta_data_entry in querying_meta_data:
            if querying_meta_data_entry.name not in self.generated_mappings:
                cql_mapping = self.generate_cql_mapping(
                    profile_snapshot, querying_meta_data_entry, module_name
                )
                self.generated_mappings.append(querying_meta_data_entry.name)
                mapping_name = cql_mapping.name
                mapping_name_cql_mapping[mapping_name] = cql_mapping
            else:
                mapping_name = querying_meta_data_entry.name
            # The logic to get the term_codes here always has to be identical with the mapping
            term_codes = (
                querying_meta_data_entry.term_codes
                if querying_meta_data_entry.term_codes
                else get_term_code_by_id(
                    profile_snapshot,
                    querying_meta_data_entry.term_code_defining_id,
                    modules_dir,
                    module_name,
                    self.__client,
                )
            )
            primary_keys = [
                (querying_meta_data_entry.context, term_code)
                for term_code in term_codes
            ]
            mapping_names = [mapping_name] * len(primary_keys)
            table = dict(zip(primary_keys, mapping_names))
            term_code_mapping_name_mapping.update(table)
        return term_code_mapping_name_mapping, mapping_name_cql_mapping

    def is_primary_path(self, resource_type, fhir_path: str) -> bool:
        """
        Checks if the given fhir path is not a primary path according to the cql elm modelinfo
        :param resource_type: resource type
        :param fhir_path: fhir path
        :return: true if the given fhir path is not a primary path, false otherwise
        """
        if resource_type in self.primary_paths:
            return self.sub_path_equals(self.primary_paths[resource_type], fhir_path)
        return False

    def generate_cql_mapping(
        self,
        profile_snapshot: StructureDefinitionSnapshot,
        querying_meta_data: ResourceQueryingMetaData,
        module_dir_name: str,
    ) -> CQLMapping:
        """
        Generates the CQL mapping for the given FHIR profile snapshot and querying metadata entry
        :param profile_snapshot: FHIR profile snapshot
        :param querying_meta_data: querying metadata entry
        :param module_dir_name: Name of the module where the QueryingMetadata file and profiles snapshot are located
        :return: CQL mapping
        """
        modules_dir = self.__project.input.cso.mkdirs("modules")
        cql_mapping = CQLMapping(querying_meta_data.name)
        cql_mapping.resourceType = querying_meta_data.resource_type
        if tc_defining_id := querying_meta_data.term_code_defining_id:
            # TODO: Temporary fix by filtering out CDS Medication querying metadata since they receive special
            #       treatment in sq2cql
            if (
                not self.is_primary_path(
                    querying_meta_data.resource_type,
                    self.remove_fhir_resource_type(tc_defining_id),
                )
                and not querying_meta_data.module.code == "mii-cds-medikation"
            ):
                if is_element_in_snapshot(profile_snapshot, tc_defining_id):
                    element = profile_snapshot.get_element_by_id(tc_defining_id)
                else:
                    element = get_element_defining_elements(
                        profile_snapshot, tc_defining_id, module_dir_name, modules_dir
                    )[-1]
                element, types = self.__select_element_compatible_with_cql_operations(
                    element, profile_snapshot
                )
                element_id = element.id
                if not types:
                    raise KeyError(
                        "ElementDefinition.type cannot be empty as at least one type is required for CQL "
                        f"translation [profile='{profile_snapshot.name}, "
                        f"element_id='{element_id}']"
                    )
                types = self.__allowed_defining_code_fhir_types.intersection(types)
                if len(types) == 0:
                    raise UnsupportedTypingException(
                        f"Supported type range of element '{element_id}' has no "
                        f"overlap with the expected type range of a time restricting "
                        f"element in the CQL mapping [present={types}, "
                        f"allowed={self.__allowed_defining_code_fhir_types}]"
                    )
                term_code_fhir_path = (
                    self.translate_term_element_id_to_fhir_path_expression(
                        element_id, profile_snapshot, module_dir_name
                    )
                )
                card = CQLMappingGenerator.__aggregate_cardinality_using_element(
                    element, profile_snapshot
                )
                cql_mapping.termCode = CQLTypeParameter(
                    path=term_code_fhir_path, types=types, cardinality=card
                )

        if val_defining_id := querying_meta_data.value_defining_id:
            element = profile_snapshot.get_element_by_id(val_defining_id)
            element, types = self.__select_element_compatible_with_cql_operations(
                element, profile_snapshot
            )
            element_id = element.id
            if not types:
                raise KeyError(
                    "ElementDefinition.type cannot be empty as at least one type is required for CQL "
                    f"translation [profile='{profile_snapshot.name}, "
                    f"element_id='{element_id}']"
                )
            types = self.__allowed_defining_value_fhir_types.intersection(types)
            if len(types) == 0:
                raise UnsupportedTypingException(
                    f"Supported type range of element '{element_id}' has no "
                    f"overlap with the expected type range of a value element in the CQL "
                    f"mapping [present={types}, "
                    f"allowed={self.__allowed_defining_value_fhir_types}]"
                )
            value_fhir_path = self.translate_element_id_to_fhir_path_expressions(
                element_id, profile_snapshot, module_dir_name
            )
            card = CQLMappingGenerator.__aggregate_cardinality_using_element(
                element, profile_snapshot
            )
            cql_mapping.value = CQLTypeParameter(
                path=value_fhir_path, types=types, cardinality=card
            )

        if time_defining_id := querying_meta_data.time_restriction_defining_id:
            element = profile_snapshot.get_element_by_id(time_defining_id)
            element, types = self.__select_element_compatible_with_cql_operations(
                element, profile_snapshot
            )
            element_id = element.id
            if not types:
                raise KeyError(
                    "ElementDefinition.type cannot be empty as at least one type is required for CQL "
                    f"translation [profile='{profile_snapshot.name}, "
                    f"element_id='{element_id}']"
                )
            types = self.__allowed_time_restriction_fhir_types.intersection(types)
            if len(types) == 0:
                raise UnsupportedTypingException(
                    f"Supported type range of element '{element_id}' has no "
                    f"overlap with the expected type range of a time restricting element "
                    f"in the CQL mapping [present={types}, "
                    f"allowed={self.__allowed_time_restriction_fhir_types}]"
                )
            fhir_path = (
                self.translate_element_id_to_fhir_path_expressions_time_restriction(
                    element_id, profile_snapshot, module_dir_name
                )
            )

            card = CQLMappingGenerator.__aggregate_cardinality_using_element(
                element, profile_snapshot
            )
            cql_mapping.timeRestriction = CQLTimeRestrictionParameter(
                types=types, cardinality=card, path=FHIRPathlike(fhir_path)
            )
        for (
            attr_defining_id,
            attr_attributes,
        ) in querying_meta_data.attribute_defining_id_type_map.items():
            attr_type = attr_attributes.type
            self.set_attribute_search_param(
                attr_defining_id,
                cql_mapping,
                attr_type,
                profile_snapshot,
                module_dir_name,
            )

        return cql_mapping

    def set_attribute_search_param(
        self,
        attr_defining_id: str,
        cql_mapping,
        attr_type: str,
        profile_snapshot: StructureDefinitionSnapshot,
        module_dir_name: str,
    ):
        attribute_key = generate_attribute_key(attr_defining_id)
        attribute_type = (
            attr_type
            if attr_type
            else self.get_attribute_type(
                profile_snapshot, attr_defining_id, module_dir_name
            )
        )
        # FIXME:
        # This is a hack to change the attribute_type to upper-case Reference to match the FHIR Type while
        # Fhir Search does not use the FHIR types...
        attribute_type = "Reference" if attr_type == "reference" else attribute_type
        attribute_types = None
        if attribute_type == "composite":
            # element = self.parser.get_element_from_snapshot(profile_snapshot, attr_defining_id)
            # element, _ = self.__select_element_compatible_with_cql_operations(element, profile_snapshot)

            attribute_fhir_path = (
                self.translate_composite_attribute_to_fhir_path_expression(
                    attr_defining_id, profile_snapshot, module_dir_name
                )
            )
            attribute_key = self.get_composite_code(
                attr_defining_id, profile_snapshot, module_dir_name
            )
            attribute_type = self.get_composite_attribute_type(
                attr_defining_id, profile_snapshot, module_dir_name
            )
        else:
            if attribute_type != "Reference":
                element = profile_snapshot.get_element_by_id(attr_defining_id)
                element, attribute_types = (
                    self.__select_element_compatible_with_cql_operations(
                        element, profile_snapshot
                    )
                )
                attr_defining_id = element.id
            attribute_fhir_path = (
                self.translate_term_element_id_to_fhir_path_expression(
                    attr_defining_id, profile_snapshot, module_dir_name
                )
            )
        attribute_types = attribute_types if attribute_types else {attribute_type}
        cards = self.__aggregate_cardinality_using_element_id(
            attr_defining_id, profile_snapshot, module_dir_name
        )
        attribute = CQLAttributeSearchParameter(
            types=attribute_types,
            key=attribute_key,
            path=attribute_fhir_path,
            cardinality=cards,
        )
        if attribute_type == "Reference":
            attribute.referenceTargetType = self.get_reference_type(
                profile_snapshot, attr_defining_id, module_dir_name
            )

        cql_mapping.add_attribute(attribute)

    def get_composite_code(
        self, attribute, profile_snapshot: StructureDefinitionSnapshot, module_dir_name
    ):
        modules_dir = self.__project.input.cso.mkdirs("modules")
        attribute_parsed = get_element_defining_elements(
            profile_snapshot, attribute, module_dir_name, modules_dir
        )
        if len(attribute_parsed) != 2:
            raise ValueError(
                "Composite search parameters must have exactly two elements"
            )
        where_clause_element = attribute_parsed[-1]
        return get_fixed_term_codes(
            profile_snapshot,
            where_clause_element,
            modules_dir,
            module_dir_name,
            self.__client,
        )[0]

    def get_composite_attribute_type(
        self,
        attribute: str,
        profile_snapshot: StructureDefinitionSnapshot,
        module_dir_name: str,
    ):
        modules_dir = self.__project.input.cso.mkdirs("modules")
        attribute_parsed = get_element_defining_elements(
            profile_snapshot, attribute, module_dir_name, modules_dir
        )
        if len(attribute_parsed) != 2:
            raise ValueError(
                "Composite search parameters must have exactly two elements"
            )
        value_element = attribute_parsed[0]
        return get_element_type(value_element)

    @staticmethod
    def find_balanced_parentheses(s):
        stack = []
        start = 0
        for i, char in enumerate(s):
            if char == "(":
                if not stack:
                    start = i
                stack.append(char)
            elif char == ")":
                stack.pop()
                if not stack:
                    return s[start : i + 1]
        return ""

    def extract_where_clause(self, updated_attribute_path):
        where_clause_match = re.search(r"\.where\(", updated_attribute_path)
        if where_clause_match:
            remaining_string = updated_attribute_path[where_clause_match.end() - 1 :]
            where_clause = self.find_balanced_parentheses(remaining_string)
            prefix = updated_attribute_path[
                : where_clause_match.end() - 1 + len(where_clause)
            ].split(".", 1)[-1]
            return where_clause, prefix
        else:
            return "", ""

    def translate_composite_attribute_to_fhir_path_expression(
        self,
        attribute: str,
        profile_snapshot: StructureDefinitionSnapshot,
        module_dir_name: str,
    ) -> str:
        """

        :param attribute: id of the attribute
        :param profile_snapshot: StructureDefinitionSnapshot
        :param module_dir_name: name of the module

        :return: FHIR search parameter

        """
        modules_dir = self.__project.input.cso.mkdirs("modules")
        elements = get_element_defining_elements(
            profile_snapshot, attribute, module_dir_name, modules_dir
        )
        # first seems to be the value every time
        elements[0], _ = self.__select_element_compatible_with_cql_operations(
            elements[0], profile_snapshot
        )

        expressions = translate_element_to_fhir_path_expression(
            profile_snapshot, elements, is_composite=True
        )
        value_clause = expressions[0]
        composite_code = self.get_composite_code(
            attribute, profile_snapshot, module_dir_name
        )
        updated_where_clause = f".where(code.coding.exists(system = '{composite_code.system}' and code = '{composite_code.code}'))"
        # replace original where clause in attribute using string manipulation and regex
        updated_attribute_path = re.sub(
            r"\.where\([^)]*\)", f"{updated_where_clause}", attribute
        )

        where_clause, prefix = self.extract_where_clause(updated_attribute_path)

        # Find the common prefix dynamically
        common_prefix_length = 0
        for i in range(min(len(updated_attribute_path), len(value_clause))):
            if updated_attribute_path[i] == value_clause[i]:
                common_prefix_length = i + 1
            else:
                break

        common_prefix = updated_attribute_path[:common_prefix_length]

        # Remove the common prefix from expr2 to get the uncommon part
        uncommon_expr2 = value_clause[len(common_prefix) :]

        # Construct the new expression
        full_composite_path = (
            prefix + "." + uncommon_expr2
            if uncommon_expr2[0] != "."
            else prefix + uncommon_expr2
        )
        return full_composite_path

    def translate_term_element_id_to_fhir_path_expression(
        self,
        element_id: str,
        profile_snapshot: StructureDefinitionSnapshot,
        module_dir_name: str,
    ) -> str:
        modules_dir = self.__project.input.cso.mkdirs("modules")
        elements = get_element_defining_elements(
            profile_snapshot, element_id, module_dir_name, modules_dir
        )
        # TODO: Revisit and evaluate if this really the way to go.
        for element in elements:
            element, types = self.__select_element_compatible_with_cql_operations(
                element, profile_snapshot
            )
            for element_type in types:
                if element_type == "Reference":
                    return (
                        self.get_cql_optimized_path_expression(
                            translate_element_to_fhir_path_expression(
                                profile_snapshot, elements
                            )[0]
                        )
                        + ".reference"
                    )
        return self.translate_element_id_to_fhir_path_expressions(
            element_id, profile_snapshot, module_dir_name
        )

    def translate_element_id_to_fhir_path_expressions(
        self,
        element_id: str,
        profile_snapshot: StructureDefinitionSnapshot,
        module_dir_name: str,
    ) -> str:
        """
        Translates an element id to a fhir search parameter
        :param element_id: element id
        :param profile_snapshot: FHIR profile snapshot containing the element id
        :param module_dir_name: Name of the module directory
        :return: fhir search parameter
        """
        modules_dir = self.__project.input.cso.mkdirs("modules")
        elements = get_element_defining_elements(
            profile_snapshot, element_id, module_dir_name, modules_dir
        )
        expressions = translate_element_to_fhir_path_expression(
            profile_snapshot, elements
        )
        return ".".join(
            [
                self.get_cql_optimized_path_expression(expression)
                for expression in expressions
            ]
        )

    def translate_element_id_to_fhir_path_expressions_time_restriction(
        self,
        element_id,
        profile_snapshot: StructureDefinitionSnapshot,
        module_dir_name: str,
    ) -> str:
        """
        Translates an element id to a fhir search parameter
        :param element_id: element id
        :param profile_snapshot: FHIR profile snapshot containing the element id
        :param module_dir_name: Name of the module directory
        :return: fhir search parameter
        """
        modules_dir = self.__project.input.cso.mkdirs("modules")
        elements = get_element_defining_elements(
            profile_snapshot, element_id, module_dir_name, modules_dir
        )
        expressions = translate_element_to_fhir_path_expression(
            profile_snapshot, elements
        )
        return ".".join(
            [
                self.get_cql_path_time_restriction(expression)
                for expression in expressions
            ]
        )

    def get_cql_path_time_restriction(self, path_expression: str) -> str:
        cql_path_time_expression = self.remove_cast(path_expression)
        return cql_path_time_expression

    @staticmethod
    def remove_cast(path_expression: str) -> str:
        """
        Removes the cast from the path expression
        :param path_expression: path expression
        :return: path expression without cast
        """
        # Discard everything before the first dot
        _, _, path_after_dot = path_expression.partition(".")

        # If there's no content after the first dot, return the original path_expression
        if not path_after_dot:
            return path_expression
        return path_after_dot.split(" as ")[0]

    @staticmethod
    def remove_fhir_resource_type(path_expression: FHIRPathlike) -> FHIRPathlike:
        """
        If a given FHIRPath expression starts with a FHIR resource type, remove this initial node and return the pruned
        expression
        :param path_expression: FHIRPath expression to prune
        :return: Pruned FHIRPath expression without an initial FHIR resource type node
        """
        match = re.match(
            r"^\(*(?P<capture_str>[A-Z][a-zA-Z0-9]*(?P<closing_prnths>\)*)\.)",
            path_expression,
        )
        if match:
            # Account for wrapping parentheses
            capture_str_start = match.start("capture_str")
            capture_str_end = match.end("capture_str")
            num_closing_parentheses = len(match.group("closing_prnths"))
            return (
                path_expression[: capture_str_start - num_closing_parentheses]
                + path_expression[capture_str_end:]
            )
        else:
            return path_expression

    def get_cql_optimized_path_expression(self, path_expression: FHIRPathlike) -> str:
        # TODO: Remove this method once the new path expressions are compatible with the cql implementation?
        """
        Translates a path expression to a cql optimized path expression
        :param path_expression: path expression
        :return: cql optimized path expression
        """
        cql_path_expression = self.convert_as_to_dot_as(path_expression)
        cql_path_expression = self.__clean_parentheses(cql_path_expression)
        cql_path_expression = self.add_first_after_extension_where_expression(
            cql_path_expression
        )
        cql_path_expression = self.remove_fhir_resource_type(cql_path_expression)
        return cql_path_expression

    @staticmethod
    def __clean_parentheses(path_expression: FHIRPathlike):
        opening_cnt = path_expression.count("(")
        closing_cnt = path_expression.count(")")
        diff = closing_cnt - opening_cnt
        if diff < 0:
            char = "("
            split = path_expression.split(char)
            idx = abs(diff) + 1
            return "".join(split[:idx]) + char.join(split[idx:])
        elif diff > 0:
            char = ")"
            split = path_expression.split(char)
            idx = opening_cnt + 1
            return char.join(split[:idx]) + "".join(split[idx:])
        else:
            return path_expression

    @staticmethod
    def convert_as_to_dot_as(path_expression: FHIRPathlike) -> FHIRPathlike:
        """
        Converts the " as " pattern to ".as("
        :param path_expression: path expression
        :return: converted path expression
        """
        # Discard everything before the first dot
        _, _, path_after_dot = path_expression.partition(".")

        # If there's no content after the first dot, return the original path_expression
        if not path_after_dot:
            return path_expression

        # Partition based on " as " to handle conversion
        before_as, _, remainder = path_after_dot.partition(" as ")

        # If there's no " as " pattern, just return the path after the first dot
        if not remainder:
            return path_after_dot

        after_as, _, rest = remainder.partition(".")
        transformed = f"{before_as}.as({after_as})"

        # Append the rest of the path if there's more after "as "
        if rest:
            transformed += f".{rest}"
        return transformed

    def get_attribute_type(
        self,
        profile_snapshot: StructureDefinitionSnapshot,
        attribute_id: str,
        module_dir_name: str,
    ) -> VALUE_TYPE_OPTIONS:
        """
        Returns the type of the given attribute
        :param profile_snapshot: FHIR profile snapshot
        :param attribute_id: attribute id
        :param module_dir_name: Name of the module directory
        :return: attribute type
        """
        modules_dir = self.__project.input.cso.mkdirs("modules")
        # remove cast expression as it is irrelevant for the type
        if " as ValueSet" in attribute_id:
            attribute_id = attribute_id.replace(" as ValueSet", "")
        attribute_element = resolve_defining_id(
            profile_snapshot, attribute_id, modules_dir, module_dir_name
        )

        attribute_type = extract_value_type(attribute_element, profile_snapshot.name)

        return CQL_TYPES_TO_VALUE_TYPES.get(attribute_type)

    def get_reference_type(
        self,
        profile_snapshot: StructureDefinitionSnapshot,
        attr_defining_id: str,
        module_dir_name: str,
    ):
        """
        Returns the type of the referenced attribute
        :param profile_snapshot: FHIR profile snapshot
        :param attr_defining_id: attribute id
        :param module_dir_name: Name of the module directory
        :return: attribute type
        """
        modules_dir = self.__project.input.cso.mkdirs("modules")
        elements = get_element_defining_elements(
            profile_snapshot, attr_defining_id, module_dir_name, modules_dir
        )
        for element in elements:
            for element_type in element.type:
                if element_type.code == "Reference":
                    return extract_reference_type(
                        element_type, modules_dir, profile_snapshot.name
                    )

    @staticmethod
    def add_first_after_extension_where_expression(cql_path_expression):
        """
        Adds the first() after an extension where expression
        :param cql_path_expression: cql path expression
        :return: cql path expression with first() added
        """
        # TODO: Find a better rule than contains extension.where(...) to apply the first() rule
        # Use regex to find the pattern "extension.where(...)"
        match = re.search(r"(.*extension\.where\([^)]+\))(.+)", cql_path_expression)

        if match:
            before_extension = match.group(1)
            after_extension = match.group(2)
            return f"{before_extension}.first(){after_extension}"

        # If no match is found, return the original string
        return cql_path_expression

    @staticmethod
    def sub_path_equals(sub_path, path):
        """
        Checks if the given sub_path equals the given path or any truncated version of it.
        :param sub_path: sub path
        :param path: path
        :return: true if the given sub_path equals the given path or any truncated version, false otherwise
        """
        if sub_path == path:
            return True

        path_elements = path.split(".")
        # Iterate over the path elements from the end and check if the current truncated path matches the sub_path.
        for i in range(len(path_elements), 0, -1):
            current_path = ".".join(path_elements[:i])
            if sub_path == current_path:
                return True
        return False

    @staticmethod
    def __aggregate_cardinality_using_element(
        element: ElementDefinition,
        snapshot: StructureDefinitionSnapshot,
        card_type: LiteralString["min", "max"] = "max",
    ) -> SimpleCardinality:
        """
        Aggregates the cardinality of an element along its path by collecting the cardinalities of itself and the parent
        elements and combining them to obtain the aggregated value as viewed from the root of the FHIR Resource
        :param element: Element to calculate the aggregated cardinality for
        :param snapshot: Snapshot of profile defining the element
        :param card_type: Type of cardinality to aggregate (either 'mix' or 'max')
        :return: Aggregated cardinality stating whether an element can occur multiple times or not
        """
        opt_element, _ = (
            CQLMappingGenerator.__select_element_compatible_with_cql_operations(
                element, snapshot
            )
        )
        card = SimpleCardinality.from_fhir_cardinality(getattr(opt_element, card_type))
        opt_element_path = opt_element.path
        is_root = opt_element_path.count(".") == 0
        match card:
            case SimpleCardinality.MANY:
                # End recursion since with the current enum members reaching this state leads to no further changes. An
                # exception will be made if the element is a root element since at that level we always assume singleton
                # occurrence (e.g. for paths like '<resource-type>')
                return SimpleCardinality.SINGLE if is_root else card
            case _:
                parent_element = get_parent_element(snapshot, opt_element)
                if opt_element_path == parent_element.id:
                    opt_parent_el, _ = (
                        CQLMappingGenerator.__select_element_compatible_with_cql_operations(
                            parent_element, snapshot
                        )
                    )
                    grand_parent_el = get_parent_element(snapshot, opt_parent_el)
                    if grand_parent_el is None and opt_element_path.count(".") == 0:
                        return SimpleCardinality.SINGLE
                    # skip one parent
                    return (
                        CQLMappingGenerator.__aggregate_cardinality_using_element(
                            grand_parent_el, snapshot, card_type
                        )
                        * card
                    )

                match parent_element:
                    case None:
                        if not is_root:
                            raise Exception(
                                f"No parent could be identified for element '{opt_element.id}' with "
                                f"non-root path '{opt_element_path}'"
                            )
                        else:
                            # The root element is always assumed to have `SINGLE` cardinality
                            return SimpleCardinality.SINGLE
                    case parent_element:
                        return (
                            CQLMappingGenerator.__aggregate_cardinality_using_element(
                                parent_element, snapshot, card_type
                            )
                            * card
                        )

    def __aggregate_cardinality_using_element_id(
        self,
        element_defining_id: str,
        profile_snapshot: StructureDefinitionSnapshot,
        module_dir_name: str,
    ) -> SimpleCardinality:
        modules_dir = self.__project.input.cso.mkdirs("modules")
        element_results = get_element_defining_elements_with_source_snapshots(
            profile_snapshot, element_defining_id, module_dir_name, modules_dir
        )
        if element_results is None or len(element_results) == 0:
            raise Exception(
                f"Aggregated cardinality could not be determined: No defining elements could be "
                f"identified using element defining ID '{element_defining_id}' and snapshot "
                f"'{profile_snapshot.id}'"
            )
        else:
            cards = []
            for result in element_results:
                opt_element, _ = self.__select_element_compatible_with_cql_operations(
                    result.element, result.profile_snapshot
                )
                cards.append(
                    self.__aggregate_cardinality_using_element(
                        opt_element, result.profile_snapshot
                    )
                )
            return reduce(lambda a, b: a * b, cards)
