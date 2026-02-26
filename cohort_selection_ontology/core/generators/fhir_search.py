import collections
import functools
from typing import Dict, Tuple, List, OrderedDict

from cohort_selection_ontology.core.resolvers.querying_metadata import (
    ResourceQueryingMetaDataResolver,
)
from cohort_selection_ontology.core.resolvers.search_parameter import (
    SearchParameterResolver,
)
from cohort_selection_ontology.core.terminology.client import (
    CohortSelectionTerminologyClient,
)
from cohort_selection_ontology.model.mapping import FhirMapping
from cohort_selection_ontology.model.query_metadata import ResourceQueryingMetaData
from cohort_selection_ontology.model.ui_data import TermCode
from cohort_selection_ontology.model.ui_profile import VALUE_TYPE_OPTIONS
from common.exceptions import NotFoundError
from common.model.fhir.structure_definition import (
    StructureDefinitionSnapshot,
    FHIR_TYPES_TO_VALUE_TYPES,
)
from common.util.log.functions import get_class_logger
from common.util.project import Project
from common.util.structure_definition.functions import (
    extract_value_type,
    get_element_defining_elements,
    resolve_defining_id,
    translate_element_to_fhir_path_expression,
    generate_attribute_key,
    get_term_code_by_id,
)

SUPPORTED_TYPES = [
    "date",
    "dateTime",
    "decimal",
    "integer",
    "Age",
    "CodeableConcept",
    "Coding",
    "Quantity",
    "Reference",
    "code",
    "Extension",
]


class InvalidElementTypeException(Exception):
    pass


