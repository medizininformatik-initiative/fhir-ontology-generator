import json
import shutil
import zipfile
from argparse import ArgumentParser
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from cohort_selection_ontology.model.ui_profile import UIProfile
from common.util.log.functions import get_logger
from data_selection_extraction.model.detail import ProfileDetail
from elasticsearch.model.codeable_concept_index import CodeableConceptIndexDoc
from elasticsearch.model.ontology_index import OntologyIndexDoc
from versiondiff import compare

_logger = get_logger(__file__)


def _configure_argparse() -> ArgumentParser:
    parser = ArgumentParser()
    parser.add_argument(
        "-p",
        "--prev",
        action="store",
        required=True,
        type=Path,
        help="Generator output from a lower version (file system path to directory)",
    )
    parser.add_argument(
        "-c",
        "--curr",
        action="store",
        required=True,
        type=Path,
        help="Generator output from the current/a higher version (file system path to directory)",
    )
    parser.add_argument(
        "-o",
        "--output",
        action="store",
        required=True,
        type=Path,
        help="Output directory for reports",
    )
    parser.add_argument(
        "target",
        action="store",
        nargs="*",
        choices=[
            "elasticsearch",
            "ui-profiles",
            "profile-details",
            "flattening-lookup",
        ],
        help="Types of output data to generate diff for. If none is supplied then diffs are generated for all types",
    )
    return parser


def _unpack_archive(path: Path) -> Path:
    dst = path / "data"
    dst.mkdir(parents=True, exist_ok=True)
    for zip_file_path in path.glob("*.zip"):
        _logger.debug("Unpacking archive @ %s", zip_file_path)
        with zipfile.ZipFile(zip_file_path, "r") as zip_file:
            zip_file.extractall(path=dst)
    return dst


def _cleanup(prev_dst: Path, curr_dst: Path):
    _logger.debug("Cleaning up unpacked data")
    shutil.rmtree(prev_dst.absolute(), ignore_errors=True)
    shutil.rmtree(curr_dst.absolute(), ignore_errors=True)


T = TypeVar("T", bound=BaseModel)


def _load_elasticsearch_docs(path: Path, prefix: str, t: type[T]) -> Mapping[str, T]:
    mapping = {}
    for file_path in path.glob(f"**/{prefix}*.ndjson"):
        _logger.debug("Loading docs from elasticsearch file @ %s", file_path)
        with file_path.open(mode="rb") as fd:
            for header_line, doc_line in zip(fd, fd):
                if not doc_line: # Last line is empty
                    break
                header = json.loads(header_line)
                entry_hash = header["index"]["_id"]
                doc_json = json.loads(doc_line)
                doc_json["hash"] = entry_hash
                doc = t.model_validate(doc_json)
                mapping[entry_hash] = doc
    return mapping


def _iter_elasticsearch_docs(path: Path, prefix: str) -> Iterator[Mapping[str, Any]]:
    for file_path in path.glob(f"**/{prefix}*.ndjson"):
        _logger.debug("Loading docs from elasticsearch file @ %s", file_path)
        with file_path.open(mode="rb") as fd:
            for header_line, doc_line in zip(fd, fd):
                if not doc_line: # Last line is empty
                    break
                header = json.loads(header_line)
                entry_hash = header["_id"]
                doc_json = json.loads(doc_line)
                doc_json["hash"] = entry_hash
                yield doc_json


# TODO: Add handling of doc-level additions
def _compare_elasticsearch_codeable_concept_docs(prev: Path, curr: Path, out: Path):
    prefix = "onto_es__codeable_concept"
    curr_docs = _load_elasticsearch_docs(
        curr / "elastic" / "content", prefix, CodeableConceptIndexDoc
    )
    # TODO: The current version on prod uses the old layout. This has to be changed once versions >= 5.x.x run on prod
    report_path = out / "elasticsearch" / "codeable_concept_index_docs.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open(mode="w") as fd:
        fd.write('{"changes":[')
        first = True
        for prev_doc in _iter_elasticsearch_docs(prev / "elastic", prefix):
            curr_doc = curr_docs.get(prev_doc["hash"])
            if changes := compare(prev_doc, curr_doc, CodeableConceptIndexDoc).changes:
                for change in changes:
                    if not first:
                        fd.write(",")
                    else:
                        first = False
                    fd.write(change.model_dump_json(exclude_none=True))
        fd.write("]}")


