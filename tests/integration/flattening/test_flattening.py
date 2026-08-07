import os
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Mapping

from common.model.fhir.structure_definition import StructureDefinitionSnapshot
from common.util.collections.functions import first
from flattening.core.flattening import check_if_root
from flattening.model.FlatteningLookupModels import (
    FlatteningLookup,
    FlatteningLookupListTA,
    FlatteningLookupElement,
)

_TMP_JOBS_DIR = Path(__file__).parent / ".tmp" / "jobs"


def _run_aether(
    aether_tool_path: Path, pipeline_config_path: Path, crtdl_file_path: Path
):
    subprocess.check_output(
        [
            str(aether_tool_path.absolute()),
            "pipeline",
            "start",
            str(pipeline_config_path.absolute()),
            str(crtdl_file_path.absolute()),
        ],
        cwd=str(Path(__file__).parent),
    )


def _actual() -> tuple[list[Path], list[Path]]:
    result_dir = sorted(
        [p for p in _TMP_JOBS_DIR.iterdir() if p.is_dir()], key=lambda p: p.name
    )[0]
    return (
        [p for p in (result_dir / "csv").iterdir() if p.is_file()],
        [p for p in (result_dir / "viewdefinitions").iterdir() if p.is_file()],
    )


def _assert_csv_tables_are_equal(actual_t: str, expected_t: str):
    actual_t_lines = actual_t.split(os.linesep)
    expected_t_lines = expected_t.split(os.linesep)

    errors = []

    actual_th = actual_t_lines[0]
    expected_th = expected_t_lines[0]
    try:
        assert actual_th == expected_th, "Tables must have the same header"
    except Exception as exc:
        errors.append(exc)

    actual_tr = sorted(actual_t_lines[1:], key=lambda s: s.split(",", 1)[0])
    expected_tr = sorted(expected_t_lines[1:], key=lambda s: s.split(",", 1)[0])
    for idx, (actual_row, expected_row) in enumerate(zip(actual_tr, expected_tr)):
        try:
            assert actual_row == expected_row, f"Difference in row {idx + 1}"
        except Exception as exc:
            errors.append(exc)
    if errors:
        raise ExceptionGroup("Tables are not equal", errors)


def test_extraction_pipeline(
    crtdl,
    expected,
    aether,
    flattening_lookup,
    pipeline_config,
    fhir_server_url,
    jobs_dir,
):
    _run_aether(aether, pipeline_config, crtdl)
    actual_csv_d, actual_view_defs_d = _actual()
    expected_csv_d, expected_view_defs_d = expected

    assert set(p.name for p in actual_csv_d) == set(
        p.name for p in expected_csv_d
    ), "The expected tables have to be generated"

    assert set(p.name for p in actual_view_defs_d) == set(
        p.name for p in expected_view_defs_d
    ), "The expected view definitions have to be generated"

    for actual_p in actual_csv_d:
        expected_p = first(lambda p: p.name == actual_p.name, expected_csv_d)
        with actual_p.open(mode="r", encoding="utf-8") as f:
            actual_data = f.read()
        with expected_p.open(mode="r", encoding="utf-8") as f:
            expected_data = f.read()
        _assert_csv_tables_are_equal(actual_data, expected_data)

    for actual_p in actual_view_defs_d:
        expected_p = first(lambda p: p.name == actual_p.name, expected_view_defs_d)
        with actual_p.open(mode="r", encoding="utf-8") as f:
            actual_data = f.read()
        with expected_p.open(mode="r", encoding="utf-8") as f:
            expected_data = f.read()
        assert actual_data == expected_data


