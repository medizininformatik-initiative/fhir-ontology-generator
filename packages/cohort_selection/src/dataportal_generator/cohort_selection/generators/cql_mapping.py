import json
from collections.abc import Mapping
from itertools import chain
from typing import Literal
from xml.etree import ElementTree as ET

import dataportal_generator.cohort_selection.resources
from dataportal_generator.cohort_selection.util.io import load_criterion_mapping

from dataportal_generator.common.fhir.structure_definition import select_element_compatible_with_cql_operations
from dataportal_generator.common.fhirpath.resolvers import FHIRPathResolver
from dataportal_generator.common.model.fhir.nav_element_definition import NavElementDefinition
from dataportal_generator.common.model.fhir.nav_structure_definition import NavStructureDefinition
from dataportal_generator.cohort_selection.model.criterion import CriterionDefinition
from dataportal_generator.cohort_selection.model.mapping.cql import (
    CQLMapping,
    CQLAttributeSearchParameter,
    CQLTimeRestrictionParameter,
    CQLTypeParameter,
    SimpleCardinality,
)
from dataportal_generator.common.model.terminology import TermCode
from dataportal_generator.common.exceptions.typing import UnsupportedTypingException
from dataportal_generator.common.fhir.structure_definition import get_parent_element

from dataportal_generator.common.model.project import Project
from dataportal_generator.common.log.functions import get_logger
from importlib.resources import files

_logger = get_logger(__name__)

_CRIT_ATTR_KEY_SYSTEM = "http://hl7.org/fhir/StructureDefinition"

with files(dataportal_generator.cohort_selection.resources).joinpath("cql", "cql-types-to-value-types.json").open(
        "r", encoding="utf-8"
) as fp:
    CQL_TYPES_TO_VALUE_TYPES = json.load(fp=fp)


class CQLMappingGenerationError(Exception):
    pass


def _get_primary_paths_per_resource() -> Mapping[str, str]:
    primary_paths = {}
    with (
        files(dataportal_generator.cohort_selection.resources)
                .joinpath("cql", "elm-modelinfo.xml")
                .open(mode="r", encoding="utf-8") as f
    ):
        _logger.info("Loading CQL ELM FHIR model info")
        root = ET.parse(f).getroot()
        namespace_map = {"elm": "urn:hl7-org:elm-modelinfo:r1"}
        for type_info in root.findall(".//elm:typeInfo", namespaces=namespace_map):
            resource_type = type_info.get("name")
            primary_path = type_info.get("primaryCodePath")
            if resource_type and primary_path:
                primary_paths[resource_type] = primary_path
    return primary_paths


_RESOURCE_TYPE_PRIMARY_PATHS: Mapping[str, str] = _get_primary_paths_per_resource()


def _cql_path_for_attribute(chain: list[tuple[NavStructureDefinition, NavElementDefinition]]) -> str:
    """
    Aggregates the path to an element for use in a CQL query (source expression)

    :param chain: Defining chain of element definitions their containing structure definitions representing the path of
                  the element and the element itself
    :return: CQL-compatible path
    """
    path = []
    for _, ed in chain:
        opt_ed, _ = select_element_compatible_with_cql_operations(ed)
        path.append(opt_ed.path.split(".", maxsplit=1)[-1])
    return ".".join(path)


