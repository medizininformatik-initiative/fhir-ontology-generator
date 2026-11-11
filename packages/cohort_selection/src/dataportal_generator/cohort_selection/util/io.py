import json
from collections.abc import Mapping
from itertools import chain

import cachetools

from dataportal_generator.cohort_selection.model.concept_tree import ConceptTreeGroup
from dataportal_generator.cohort_selection.model.criterion import CriterionDefinition
from dataportal_generator.common.log.functions import get_logger
from dataportal_generator.common.model.project import Project


_logger = get_logger(__file__)


def load_criterion_definitions(project: Project) -> Mapping[str, list[CriterionDefinition]]:
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
                    _logger.debug(f"Loading criterion definition @ {fp!r}")
                    with fp.open(mode="rb") as fd:
                        crit_def = CriterionDefinition.model_validate_yaml(fd)
                        if crit_def.name in mod_crit_defs:
                            raise KeyError(f"Duplicate criterion name '{crit_def.name}' in module "
                                                             f"'{module_dir.name}'")
                        mod_crit_defs.append(crit_def)
            crit_defs[module_dir.name] = mod_crit_defs
    return crit_defs


type _CriterionMapping = Mapping[str, Mapping[str, Mapping[str, str]]]


@cachetools.cached(cache={}, key=lambda p: p.name)
def load_criterion_mapping(project: Project) -> _CriterionMapping:
    criterion_mapping = {}
    file_path = project.output.cohort_selection / "concept_trees" / "criterion_mapping.json"
    if not file_path.exists() or not file_path.is_file():
        raise FileNotFoundError(f"Missing concept tree criterion mapping file @ {file_path!r}")
    with file_path.open(mode="r", encoding="utf-8") as fd:
        criterion_mapping = json.load(fd)
    return criterion_mapping


def load_concept_tree_group(project: Project, identifier: str) -> ConceptTreeGroup:
    file_path = project.output.cohort_selection / "concept_trees" / "trees" / f"{ConceptTreeGroup.uuid_of(identifier)}.json"
    if not file_path.exists() or not file_path.is_file():
        raise FileNotFoundError(f"Missing concept tree group {identifier!r} @ {file_path!r}")
    with file_path.open(mode="rb") as fd:
        concept_tree_group = ConceptTreeGroup.model_validate_json(fd.read())
    return concept_tree_group