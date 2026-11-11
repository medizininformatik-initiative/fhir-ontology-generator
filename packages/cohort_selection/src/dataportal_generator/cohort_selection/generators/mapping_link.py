import json
from collections.abc import Mapping, Iterator
from contextlib import contextmanager
from itertools import groupby
from pathlib import Path

from typing_extensions import deprecated

from dataportal_generator.cohort_selection.model.criterion import CriterionDefinition
from dataportal_generator.cohort_selection.model.mapping.query_criterion import QueryCriterionMappingEntry
from dataportal_generator.cohort_selection.util.io import load_criterion_definitions, load_concept_tree_group, \
    load_criterion_mapping
from dataportal_generator.common.log.functions import get_logger
from dataportal_generator.common.model.project import Project
from dataportal_generator.common.model.terminology import TermCode

_logger = get_logger(__file__)


class QueryCriterionMappingGenerationError(Exception):
    pass


@contextmanager
def _json_list_file_writer(file_path: Path, binary: bool = False):
    with open(file_path, mode="wb" if binary else "w", encoding=None if binary else "utf-8") as fd:
        fd.write("[")
        try:
            yield fd
        finally:
            fd.write("]")


def _iter_crit_identifiers(project: Project, module: str, name: str) -> Iterator[TermCode]:
    """
    Iterates over the term codes of the concept trees associated with the identifier of a criterion

    :param project: Project to locate the criterion tree mapping file and the concept tree files in
    :param module: Module the criterion belongs to
    :param name: Name of the criterion
    :return: Iterator of term codes of the concept trees associated with the criterion
    """
    crit_mapping_entry = load_criterion_mapping(project).get(module, {}).get(name)
    if not crit_mapping_entry:
        raise KeyError(f"Missing criterion mapping for criterion '{name}' of module '{module}'")
    tree_group_idents = crit_mapping_entry["$identifier"]
    for tree_ident in tree_group_idents:
        tree_group = load_concept_tree_group(project, tree_ident)
        for tree in tree_group.trees.values():
            system = tree.system
            version = tree.version
            for entry in tree.entries:
                yield TermCode(system=system, version=version, code=entry.code)


def _group_crit_defs(criterion_defs: Mapping[str, list[CriterionDefinition]]) -> Iterator[tuple[TermCode, list[CriterionDefinition]]]:
    """
    Groups the provided criterion definitions by their context

    :param criterion_defs: List of criterion definitions to group
    :return: Iterator of groups identified by a common context
    """
    flat_crit_defs = (crit_def for _, crit_defs in criterion_defs.items() for crit_def in crit_defs)
    sorted_crits_defs = sorted(flat_crit_defs , key=lambda crit_def: crit_def.context.code)
    return groupby(sorted_crits_defs, key=lambda crit_def: crit_def.context)


def generate_query_criterion_link(project: Project):
    """
    Generates a mapping between the contextualized term codes of the criteria and the corresponding query language
    mapping entries. The generated mapping is stored in the project as a JSON file.
    :param project: Project instance to generate the mapping for
    """
    _logger.info(f"Creating query criterion link for query language mappings")
    try:
        criterion_defs = load_criterion_definitions(project)
        with _json_list_file_writer(project.output.cohort_selection.mkdirs("mappings") / "query_criterion_link.json") as fd:
            first = True
            for context, crit_defs in _group_crit_defs(criterion_defs):
                system_keys = {}
                for crit_def in crit_defs:
                    for term_code in _iter_crit_identifiers(project, crit_def.module, crit_def.name):
                        # System level
                        if not term_code.system in system_keys:
                            version_keys = {}
                            system_keys[term_code.system] = version_keys
                        else:
                            version_keys = system_keys[term_code.system]
                        # Version level
                        if not term_code.version in version_keys:
                            code_keys = {}
                            version_keys[term_code.version] = code_keys
                        else:
                            code_keys = version_keys[term_code.version]
                        # Code level
                        if crit_ref := code_keys.get(term_code.code):
                            raise KeyError(f"Duplicate association for term code {term_code} in context {context}: "
                                           f"{crit_def.module}.{crit_def.name} and {crit_ref}")
                        code_keys[term_code.code] = f"{crit_def.module}.{crit_def.name}"
                context_entry = QueryCriterionMappingEntry(
                    context=context,
                    keys=system_keys
                )
                if not first:
                    fd.write(",")
                else:
                    first = False
                fd.write(context_entry.model_dump_json(exclude_none=True, exclude_unset=True))
    except Exception as x:
        _logger.error(f"Failed to generate query criterion mapping", exc_info=True)
        raise QueryCriterionMappingGenerationError("Failed to generate query criterion mapping") from x


@deprecated("Use ``generate_query_criterion_link`` instead. Future versions will prefer the separated mapping "
            "structure to reduce file size")
def contextualize_query_language_mappings(project: Project):
    """
    Generates a mapping between the contextualized term codes of the criteria and the corresponding query language
    mapping entries. The generated mapping is stored in the project as a JSON file.
    :param project: Project instance to generate the mapping for
    """
    for mapping_fp in project.output.cohort_selection.mkdirs("mappings").glob("*_mapping.json"):
        crit_def_map = {f"{mod}.{crit_def.name}": crit_def for mod, crit_defs in load_criterion_definitions(project).items() for crit_def in crit_defs}
        with mapping_fp.open(mode="r", encoding="utf-8") as fd:
            mapping = json.load(fd)
        # Overwrite the mapping file with the contextualized mapping entries
        with _json_list_file_writer(mapping_fp) as fd:
            first = True
            for mapping_entry in mapping:
                crit_def = crit_def_map[mapping_entry["name"]]
                context = crit_def.context.model_dump(exclude_none=True, exclude_unset=True)
                for term_code in _iter_crit_identifiers(project, crit_def.module, crit_def.name):
                    ctx_mapping_entry = mapping_entry.copy()
                    ctx_mapping_entry["context"] = context
                    ctx_mapping_entry["key"] = term_code.model_dump_json(exclude_none=True, exclude_unset=True)
                    ctx_mapping_entry["name"] = crit_def.name
                    if not first:
                        fd.write(",")
                    else:
                        first = False
                    fd.write(json.dumps(ctx_mapping_entry))