def _construct_fhirpaths(
    elem_id: str,
    elem: FlatteningLookupElement,
    child_to_parent: Mapping[str, list[str]],
    lookup: FlatteningLookup,
) -> list[str]:
    fhirpath_exprs = list()
    if parent_ids := child_to_parent.get(elem_id):
        if len(parent_ids) > 1:
            raise ValueError(
                f"Cannot construct FHIRPath expressions for lookup element {repr(elem_id)} since it has multiple parent elements"
            )
        parent_id = parent_ids[0]
        prefixes = _construct_fhirpaths(
            parent_id, lookup.elements[parent_id], child_to_parent, lookup
        )
    else:
        prefixes = []
    if vd := elem.view_definition:
        if foreach_filter := vd.for_each_or_null:
            prefixes = (
                [f"{prefix}.{foreach_filter}" for prefix in prefixes]
                if prefixes
                else [foreach_filter]
            )
        if columns := vd.column:
            for c in columns:
                fhirpath_exprs.extend(f"{prefix}.{c}" for prefix in prefixes)
        else:
            fhirpath_exprs = prefixes
    else:
        fhirpath_exprs = prefixes
    return fhirpath_exprs


def _assert_lookup_validity(
    lookup: FlatteningLookup, struct_def: StructureDefinitionSnapshot
):
    errors = []
    child_to_parent = defaultdict(list)
    expr_to_elem = defaultdict(list)
    for elem_id, elem in lookup.elements.items():
        if children := getattr(elem, "children", []):
            for child_id in children:
                child_to_parent[child_id].append(elem_id)

    for child_id, parents in child_to_parent.items():
        elem_errors = []
        try:
            assert (
                child_id in lookup.elements
            ), f"Child ID {repr(child_id)} should point to an existing element"
        except AssertionError as err:
            elem_errors.append(err)
        try:
            assert (
                len(parents) == 1
            ), f"Lookup element {repr(child_id)} has more than one parent"
            child = lookup.elements[child_id]
            if not child.children:
                exprs = _construct_fhirpaths(child_id, child, child_to_parent, lookup)
                assert (
                    len(exprs) >= 1
                ), f"A leaf element should be translatable into a FHIRPath expression"
                for expr in exprs:
                    expr_to_elem[expr].append(child_id)
        except AssertionError as err:
            elem_errors.append(err)
        parent_id = parents[0] if parents else None
        if not parent_id:
            try:
                assert check_if_root(
                    parent_id, struct_def
                ), "Only root elements do not have a parent"
            except AssertionError as err:
                elem_errors.append(err)
        else:
            try:
                assert child_id.startswith(
                    parent_id
                ), f"Child ID {repr(child_id)} should be an actual subpath of the parent lookup element {repr(parent_id)}"
                assert (
                    child_id != parent_id
                ), f"Child ID {repr(child_id)} cannot be equal to its parents ID {repr(parent_id)}"
            except AssertionError as err:
                errors.append(err)

        if elem_errors:
            errors.append(
                ExceptionGroup(
                    f"Lookup element {repr(elem_id)} is invalid", elem_errors
                )
            )

    expr_errors = []
    for expr, elems in expr_to_elem.items():
        try:
            assert (
                len(elems) <= 1
            ), f'Lookup elements {repr(elems)} resolve to the same FHIRPath expression: "{expr}"'
        except AssertionError as err:
            expr_errors.append(err)
    if expr_errors:
        errors.append(
            ExceptionGroup(
                "Resolved FHIRPath expression of leaf elements are not unique",
                expr_errors,
            )
        )

    if errors:
        raise ExceptionGroup(
            f"Lookup for profile {repr(lookup.url)} is invalid", errors
        )


def test_lookup_file_validity(flattening_lookup: Path, package_manager):
    with flattening_lookup.open(mode="r", encoding="utf-8") as f:
        flattening_lookups = FlatteningLookupListTA.validate_json(f.read())
    errors = []
    for lookup in flattening_lookups:
        struct_def = package_manager.find({"url": lookup.url})
        try:
            _assert_lookup_validity(lookup, struct_def)
        except Exception as exc:
            errors.append(exc)
    if errors:
        raise ExceptionGroup(f"Flattening lookup file is invalid", errors)
