import json
import zipfile
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import cachetools

from cohort_selection_ontology.model.tree_map import (
    ContextualizedTermCodeInfo,
    ContextualizedTermCodeInfoList,
    TermEntryNode,
    TreeMap,
    TreeMapList,
)
from cohort_selection_ontology.model.ui_data import Module, TermCode
from common.util.log.functions import get_logger
from common.util.project import Project

_logger = get_logger(__name__)


@cachetools.cached(cache={}, key=lambda p: p.path.absolute())
def _prepare_elasticsearch_data(project: Project):
    restore_archive_path = project / "input" / "restore" / "elastic.zip"
    if not restore_archive_path.is_file():
        raise FileNotFoundError(f"Missing Elasticsearch archive to restore from @ {restore_archive_path!r}")
    restore_data_path = project.mkdirs(".tmp", "restore", "terminology")
    _logger.info("Unpacking Elasticsearch data for restoration")
    with zipfile.ZipFile(restore_archive_path, mode="r") as zip_ref:
        zip_ref.extractall(restore_data_path)


# Module -> context code -> code system URL -> code system version -> code -> info
type TermCodeIndex = Mapping[Mapping, Mapping[str, Mapping[str, Mapping[str, Mapping[str, Mapping[str, Any]]]]]]


def _iter_elasticsearch_docs(path: Path, prefix: str) -> Iterator[Mapping[str, Any]]:
    for file_path in path.glob(f"**/{prefix}*"):
        _logger.debug("Loading docs from elasticsearch file @ %s", file_path)
        with file_path.open(mode="rb") as fd:
            for header_line, doc_line in zip(fd, fd):
                if not doc_line:  # Last line is empty
                    break
                header = json.loads(header_line)
                entry_hash = header["index"]["_id"]
                doc_json = json.loads(doc_line)
                doc_json["hash"] = entry_hash
                yield doc_json


_INCLUDE_KEYS = {"criteria_sets", "display", "parents", "children"}


def _build_termcode_index(dir_path: Path, project: Project) -> Mapping[str, Any]:
    _prepare_elasticsearch_data(project)
    index = {}
    for entry in _iter_elasticsearch_docs(dir_path, prefix="onto_es__ontology"):
        module = entry["kds_module"]
        if module in index:
            context_index = index[module]
        else:
            context_index = {}
            index[module] = context_index
        context_code = entry["context"]["code"]
        if context_code in context_index:
            context_entry = context_index[context_code]
        else:
            context_entry = {"context": entry["context"], "entries": {}}
            context_index[context_code] = context_entry
        system_index = context_entry["entries"]
        term_code = entry["termcodes"][0]
        system = term_code["system"]
        version = term_code["version"]
        code = term_code["code"]
        if system in system_index:
            version_index = system_index[system]
        else:
            version_index = {}
            system_index[system] = version_index
        if version in version_index:
            code_index = version_index[version]
        else:
            code_index = {}
            version_index[version] = code_index
        code_index[code] = {k: v for k, v in entry.items() if k in _INCLUDE_KEYS}
    return index


@cachetools.cached(cache={}, key=lambda p: p.path.absolute())
def _load_termcode_index(project: Project) -> Mapping[str, Any]:
    index_file_path = project.mkdirs(".tmp", "restore", "terminology") / "termcode_index.json"
    if index_file_path.is_file():
        _logger.debug("Loading term code index from file @ %s", index_file_path)
        with index_file_path.open(mode="r", encoding="utf-8") as fd:
            return json.load(fd)
    _logger.debug("Building term code index")
    index = _build_termcode_index(index_file_path.parent, project)
    with index_file_path.open(mode="w", encoding="utf-8") as fd:
        json.dump(index, fd)
    return index


def restore_ui_trees(project: Project, module: Module) -> TreeMapList | None:
    index = _load_termcode_index(project)
    context_index = index.get(module.display)
    if not context_index:
        return None
    trees = []
    for context_entry in context_index.values():
        context = context_entry["context"]
        for system, version_index in context_entry["entries"].items():
            for version, code_index in version_index.items():
                entries = {}
                for code, info in code_index.items():
                    entries[code] = TermEntryNode(
                        term_code=TermCode(system=system, code=code, display=info["display"]["original"], version=version),
                        parents=[p["term_code"] for p in info.get("parents", [])],
                        children=[c["term_code"] for c in info.get("children", [])],
                    )
                trees.append(TreeMap(context=context, system=system, version=version, entries=entries))        
    return TreeMapList(entries=trees, module_name=module.display)


def restore_term_code_infos(project: Project, module: Module) -> ContextualizedTermCodeInfoList | None:
    index = _load_termcode_index(project)
    module_index = index.get(module.display)
    if not module_index:
        return None
    ctc_list = []
    for context_entry in module_index.values():
        context = context_entry["context"]
        for system, versions in context_entry["entries"].items():
            for version, codes in versions.items():
                for code, info in codes.items():
                    ctc_list.append(ContextualizedTermCodeInfo(
                        term_code=TermCode(system=system, code=code, display=info["display"]["original"], version=version),
                        context=context,
                        module=module,
                    ))
    return ContextualizedTermCodeInfoList(entries=ctc_list)


def restore_dse_value_sets(project: Project) -> list[Mapping[str, Any]]:
    dir_path = project.mkdirs(".tmp", "restore", "terminology")
    value_sets = {}
    for entry in _iter_elasticsearch_docs(dir_path, prefix="onto_es__codeable_concept"):
        for vs_url in entry["value_sets"]:
            if vs_url in value_sets:
                contains = value_sets[vs_url]["expansion"]["contains"]
            else:
                contains = []
                vs_entry = {
                    "url": vs_url,
                    "expansion": {
                        "contains": contains
                    }
                }
                value_sets[vs_url] = vs_entry
            term_code = entry["termcode"]
            contains.append({
                "system": term_code["system"],
                "code": term_code["code"],
                "display": term_code["display"]
            })
    vs_dir = project.output.dse.mkdirs("value-sets")
    for vs in value_sets.values():
        file_name = f"{urlparse(vs["url"]).path.split("/ValueSet/", 1)[-1].replace("/", "")}.json"
        with (vs_dir / file_name).open(mode="w", encoding="utf-8") as fd:
            json.dump(vs, fd)
    return list(value_sets.values())