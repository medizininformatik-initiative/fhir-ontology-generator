import json
from collections.abc import Mapping
from pathlib import Path

from itertools import groupby, chain

from fhir.resources.R4B.coding import Coding
from fhir.resources.R4B.valueset import ValueSetExpansion

from dataportal_generator.common.exceptions.fhir import ResourceNotFoundError
from dataportal_generator.common.fhirpath.resolvers import FHIRPathResolver
from dataportal_generator.common.log.functions import get_logger
from dataportal_generator.common.model.fhir.nav_element_definition import (
    NavElementDefinition,
)
from dataportal_generator.common.model.project import Project
from fhir.resources.R4B.elementdefinition import ElementDefinition, ElementDefinitionBinding

from dataportal_generator.cohort_selection.model.concept_tree import (
    ConceptTree,
    ConceptTreeEntry,
    ConceptTreeGroup, CRITERION_IDENTIFIER_KEY, CriterionTreeMapping,
)
from dataportal_generator.cohort_selection.model.criterion import CriterionDefinition, CriterionAttribute

_logger = get_logger(__file__)

# FHIR data types of elements that can be the source of allowed concepts
_CODED_TYPES = frozenset({"code", "Coding", "CodeableConcept"})
# Binding strengths that actually constrain the allowed codes. 'example' bindings are purely illustrative
_CONSTRAINING_BINDING_STRENGTHS = frozenset({"required", "extensible", "preferred"})
_BINDING_STRENGTH_MAGNITUDE = {
    None: -1,
    "example": 0,
    "preferred": 1,
    "extensible": 2,
    "required": 3,
}
# Elements of the `Coding` data type relevant for identifying a concept
_CODING_KEYS = ("system", "version", "code", "display")
# All `ElementDefinition.fixed[x]` and `ElementDefinition.pattern[x]` fields (excluding primitive extension fields)
_FIXED_VALUE_FIELDS = tuple(
    name
    for name in ElementDefinition.model_fields
    if name.startswith(("fixed", "pattern")) and "__" not in name
)

type _AttributeTreeMapping = dict[str, list[str]]

type Binding = ElementDefinitionBinding


class ConceptTreeGenerationError(Exception):
    pass


def _canonical(url: str, version: str | None = None) -> str:
    """
    Builds the FHIR canonical from the provided URL and (optional) version as ``<url>[|<version>]``
    """
    return url + (("|" + version) if version else "")


def _split_canonical(canonical: str) -> tuple[str, str | None]:
    """
    Splits a FHIR canonical value into its URL and (optional) version component, e.g. ``<url>[|<version>]``
    """
    split = canonical.split("|")
    return split[0], split[1] if len(split) > 1 else None


def _merge_codings(a: Coding, b: Coding) -> Coding:
    """Merges two partial codings. Raises ``ValueError`` if they are not compatible, i.e. contradict each other"""
    for key in _CODING_KEYS:
        val_a, val_b = getattr(a, key), getattr(b, key)
        if val_a and val_b and val_a != val_b:
            raise ValueError(f"Provided Codings are not mergeable: {a!r}, {b!r}")
    return Coding.model_validate({**a.model_dump(exclude_none=True), **b.model_dump(exclude_none=True)})


def _fixed_concept_tree_identifier(crit_def: CriterionDefinition, attr_name: str) -> str:
    """Generates an identifier for a fixed concept tree group"""
    return f"{crit_def.module}.{crit_def.name}.{attr_name}"


def _cmp_binding_strength(a: Binding | None, b: Binding | None) -> int:
    """
    Compares FHIR ValueSet binding strengths. Return value is ``> 0`` if ``a > b``, ``0`` if ``a = b`` and ``< 0``
    otherwise
    """
    return _BINDING_STRENGTH_MAGNITUDE[a.strength if a else None] - _BINDING_STRENGTH_MAGNITUDE[
        b.strength if b else None]