def _compare_elasticsearch_ontology_docs(prev: Path, curr: Path, out: Path):
    prefix = "onto_es__ontology"
    curr_docs = _load_elasticsearch_docs(
        curr / "elastic" / "content", prefix, OntologyIndexDoc
    )
    updated = set()
    # TODO: The current version on prod uses the old layout. This has to be changed once versions >= 5.x.x run on prod
    report_path = out / "elasticsearch" / "ontology_index_docs.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open(mode="w") as fd:
        fd.write('{"changes":[')
        first = True
        for prev_doc in _iter_elasticsearch_docs(prev / "elastic", prefix):
            curr_doc = curr_docs.get(prev_doc["hash"])
            updated.add(curr_doc.hash)
            if changes := compare(prev_doc, curr_doc, OntologyIndexDoc).changes:
                for change in changes:
                    if not first:
                        fd.write(",")
                    else:
                        first = False
                    fd.write(change.model_dump_json(exclude_none=True))
        fd.write("]}")


def _iter_sql_dump(sql_dump_path: Path, table_name: str) -> Iterator[str]:
    _logger.debug("Loading table %s from SQL dump file @ %s", table_name, sql_dump_path)
    with sql_dump_path.open(mode="r", encoding="utf-8") as fd:
        for line in fd:
            if line.startswith(f"COPY public.{table_name}"):
                for line in fd:
                    if line.startswith("\\."):
                        break
                    # Always accessing the third column works for now
                    yield line.strip().split("\t")[2].replace("\\n    ", "").replace("\\n", "")


def _compare_ui_profiles(prev: Path, curr: Path, out: Path):
    file_name = "R__Load_latest_ui_profile.sql"
    prev_data = [json.loads(row) for row in _iter_sql_dump(prev / file_name, "ui_profile")]
    curr_data = [
        UIProfile.model_validate_json(row)
        for row in _iter_sql_dump(curr / file_name, "ui_profile")
    ]
    report = compare(prev_data, curr_data, model=list[UIProfile])
    out.mkdir(parents=True, exist_ok=True)
    with (out / "ui_profiles.json").open(mode="w", encoding="utf-8") as fd:
        fd.write(report.model_dump_json(exclude_none=True))


def _compare_profile_details(prev: Path, curr: Path, out: Path):
    file_name = "R__load_latest_dse_profiles.sql"
    prev_data = [row for row in _iter_sql_dump(prev / file_name, "dse_profile")]
    curr_data = [
        ProfileDetail.model_validate_json(row)
        for row in _iter_sql_dump(curr / file_name, "dse_profile")
    ]
    report = compare(prev_data, curr_data, model=list[ProfileDetail])
    out.mkdir(parents=True, exist_ok=True)
    with (out / "dse_profiles.json").open(mode="w", encoding="utf-8") as fd:
        fd.write(report.model_dump_json(exclude_none=True))


def _compare_flattening_lookup(prev: Path, curr: Path, out: Path):
    # TODO
    pass


if __name__ == "__main__":
    parser = _configure_argparse()
    args = parser.parse_args()

    prev = args.prev
    curr = args.curr
    out = args.output
    targets = getattr(args, "target", None)

    _logger.debug("Unpacking archives")
    prev = _unpack_archive(prev)
    curr = _unpack_archive(curr)
    
    try:
        _logger.info("Generating diff reports")
        if not targets or "elasticsearch" in targets:
            _logger.info("Generating diff for Elasticsearch files")
            _compare_elasticsearch_codeable_concept_docs(prev, curr, out)
            _compare_elasticsearch_ontology_docs(prev, curr, out)
        if not targets or "ui-profiles" in targets:
            _logger.info("Generating diff for UI profiles")
            _compare_ui_profiles(prev, curr, out)
        if not targets or "profile-details" in targets:
            _logger.info("Generating diff for profile details")
            _compare_profile_details(prev, curr, out)
        if not targets or "flattening-lookup" in targets:
            _logger.info("Generating diff for flattening lookup")
            _compare_flattening_lookup(prev, curr, out)
    finally:
        _cleanup(prev, curr)