class FHIRSearchMappingGenerator(object):
    """
    This class is responsible for generating FHIR mappings for a given FHIR profile.
    """

    __logger = get_class_logger("FHIRSearchMappingGenerator")

    def __init__(
        self,
        project: Project,
        querying_meta_data_resolver: ResourceQueryingMetaDataResolver,
        fhir_search_mapping_resolver: SearchParameterResolver,
    ):
        """
        :param project: Project to operate on
        :param querying_meta_data_resolver: resolves the for the query relevant metadata for a given FHIR profile
        snapshot
        """
        self.__project = project
        self.__client = CohortSelectionTerminologyClient(self.__project)
        self.querying_meta_data_resolver = querying_meta_data_resolver
        self.generated_mappings = []
        self.fhir_search_mapping_resolver = fhir_search_mapping_resolver
        self.__modules_dir = self.__project.input.cso.mkdirs("modules")

    def generate_mapping(
        self, module_name: str
    ) -> Tuple[Dict[Tuple[TermCode, TermCode], str], Dict[str, FhirMapping]]:
        """
        Generates the FHIR search mappings for the given FHIR dataset directory
        :param module_name: Name of the module
        :return: normalized term code FHIR search mapping
        """
        snapshot_dir = self.__project.input.cso.mkdirs(
            "modules", module_name, "differential", "package"
        )
        full_context_term_code_fhir_search_mapping_name_mapping: Dict[
            Tuple[TermCode, TermCode]
        ] = {}
        full_fhir_search_mapping_name_fhir_search_mapping: Dict[str, FhirMapping] = {}
        files = [
            file for file in snapshot_dir.rglob("*-snapshot.json") if file.is_file()
        ]
        for file in files:
            with open(file, mode="r", encoding="utf8") as f:
                snapshot = StructureDefinitionSnapshot.model_validate_json(f.read())
                context_tc_to_mapping_name, fhir_search_mapping_name_to_mapping = (
                    self.generate_normalized_term_code_fhir_search_mapping(
                        snapshot, module_name
                    )
                )
                full_context_term_code_fhir_search_mapping_name_mapping.update(
                    context_tc_to_mapping_name
                )
                full_fhir_search_mapping_name_fhir_search_mapping.update(
                    fhir_search_mapping_name_to_mapping
                )
        return (
            full_context_term_code_fhir_search_mapping_name_mapping,
            full_fhir_search_mapping_name_fhir_search_mapping,
        )

    def resolve_fhir_search_parameter(
        self,
        element_id: str,
        profile_snapshot: StructureDefinitionSnapshot,
        module_dir_name: str,
        attribute_type: VALUE_TYPE_OPTIONS = None,
    ) -> OrderedDict[str, dict]:
        """
        Based on the element id, this method resolves the FHIR search parameter for the given FHIR Resource attribute
        :param element_id: element id that defines the of the FHIR Resource attribute
        :param profile_snapshot: FHIR profile snapshot that contains the element id
        :param module_dir_name: Name of the module directory
        :param attribute_type: type of the FHIR Resource attribute
        :return: FHIR search parameter
        """
        fhir_path_expressions = self.translate_element_id_to_fhir_path_expressions(
            element_id, profile_snapshot, module_dir_name
        )
        try:
            search_parameters: OrderedDict[str, dict] = (
                self.fhir_search_mapping_resolver.find_search_parameter(
                    fhir_path_expressions
                )
            )
            if attribute_type == "composite":
                return self._resolve_composite_search_parameter(search_parameters)
            return search_parameters
        except NotFoundError as err:
            location_hint = self.__project.input.cso.mkdirs(
                "modules", module_dir_name, "search_parameters"
            )
            self.__logger.error(
                f"Could not find search parameter for expressions {fhir_path_expressions}. If standard "
                f"search parameters do not suffice, consider adding a custom search parameter "
                f"definition to {location_hint}"
            )
            self.__logger.debug("[Reason]", exc_info=err)
            return collections.OrderedDict.fromkeys([])

    def _resolve_composite_search_parameter(self, search_parameters: OrderedDict[str, dict]):
        if len(search_parameters) != 2:
            raise InvalidElementTypeException(
                "Composite search parameter must have 2 elements"
            )
        search_parameter = (
            self.fhir_search_mapping_resolver.find_composite_search_parameter(
                search_parameters
            )
        )
        return search_parameter

    def chain_search_parameters(self, search_parameters: OrderedDict[str, dict]) -> str:
        self.validate_chainable(search_parameters.values())
        return ".".join(
            [
                search_parameter.get("code")
                for search_parameter in search_parameters.values()
            ]
        )

    def generate_normalized_term_code_fhir_search_mapping(
        self, profile_snapshot: StructureDefinitionSnapshot, module_name: str
    ) -> Tuple[Dict[Tuple[TermCode, TermCode], str], Dict[str, FhirMapping]]:
        """
        Generates the normalized term code FHIR search mapping for the given FHIR profile snapshot in the specified
        context
        :param profile_snapshot: FHIR profile snapshot
        :param module_name: name of the module the profile belongs to
        :return: normalized term code FHIR search mapping
        """
        querying_meta_data: List[ResourceQueryingMetaData] = (
            self.querying_meta_data_resolver.get_query_meta_data(
                profile_snapshot, module_name
            )
        )
        term_code_mapping_name_mapping = {}
        mapping_name_fhir_search_mapping = {}
        for querying_meta_data_entry in querying_meta_data:
            if querying_meta_data_entry.name not in self.generated_mappings:
                fhir_mapping = self.generate_fhir_search_mapping(
                    profile_snapshot, querying_meta_data_entry, module_name
                )
                self.generated_mappings.append(querying_meta_data_entry.name)
                mapping_name = fhir_mapping.name
                mapping_name_fhir_search_mapping[mapping_name] = fhir_mapping
            else:
                mapping_name = querying_meta_data_entry.name
            # The logic to get the term_codes here always has to be identical with the mapping Generators!
            term_codes = (
                querying_meta_data_entry.term_codes
                if querying_meta_data_entry.term_codes
                else get_term_code_by_id(
                    profile_snapshot,
                    querying_meta_data_entry.term_code_defining_id,
                    self.__modules_dir,
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
        return term_code_mapping_name_mapping, mapping_name_fhir_search_mapping

    def generate_fhir_search_mapping(
        self,
        profile_snapshot: StructureDefinitionSnapshot,
        querying_meta_data: ResourceQueryingMetaData,
        module_dir_name: str,
    ) -> FhirMapping:
        """
        Generates the FHIR search mapping for the given FHIR profile snapshot and querying metadata
        :param profile_snapshot: FHIR profile snapshot
        :param querying_meta_data: querying metadata
        :param module_dir_name: Name of the module directory
        :return: FHIR search mapping
        """
        fhir_mapping = FhirMapping(name=querying_meta_data.name)
        fhir_mapping.fhirResourceType = querying_meta_data.resource_type
        if querying_meta_data.term_code_defining_id:
            self.set_term_code_search_param(
                fhir_mapping, profile_snapshot, querying_meta_data, module_dir_name
            )
        if querying_meta_data.value_defining_id:
            self.set_value_search_param(
                fhir_mapping, profile_snapshot, querying_meta_data, module_dir_name
            )
        if querying_meta_data.time_restriction_defining_id:
            fhir_mapping.timeRestrictionParameter = self._handle_search_parameter(
                "date",
                self.resolve_fhir_search_parameter(
                    querying_meta_data.time_restriction_defining_id,
                    profile_snapshot,
                    "date",
                ),
            )
        for (
            attribute,
            predefined_attributes,
        ) in querying_meta_data.attribute_defining_id_type_map.items():
            predefined_type = predefined_attributes.type
            self.set_attribute_search_param(
                attribute,
                fhir_mapping,
                predefined_type,
                profile_snapshot,
                module_dir_name,
            )
        return fhir_mapping

    def _handle_search_parameter(self, param_type, search_params):
        """
        Handle search parameters based on its type.

        Args:
            param_type (str): Type of the parameter ("reference" or other types).
            search_params (dict): Resolved search parameters.

        Returns:
            str: The code of the search parameter if type is "reference", or the chained search parameters otherwise.
        """
        if param_type == "reference":
            return list(search_params.values())[0].get("code")
        else:
            return self.chain_search_parameters(search_params)

    def set_attribute_search_param(
        self,
        attribute,
        fhir_mapping,
        predefined_type,
        profile_snapshot,
        module_dir_name: str,
    ):
        attribute_key = generate_attribute_key(attribute)
        attribute_type = (
            predefined_type
            if predefined_type
            else self.get_attribute_type(profile_snapshot, attribute, module_dir_name)
        )
        attribute_search_params = self.resolve_fhir_search_parameter(
            attribute, profile_snapshot, module_dir_name, attribute_type
        )
        composite_code = None
        if attribute_type == "composite":
            attribute_type = self.get_composite_attribute_type(
                attribute, profile_snapshot, module_dir_name
            )
            composite_code = self.get_composite_code(
                attribute, profile_snapshot, module_dir_name
            )
            attribute_key = composite_code
        fhir_mapping.add_attribute(
            attribute_type,
            attribute_key,
            self._handle_search_parameter(attribute_type, attribute_search_params),
            composite_code,
        )

    def get_composite_code(
        self, attribute, profile_snapshot: StructureDefinitionSnapshot, module_dir_name
    ):
        attribute_parsed = get_element_defining_elements(
            profile_snapshot, attribute, module_dir_name, self.__modules_dir
        )
        if len(attribute_parsed) != 2:
            raise ValueError(
                "Composite search parameters must have exactly two elements"
            )
        where_clause_element = attribute_parsed[-1]
        return profile_snapshot.get_fixed_term_codes(
            where_clause_element, self.__modules_dir, module_dir_name, self.__client
        )[0]

    def get_composite_attribute_type(
        self,
        attribute,
        profile_snapshot: StructureDefinitionSnapshot,
        module_dir_name: str,
    ):
        search_param_components = self.resolve_fhir_search_parameter(
            attribute, profile_snapshot, module_dir_name, "composite"
        )
        first_search_param = next(iter(search_param_components.values()))

        match first_search_param.get("type"):
            case "quantity":
                attribute_type = "quantity"
            case "token":
                attribute_type = "concept"
            case _ as t:
                comb_sp_name = "$".join(search_param_components.keys())
                raise ValueError(
                    f"Composite search parameter must have a quantity or token as the first element but has {t}"
                    f"[search_param={comb_sp_name}, elem_id={attribute}, profile_url={profile_snapshot.url}]"
                )
        return attribute_type

    def set_value_search_param(
        self,
        fhir_mapping: FhirMapping,
        profile_snapshot: StructureDefinitionSnapshot,
        querying_meta_data: ResourceQueryingMetaData,
        module_dir_name: str,
    ):
        value_type = (
            querying_meta_data.value_type
            if querying_meta_data.value_type
            else self.get_attribute_type(
                profile_snapshot, querying_meta_data.value_defining_id, module_dir_name
            )
        )
        fhir_mapping.valueType = value_type
        value_search_params = self.resolve_fhir_search_parameter(
            querying_meta_data.value_defining_id,
            profile_snapshot,
            module_dir_name,
            value_type,
        )
        fhir_mapping.valueSearchParameter = self._handle_search_parameter(
            value_type, value_search_params
        )

    def set_term_code_search_param(
        self,
        fhir_mapping: FhirMapping,
        profile_snapshot: StructureDefinitionSnapshot,
        querying_meta_data: ResourceQueryingMetaData,
        module_dir_name: str,
    ):
        term_code_search_params = self.resolve_fhir_search_parameter(
            querying_meta_data.term_code_defining_id,
            profile_snapshot,
            module_dir_name,
            "concept",
        )
        search_param_str = self.chain_search_parameters(term_code_search_params)
        fhir_mapping.termCodeSearchParameter = search_param_str

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
        # remove cast expression as it is irrelevant for the type
        if " as ValueSet" in attribute_id:
            attribute_id = attribute_id.replace(" as ValueSet", "")
        attribute_element = resolve_defining_id(
            profile_snapshot, attribute_id, str(self.__modules_dir), module_dir_name
        )
        extracted_value_type = extract_value_type(
            attribute_element, profile_snapshot.name
        )
        return (
            FHIR_TYPES_TO_VALUE_TYPES.get(extracted_value_type)
            if extracted_value_type in FHIR_TYPES_TO_VALUE_TYPES
            else extracted_value_type
        )

    def translate_element_id_to_fhir_path_expressions(
        self,
        element_id: str,
        profile_snapshot: StructureDefinitionSnapshot,
        module_dir_name: str,
    ) -> List[str]:
        """
        Translates an element id to a fhir search parameter
        :param element_id: element id
        :param profile_snapshot: FHIR profile snapshot containing the element id
        :param module_dir_name: Name of the module directory
        :return: fhir search parameter
        """
        elements = get_element_defining_elements(
            profile_snapshot, element_id, module_dir_name, self.__modules_dir
        )
        return translate_element_to_fhir_path_expression(profile_snapshot, elements)

    @staticmethod
    def validate_chainable(chainable_search_parameter) -> bool:
        """
        Validates the chaining of search parameters
        :param chainable_search_parameter: the search parameter to be chained
        :return: true if the search parameter can be chained else false
        """
        if not chainable_search_parameter:
            raise ValueError("No search parameters to chain")
        elif len(chainable_search_parameter) == 1:
            return True
        return functools.reduce(
            lambda x, y: (
                True
                if x
                and len(set(y.get("base", [])).intersection(x.get("target", []))) != 0
                else False
            ),
            chainable_search_parameter,
        )