def _system_restriction(elem_def: NavElementDefinition) -> str | None:
    """
    Finds value restriction on the ``system`` element of a FHIR ``Coding``

    :param elem_def: ``ElementDefintion`` of the ``system`` element
    :return: Fixed element value if it exists, otherwise ``None``
    """
    fixed_val = elem_def.fixedUri
    if not fixed_val:
        fixed_val = elem_def.patternUri
    return fixed_val


def _code_systems_used_in_expansion(vs_expansion: ValueSetExpansion) -> list[tuple[str, str | None]]:
    """
    Extracts the canonicals and versions of code systems used in a value set expansion

    :param vs_expansion: Value set expansion to extract canonicals of used code systems from
    :return: List of tuples of canonical and version (``None`` if not present)
    """
    code_systems = []
    for param in filter(lambda param: param.name == "used-codesystem", vs_expansion.parameter):
        code_systems.append(_split_canonical(param.valueUri))
    if not code_systems:
        raise ValueError("Value set expansion is missing expansion parameters 'used-codesystem'")
    return code_systems


class CriterionConceptTreeGenerator:
    def __init__(
            self, project: Project, crit_def: CriterionDefinition
    ):
        """
        :param project: Project to operate on
        :param crit_def: Criterion definition to generate concept trees for
        :param existing_tree_ids: (Optional) identifiers of already generated attribute concept trees. Value set based
                                  concept trees with a matching identifier are reused instead of being generated again
        """
        self.__project = project
        self.__package_manager = project.package_manager
        self.__terminology_src = project.terminology_src
        self.__fp_resolver = FHIRPathResolver(self.__package_manager)
        self.__tree_dir = project.output.cohort_selection.mkdirs("concept_trees", "trees")
        self.__tree_group_uuids = {fp.stem for fp in self.__tree_dir.iterdir() if fp.is_file() and fp.suffix == ".json"}

        self.__crit_def = crit_def
        url = crit_def.definition_source.structure_definition
        if struct_def := self.__package_manager.find_struct_def(url):
            self.__struct_def = struct_def
        else:
            raise ConceptTreeGenerationError(f"Structure definition '{url}' of criterion '{crit_def.name}' not found")

    def _tree_group_exists(self, identifier: str) -> bool:
        return ConceptTreeGroup.uuid_of(identifier) in self.__tree_group_uuids

    def _get_composing_code_system_canonicals(self, vs_canonical: str) -> set[str]:
        vs = self.__package_manager.find_value_set(vs_canonical)
        if not vs:
            vs = self.__terminology_src.value_set(canonical=vs_canonical)
        if not vs:
            raise ResourceNotFoundError(f"Could not find ValueSet resource '{vs_canonical}'")
        if compose := vs.compose:
            cs_canonicals = set()
            for incl in compose.include:
                if incl.valueSet:
                    cs_canonicals.update(
                        self._get_composing_code_system_canonicals(vs_canonical) for vs_canonical in incl.valueSet)
                else:
                    cs_canonicals.add(incl.system + (("|" + incl.version) if incl.version else ""))
            return cs_canonicals
        elif (expansion := vs.expansion) and (contains := expansion.contains):
            return {c.system + (("|" + c.version) if c.version else "") for c in contains}
        else:
            raise ValueError(f"Value set '{vs_canonical}' has neither definition nor expansion")

    def _code_restriction(self, elem_def: NavElementDefinition) -> Coding | Binding | None:
        # TODO: Do we also need slicing handling here?
        fixed_val = elem_def.fixedCode
        if not fixed_val:
            fixed_val = elem_def.patternCode
        binding = None
        if (b := elem_def.binding) and b.valueSet and (b.strength in _CONSTRAINING_BINDING_STRENGTHS):
            binding = b
        if not fixed_val:
            return binding
        system = None
        if binding:
            code_systems = {canonical.split("|", 1)[0] for canonical in
                            self._get_composing_code_system_canonicals(binding.valueSet)}
            if len(code_systems) == 1:
                system = code_systems[0]
        return Coding(
            system=system,
            code=fixed_val
        )

    def _coding_restriction(self, elem_def: NavElementDefinition) -> list[Coding | Binding]:
        binding = None
        system = None
        code = None
        if fixed_val := elem_def.fixedCoding:
            # If a fixed value is present we can return immediately since no deviation from it is allowed
            if not fixed_val.system or not fixed_val.code:
                raise ValueError(f"Coding pattern of element definition '{elem_def.id}' in structure definition "
                                 f"'{elem_def.struct_def.url}' is incomplete (system and code are required)")
            return [fixed_val]
        fixed_val = elem_def.patternCoding
        if fixed_val:
            system = fixed_val.system
            code = fixed_val.code
        # Further fixed system determination
        if not system and (system_elem_def := elem_def.child("system")):
            system = _system_restriction(system_elem_def)
        if (b := elem_def.binding) and b.valueSet and (b.strength in _CONSTRAINING_BINDING_STRENGTHS):
            binding = b
            systems = {canonical.split("|", 1)[0] for canonical in
                       self._get_composing_code_system_canonicals(b.valueSet)}
            if not system and len(systems) == 1:
                system = systems[0]
        # Further fixed code determination
        if not code and (code_elem_def := elem_def.child("code")):
            match self._code_restriction(code_elem_def):
                case ElementDefinitionBinding() as b:
                    binding = b if not binding or _cmp_binding_strength(b, binding) else binding
                case Coding() as c:
                    c = _merge_codings(c, Coding(system=system)) if system else c
                    system, code = c.system, c.code
                case _:  # None
                    pass
        # Check external data type definitions if necessary
        coding = Coding(system=system, code=code)
        if not system or not code:
            type_info = elem_def.type_info_for("Coding")
            if type_info and (def_refs := type_info.profile):
                for ref in def_refs:
                    dt_struct_def = self.__package_manager.find_struct_def(ref)
                    if not dt_struct_def:
                        raise ResourceNotFoundError(f"Could not find data type-defining StructureDefinition '{ref}'")
                    for restriction in self._coding_restriction(dt_struct_def.root):
                        match restriction:
                            case ElementDefinitionBinding() as b:
                                binding = b if not binding or _cmp_binding_strength(b, binding) else binding
                            case Coding() as c:
                                coding = _merge_codings(coding, c)
                            case _:  # None
                                pass
        # Coding-level slicing handling
        restrictions = [r for s in elem_def.slices for r in self._coding_restriction(s)] if elem_def.slicing else []
        if coding.system or coding.code:
            restrictions.append(coding)
        if binding:
            restrictions.append(binding)
        return restrictions

    def _codeable_concept_restriction(self, elem_def: NavElementDefinition) -> list[Coding | Binding]:
        if elem_def.slicing:
            # CodeableConcept-level slicing handling
            return [r for s in elem_def.slices for r in
                    self._codeable_concept_restriction(s)] if elem_def.slicing else []
        if (val := elem_def.fixedCodeableConcept) and (codings := val.coding):
            # If a fixed value is present we can return immediately since no deviation from it is allowed
            if any(not c.system or not c.code for c in codings):
                raise ValueError(f"CodeableConcept pattern of element definition '{elem_def.id}' in structure "
                                 f"definition '{elem_def.struct_def.url}' has incomplete Codings (system and code are "
                                 f"required)")
            return codings
        codings = []
        if (val := elem_def.patternCodeableConcept) and val.coding:
            # Add only "complete" codings
            codings.extend(filter(lambda c: c.system and c.code, val.coding))
        bindings = []
        if (b := elem_def.binding) and b.valueSet and (b.strength in _CONSTRAINING_BINDING_STRENGTHS):
            bindings.append(b)
        if coding_elem_def := elem_def.child("coding"):
            for constraint in self._coding_restriction(coding_elem_def):
                match constraint:
                    case ElementDefinitionBinding() as b:
                        match _cmp_binding_strength(b, bindings[0] if bindings else None):
                            case x if x > 0:
                                bindings = [b]
                            case 0:
                                bindings.append(b)
                    case Coding() as c:
                        codings.append(c)
        return [*codings, *bindings]

    def _restrictions(self, elem_def: NavElementDefinition) -> list[Coding | Binding]:
        match elem_def.type[0].code:
            case "CodeableConcept":
                return self._codeable_concept_restriction(elem_def)
            case "Coding":
                return self._coding_restriction(elem_def)
            case "code":
                restriction = self._code_restriction(elem_def)
                return [restriction] if restriction else []
            case _:
                raise TypeError(f"Unsupported FHIR data type '{elem_def.type[0].code}'. Expected one of "
                                f"'CodeableConcept', 'Coding' or 'code'")

    def _is_hierarchical(self, system: str, version: str | None) -> bool:
        code_system = self.__terminology_src.code_system(system, version)
        if not code_system:
            raise ResourceNotFoundError(
                f"Could not find CodeSystem resource '{_canonical(system, version)}'")
        return code_system.hierarchyMeaning is not None

    def _write_concept_tree_group(self, group: ConceptTreeGroup) -> str:
        tree_grp_id = ConceptTreeGroup.uuid_of(group.identifier)
        with (self.__tree_dir / (tree_grp_id + ".json")).open(mode="w", encoding="utf-8") as fd:
            fd.write(group.model_dump_json(exclude_none=True))
        return tree_grp_id

    def _generate_concept_tree_group_for_vs_canonical(self, canonical: str) -> str:
        """
        Generates the concept tree group for the value set with the given canonical. If concept trees do not exist yet,
        they will be generated, written to disk, and their identifiers returned. Otherwise, the identifiers of the
        existing concept tree group is returned.

        :param canonical: Canonical of the value set to generate concept tree group for
        :return: Concept tree group identifier
        """
        vs_url, vs_version = _split_canonical(canonical)
        vs = self.__terminology_src.expand_value_set(vs_url, vs_version)
        expansion = vs.expansion
        trees = {}
        # Get default code system version used in the expansion to supply version data if the concepts in the expansion
        # list none themselves
        default_cs_version_map = {}
        for s, v in _code_systems_used_in_expansion(expansion):
            cur_v = default_cs_version_map.get(s)
            default_cs_version_map[s] = max(cur_v, v) if cur_v else v
        # Group by code system version
        key_func = lambda c: (c.system, c.version)
        for key, grp in groupby(sorted(expansion.contains, key=key_func), key=key_func):
            cs_url, cs_version = key
            if not cs_version:
                cs_version = default_cs_version_map[cs_url]  # Choose latest version as default
            if self._is_hierarchical(cs_url, cs_version):
                codings = [Coding(system=cs_url, version=cs_version, code=c.code, display=c.display) for c in grp]
                cm = self.__terminology_src.closure(codings)
                if not cm.group:
                    _logger.warning(
                        f"Code system {_canonical(cs_url, cs_version)} defines supported hierarchy meaning but "
                        f"no hierarchy was found. Defaulting to flat concept list")
                    tree = ConceptTree(
                        system=cs_url,
                        version=cs_version,
                        entries=[ConceptTreeEntry(code=c.code) for c in codings]
                    )
                else:
                    concept_entries = {c.code: ConceptTreeEntry(code=c.code) for c in codings}
                    # According to the operations definition, the ConceptMap resource should contain exactly one group
                    subsumption_map = {elem.code: [t.code for t in elem.target] for elem in cm.group[0].element}
                    # Remove non-immediate ancestors and aggregate children
                    for code, ancestors in subsumption_map.items():
                        parents = ancestors.copy()
                        for a in ancestors:
                            # There are cases where the closure table does not contain entries for parent concepts.
                            # Presumably because they do not have parents. Such concepts cannot and do not need to be
                            # processed further (under that assumption)
                            # TODO: Check the assumption described above
                            if a in parents and (a_ancestors := subsumption_map.get(a)):
                                for aa in a_ancestors:
                                    if aa in parents:
                                        parents.remove(aa)
                        concept_entries[code].parents = parents
                        subsumption_map[code] = parents
                        # Add as child to all true parents
                        for p in parents:
                            concept_entries[p].children.append(code)
                    tree = ConceptTree(
                        system=cs_url,
                        version=cs_version,
                        entries=list(concept_entries.values())
                    )
            else:
                tree = ConceptTree(
                    system=cs_url,
                    version=cs_version,
                    entries=[ConceptTreeEntry(code=c.code) for c in grp]
                )
            trees[cs_url + (("|" + cs_version) if cs_version else "")] = tree
        concept_tree_grp = ConceptTreeGroup(
            identifier=canonical,
            valueSet=f"{vs.url}|{vs.version}",
            trees=trees
        )
        return self._write_concept_tree_group(concept_tree_grp)

    def _generate_concept_tree_group_for_coding_list(self, identifier: str, codings: list[Coding]) -> str:
        key_func = lambda c: (c.system, c.version)
        cs_groups = groupby(sorted(codings, key=key_func), key=key_func)
        concept_tree_grp = ConceptTreeGroup(
            identifier=identifier,
            valueSet=None,
            trees={key[0] + (("|" + key[1]) if key[1] else ""): ConceptTree(
                system=key[0],
                version=key[1],
                entries=[ConceptTreeEntry(code=c.code) for c in grp]
            ) for key, grp in cs_groups}
        )
        return self._write_concept_tree_group(concept_tree_grp)

    def _generate_for_implicit_definition(self, identifier: str, expr: str) -> list[str]:
        """
        Generates the concept trees for the element the expression points to. If concept trees do not exist yet, they
        will be generated, written to disk, and their identifiers returned. Otherwise, the identifiers of the existing
        concept trees are returned.

        :param identifier: Criterion identifier-/attribute-unique identifier used if the concepts are not solely
                           defined by a value set binding
        :param expr: FHIRPath expression pointing to the target element
        :return: List of concept tree identifiers
        """
        if not (result := self.__fp_resolver.resolve_leaf(self.__struct_def, expr)):
            raise ConceptTreeGenerationError(f"Expression '{expr}' could not be resolved in '{self.__struct_def.url}'")
        struct_def, elem_def = result
        type_codes = {t.code for t in elem_def.type or []}
        if len(type_codes) != 1 or not type_codes <= _CODED_TYPES:
            raise ConceptTreeGenerationError(
                f"Element definition '{elem_def.id}' targeted by expression '{expr}' has to support exactly one of the "
                f"data types {sorted(_CODED_TYPES)} but instead supports {sorted(type_codes)}"
            )
        restrictions = self._restrictions(elem_def)
        if not restrictions:
            raise ConceptTreeGenerationError(f"Failed to determine restrictions of element definition '{elem_def.id}' "
                                             f"defined in structure definition '{struct_def.url}'")
        concept_tree_refs = []
        codings = []
        for restriction in restrictions:
            if isinstance(restriction, ElementDefinitionBinding):
                canonical = restriction.valueSet
                concept_tree_refs.append(canonical)
                if not self._tree_group_exists(canonical):
                    _logger.debug(f"Generating concept trees for value set {canonical!r}")
                    self._generate_concept_tree_group_for_vs_canonical(canonical)
            elif isinstance(restriction, Coding) and restriction.code and restriction.system:
                codings.append(restriction)
        if codings:
            self._generate_concept_tree_group_for_coding_list(identifier, codings)
            concept_tree_refs.append(identifier)
        return concept_tree_refs

    def _generate_for_crit_identifier(self) -> list[str]:
        crit_identifier = self.__crit_def.identifier
        tree_id = _fixed_concept_tree_identifier(self.__crit_def, "identifier")
        if crit_identifier.type == "fixed":
            return [self._generate_concept_tree_group_for_coding_list(tree_id, crit_identifier.definition)]
        else:
            return self._generate_for_implicit_definition(tree_id, crit_identifier.definition.expression)

    def _generate_for_crit_attribute(self, crit_attr: CriterionAttribute) -> list[str]:
        return self._generate_for_implicit_definition(
            _fixed_concept_tree_identifier(self.__crit_def, crit_attr.name),
            crit_attr.definition.expression
        )

    def generate(self) -> _AttributeTreeMapping:
        _logger.debug(f"Generating concept trees for criterion identifier of criterion '%s'", self.__crit_def.name)
        crit_ident_trees = self._generate_for_crit_identifier()
        if not crit_ident_trees:
            raise ConceptTreeGenerationError(f"Failed determine concept trees for identifier of criterion "
                                             f"'{self.__crit_def.name}'")
        attr_mapping = {CRITERION_IDENTIFIER_KEY: crit_ident_trees}
        for attribute in self.__crit_def.attributes:
            _logger.debug("Generating concept trees for criterion attribute '%s' of criterion '%s'", attribute.name,
                          self.__crit_def.name)
            attr_trees = self._generate_for_crit_attribute(attribute)
            if not attr_trees:
                raise ConceptTreeGenerationError(f"Failed to determine concept trees for attribute '{attribute.name}' "
                                                 f"of criterion '{self.__crit_def.name}'")
            attr_mapping[attribute.name] = attr_trees
        return attr_mapping