def _aggregate_cardinality_using_element(
        elem_def: NavElementDefinition,
        struct_def: NavStructureDefinition,
        card_type: Literal["min", "max"] = "max",
) -> SimpleCardinality:
    """
    Aggregates the cardinality of an element along its path by collecting the cardinalities of itself and the parent
    elements and combining them to obtain the aggregated value as viewed from the root of the FHIR Resource

    :param elem_def: Element to calculate the aggregated cardinality for
    :param struct_def: Snapshot of profile defining the element
    :param card_type: Type of cardinality to aggregate (either 'mix' or 'max')
    :return: Aggregated cardinality stating whether an element can occur multiple times or not
    """
    opt_element, _ = select_element_compatible_with_cql_operations(
        elem_def
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
            parent_elem_def = get_parent_element(struct_def, elem_def)
            # when no slice
            if opt_element_path == parent_elem_def.id:
                opt_parent_el, _ = select_element_compatible_with_cql_operations(parent_elem_def)
                grand_parent_el = get_parent_element(struct_def, opt_parent_el)
                if grand_parent_el is None and opt_element_path.count(".") == 0:
                    return SimpleCardinality.SINGLE
                return (
                        _aggregate_cardinality_using_element(
                            parent_elem_def, struct_def, card_type
                        )
                        * card
                )

            match parent_elem_def:
                case None:
                    if not is_root:
                        raise Exception(
                            f"No parent could be identified for element '{opt_element.id}' with "
                            f"non-root path '{opt_element_path}'"
                        )
                    else:
                        # The root element is always assumed to have `SINGLE` cardinality
                        return SimpleCardinality.SINGLE
                case parent_elem_def:
                    return (
                            _aggregate_cardinality_using_element(
                                parent_elem_def, struct_def, card_type
                            )
                            * card
                    )


def _aggregate_cardinality_of_element_chain(
        chain: list[tuple[NavStructureDefinition, NavElementDefinition]]) -> SimpleCardinality:
    """
    Aggregate the cardinality along a chain of element definitions and the structure definition they are defined in.
    Short-circuits if at any point along the sub chains multiple elements are allowed

    :param chain: List of tuples of element definitions and the structure definitions they are defined in. The chain
                  represents the all the defining contexts of some nested element
    :return: Aggregated max cardinality
    """
    card = SimpleCardinality.SINGLE
    for struct_def, elem_def in chain:
        card *= _aggregate_cardinality_using_element(elem_def, struct_def)
        if card == SimpleCardinality.MANY:
            break
    return card


def _sub_path_equals(sub_path, path):
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


class CQLMappingGenerator(object):
    __allowed_time_restriction_fhir_types = {"date", "dateTime", "Period", "instant"}
    __allowed_defining_code_fhir_types = {"Coding", "CodeableConcept", "Reference"}
    __allowed_defining_value_fhir_types = {
        "code",
        "date",
        "Coding",
        "CodeableConcept",
        "Quantity",
    }

    def __init__(
            self,
            project: Project,
    ):
        """
        :param project: Project to operate on
        """
        self.__project = project
        self.__package_manager = project.package_manager
        self.__fp_resolver = FHIRPathResolver(self.__package_manager)
        self.__terminology_src = self.__project.terminology_src
        self.__criterion_mapping = load_criterion_mapping(self.__project)

    def _load_criterion_definitions(self, module: str) -> list[CriterionDefinition]:
        module_dir = self.__project.input.cohort_selection / "modules" / module
        _logger.debug(f"Loading criterion definitions for module '{module}' @ {module_dir!r}")
        criteria_dir = module_dir / "criteria"
        cds = []
        for cd_fp in sorted(chain(criteria_dir.glob("**/*.yml"), criteria_dir.glob("**/*.yaml"))):
            _logger.debug(f"Found criterion definition '{cd_fp.name}' @ {cd_fp!r}")
            with open(cd_fp, mode="rb") as fd:
                cds.append(CriterionDefinition.model_validate_yaml(fd))
        return cds

    def _is_primary_path(self, resource_type: str, fhir_path: str) -> bool:
        """
        Checks if the given fhir path is not a primary path according to the cql elm modelinfo
        :param resource_type: FHIR resource type
        :param fhir_path: FHIRPath expression to check if it represents the primary path
        :return: ``True`` if the given fhir path is not a primary path, ``False`` otherwise
        """
        if primary_path := _RESOURCE_TYPE_PRIMARY_PATHS.get(resource_type):
            return _sub_path_equals(primary_path, fhir_path)
        return False

    def _get_reference_type(
            self,
            chain: list[tuple[NavStructureDefinition, NavElementDefinition]],
    ):
        """
        Returns the type of the referenced attribute. The first element definition in the chain that is of type
        Reference is used and the first FHIR resource type determined as the reference target is returned

        :param chain: Chain of structure definition and element definition tuples leading to the attribute
        :return: Reference FHIR resource type of the attribute
        """
        # FIXME: This method is not sustainable since it does not consider the case where multiple types are allowed as
        #        the reference target. Also, the first Reference-typed element definition is used always, which may not
        #        be intended
        ref_elem_def = next(ed for _, ed in chain if any(t.code == "Reference" for t in ed.type))
        ref_type_info = ref_elem_def.type_info_for("Reference")
        ref_profile = self.__package_manager.find_struct_def(ref_type_info.targetProfile[0])
        if not ref_profile:
            raise FileNotFoundError(f"Referenced structure definition '{ref_type_info.targetProfile[0]}' not found")
        return ref_profile.type

    def generate_mapping(
            self, module: str
    ) -> list[CQLMapping]:
        """
        Generates the CQL mappings for the given module
        :param module: Name of the module to generate the mapping for
        :return: normalized term code CQL mapping
        """
        criterion_defs = self._load_criterion_definitions(module)
        mappings = []
        for criterion_def in criterion_defs:
            _logger.info(f"Generating CQL mapping for criterion '{criterion_def.name}'")
            mappings.append(self.generate_cql_mapping(criterion_def))
        return mappings

    def generate_cql_mapping(
            self, criterion_def: CriterionDefinition
    ) -> CQLMapping:
        """
        Generates the CQL mapping for the given FHIR profile snapshot and querying metadata entry
        :param criterion_def: Criterion definition to generate CQL mapping for
        :return: CQL mapping
        """
        # Construct only since keys are added later (key expansion)
        cql_mapping = CQLMapping.model_construct(name=f"{criterion_def.module}.{criterion_def.name}")
        struct_def = self.__package_manager.find_struct_def(criterion_def.definition_source.structure_definition)
        if crit_identifier := criterion_def.identifier:
            # TODO: Temporary fix by filtering out CDS Medication querying metadata since they receive special
            #       treatment in the CCTB CQL translation logic. This should not be handled by the generator. Instead
            #       the criterion definition and mapping should be able to express this handling by themselves
            if (
                    not crit_identifier.type == "fixed"
                    and not self._is_primary_path(
                struct_def.type,
                crit_identifier.definition.expression.split(".", maxsplit=1)[-1],
            )
                    and not criterion_def.module == "Medikation"
            ):
                chain = self.__fp_resolver.resolve_path(struct_def, crit_identifier.definition.expression)
                struct_def, elem_def = chain[-1]
                elem_def, types = select_element_compatible_with_cql_operations(elem_def)
                if not types:
                    raise KeyError(
                        "ElementDefinition.type cannot be empty as at least one type is required for CQL "
                        f"translation ('{struct_def.name}|{elem_def.id}')]"
                    )
                types = self.__allowed_defining_code_fhir_types.intersection(types)
                if len(types) == 0:
                    raise UnsupportedTypingException(
                        f"Supported type range of element '{elem_def.id}' has no "
                        f"overlap with the expected type range of a time restricting "
                        f"element in the CQL mapping [present={types}, "
                        f"allowed={self.__allowed_defining_code_fhir_types}]"
                    )
                term_code_fhir_path = _cql_path_for_attribute(chain)
                card = _aggregate_cardinality_of_element_chain(
                    chain
                )
                cql_mapping.termCode = CQLTypeParameter(
                    path=term_code_fhir_path, types=types, cardinality=card
                )

        if crit_value := criterion_def.value:
            chain = self.__fp_resolver.resolve_path(struct_def, crit_value.definition.expression)
            struct_def, elem_def = chain[-1]
            elem_def, types = select_element_compatible_with_cql_operations(elem_def)
            if not types:
                raise KeyError(
                    "ElementDefinition.type cannot be empty as at least one type is required for CQL "
                    f"translation ('{struct_def.name}|{elem_def.id}')"
                )
            types = self.__allowed_defining_value_fhir_types.intersection(types)
            if len(types) == 0:
                raise UnsupportedTypingException(
                    f"Supported type range of element {elem_def.id!r} has no "
                    f"overlap with the expected type range of a value element in the CQL "
                    f"mapping [present={types}, "
                    f"allowed={self.__allowed_defining_value_fhir_types}]"
                )
            value_fhir_path = _cql_path_for_attribute(chain)
            card = _aggregate_cardinality_of_element_chain(chain)
            cql_mapping.value = CQLTypeParameter(
                path=value_fhir_path, types=types, cardinality=card
            )

        if crit_time_restriction := criterion_def.time_restriction:
            chain = self.__fp_resolver.resolve_path(struct_def, crit_time_restriction.expression)
            struct_def, elem_def = chain[-1]
            elem_def, types = select_element_compatible_with_cql_operations(elem_def)
            if not types:
                raise KeyError(
                    "ElementDefinition.type cannot be empty as at least one type is required for CQL "
                    f"translation ('{struct_def.id}|{elem_def.id}')"
                )
            types = self.__allowed_time_restriction_fhir_types.intersection(types)
            if len(types) == 0:
                raise UnsupportedTypingException(
                    f"Supported type range of element '{elem_def.id}' has no "
                    f"overlap with the expected type range of a time restricting element "
                    f"in the CQL mapping [present={types}, "
                    f"allowed={self.__allowed_time_restriction_fhir_types}]"
                )
            fhir_path = _cql_path_for_attribute(chain)
            card = _aggregate_cardinality_of_element_chain(
                chain
            )
            cql_mapping.timeRestriction = CQLTimeRestrictionParameter(
                types=types, cardinality=card, path=fhir_path
            )
        # Criterion attributes
        cql_mapping.attributes = self._generate_attribute_mapping(criterion_def)

        return cql_mapping

    def _generate_attribute_mapping(
            self, criterion_def: CriterionDefinition
    ) -> list[CQLAttributeSearchParameter]:
        params = []
        struct_def = self.__package_manager.find_struct_def(criterion_def.definition_source.structure_definition)
        for criterion_attr in criterion_def.attributes:
            chain = self.__fp_resolver.resolve_path(struct_def, criterion_attr.definition.expression)
            # TODO: Switch over to appropriate term code or just attribute name
            attribute_key = TermCode(
                system=_CRIT_ATTR_KEY_SYSTEM,
                code=criterion_attr.name,
                display=criterion_attr.name
            )
            if criterion_attr.type == "reference":
                attribute_types = {"Reference"}
                reference_target_type = self._get_reference_type(chain)
            else:
                _, opt_elem_def_types = select_element_compatible_with_cql_operations(chain[-1][1])
                attribute_types = {CQL_TYPES_TO_VALUE_TYPES[t] for t in opt_elem_def_types}
                reference_target_type = None
            attribute_fhir_path = _cql_path_for_attribute(chain)
            cards = _aggregate_cardinality_of_element_chain(
                chain
            )
            params.append(CQLAttributeSearchParameter(
                types=attribute_types,
                key=attribute_key,
                path=attribute_fhir_path,
                cardinality=cards,
                referenceTargetType=reference_target_type
            ))
        return params


def generate_cql_mapping(project: Project, modules: list[str] | None = None):
    """
    Generates the CQL mapping for all modules in the project
    :param project: Project to generate the mapping for
    :param modules: List of module names to generate the mapping for. If ``None`` then all modules are considered
    """
    try:
        generator = CQLMappingGenerator(project)
        output_file = project.output.cohort_selection / "mappings" / "cql_mapping.json"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with output_file.open(mode="wb") as out_fd:
            out_fd.write(b"[")
            first = True
            for module_dir in (project.input.cohort_selection / "modules").iterdir():
                if module_dir.is_dir() and (not modules or module_dir.name in modules):
                    module_name = module_dir.name
                    _logger.info(f"Generating CQL mapping for module '{module_name}'")
                    for entry in generator.generate_mapping(module_name):
                        if not first:
                            out_fd.write(b",")
                        else:
                            first = False
                        out_fd.write(entry.model_dump_json(by_alias=True, exclude_none=True).encode("utf-8"))
            out_fd.write(b"]")
    except Exception as x:
        _logger.error(f"Failed to generate CQL mapping: {x}")
        raise CQLMappingGenerationError("Failed to generate CQL mapping") from x