def _load_criterion_definitions(project: Project) -> Mapping[str, list[CriterionDefinition]]:
    """
    Loads all criterion definitions of the project, i.e. the YAML files in
    ``<project>/input/cohort_selection/modules/<module>/criteria``

    :param project: Project to load criterion definitions for
    :return: List of criterion definitions
    """
    modules_dir = project.input.cohort_selection / "modules"
    crit_defs = {}
    for module_dir in sorted(modules_dir.iterdir()):
        if module_dir.is_dir():
            mod_crit_defs = []
            criteria_dir = module_dir / "criteria"
            for fp in sorted(chain(criteria_dir.glob("**/*.yml"), criteria_dir.glob("**/*.yaml"))):
                if fp.is_file():
                    _logger.debug(f"Loading criterion definition @ {fp}")
                    with fp.open(mode="rb") as fd:
                        crit_def = CriterionDefinition.model_validate_yaml(fd)
                        if crit_def.name in mod_crit_defs:
                            raise ConceptTreeGenerationError(f"Duplicate criterion name '{crit_def.name}' in module "
                                                             f"'{module_dir.name}'")
                        mod_crit_defs.append(crit_def)
            crit_defs[module_dir.name] = mod_crit_defs
    return crit_defs


def _remove_unused_tree_sets(tree_dir: Path, mapping: CriterionTreeMapping):
    if not tree_dir.exists():
        return
    used_uuids = set()
    for mod_crits in mapping.values():
        for crit_attrs in mod_crits.values():
            for tree_grps in crit_attrs.values():
                used_uuids.update([ConceptTreeGroup.uuid_of(grp_id) for grp_id in tree_grps])
    for path in tree_dir.glob("*.json"):
        if path.is_file() and path.stem not in used_uuids:
            _logger.info(f"Removing unused concept tree group '{path.stem}' @ {path}")
            path.unlink()


def generate_concept_trees(project: Project, remove_unused: bool = True) -> CriterionTreeMapping:
    """
    Generates concept trees for the identifiers and coded attributes of criterion definitions as well as a mapping
    associating them with the generated concept trees. Concept trees are persisted in the output directory and reused
    by subsequent runs. Concept trees no longer referenced by any criterion are removed at the end of each run
    """
    try:
        criterion_defs = _load_criterion_definitions(project)
        mapping = {}
        for module, crit_defs in criterion_defs.items():
            _logger.info("Generating criterion concept trees for module '%s'", module)
            mod_mapping = {}
            mapping[module] = mod_mapping
            for crit_def in crit_defs:
                _logger.info(f"Generating concept trees for criterion '{crit_def.name}'")
                mod_mapping[crit_def.name] = CriterionConceptTreeGenerator(project, crit_def).generate()
        with (project.output.cohort_selection.mkdirs("concept_trees") / "criterion_mapping.json").open(mode="w",
                                                                                                       encoding="utf-8") as fd:
            json.dump(mapping, fd, indent=4)
        if remove_unused:
            _remove_unused_tree_sets(project.output.cohort_selection / "concept_trees" / "trees", mapping)
        return mapping
    except Exception as x:
        _logger.error(f"Failed to generate concept trees", exc_info=True)
        raise ConceptTreeGenerationError("Failed to generate concept trees") from x
