import subprocess
import warnings
from pathlib import Path

import requests
from fhir.resources.R4B.measure import Measure
from fhir.resources.R4B.measurereport import MeasureReport
from fhir.resources.R4B.bundle import Bundle
from pydantic import ValidationError

from common.util.fhirpath import parse_expr
from common.util.log.functions import get_logger
from common.util.test.docker import save_docker_logs

_logger = get_logger(__name__)


# TODO: Only restart fhir-data-evaluator container for each measure and not the entire project
def run_fhir_data_evaluator(test_dir: Path, test_data_bundle: Bundle):
    try:
        subprocess.check_output(
            ["docker", "compose", "up", "--wait", "fhir-server"], cwd=test_dir
        )
        requests.post(
            url="http://localhost:8182/fhir",
            data=test_data_bundle.model_dump_json().encode("utf-8"),
            headers={"Content-Type": "application/fhir+json"},
        ).raise_for_status()
        subprocess.check_output(
            ["docker", "compose", "run", "--rm", "fhir-data-evaluator"],
            cwd=test_dir,
        )
    finally:
        save_docker_logs(str(test_dir), "integration-test_dse-element-availability")
        subprocess.check_output(["docker", "compose", "down", "-v"], cwd=test_dir)


def test_stratifier_fhirpath_expression_validity(measure: Measure):
    for grp in measure.group:
        for strat in grp.stratifier:
            try:
                expr_str = strat.criteria.expression
                parse_expr(expr_str)
            except Exception as exc:
                raise Exception(
                    f"Failed to parse FHIRPath expression of stratifier '{strat.id}' in group '{grp.id}'"
                ) from exc


def test_measure_compatability_with_fde(measure: Measure):
    ids = set()
    fde_codes = set()
    errors = list()
    for grp in measure.group:
        criteria = set()
        for strat in grp.stratifier:
            # Stratifier IDs
            try:
                assert strat.id not in ids, "All stratifiers should have a unique ID"
                ids.add(strat.id)
            except AssertionError as err:
                errors.append(err)
            # Stratifier FDE coding
            try:
                fde_codings = list(
                    filter(
                        lambda c: c.system == "http://fhir-data-evaluator/strat/system",
                        strat.code.coding,
                    )
                )
                assert (
                    len(fde_codings) == 1
                ), f"Exactly one FDE stratifier coding should be present (group: {repr(grp.id)}, stratifier: {strat.id})"
                fde_code = fde_codings[0].code
                assert (
                    fde_code not in fde_codes
                ), "All stratifiers should have a unique FDE code"
                fde_codes.add(fde_codings[0].code)
            except AssertionError as err:
                errors.append(err)
            # Stratifier criteria
            try:
                c = strat.criteria
                assert (
                    c is not None
                    and c.language == "text/fhirpath"
                    and c.expression is not None
                ), "Stratifier should have a FHIRPath criterion"
                assert (
                    c.expression not in criteria
                ), "All stratifiers of a group should have a unique FHIRPath expression"
                criteria.add(c.expression)
            except AssertionError as err:
                errors.append(err)
    if errors:
        raise ExceptionGroup(
            f"Measure {repr(measure.name)} is not compatible with FDE", errors
        )


def test_generating_measure_report(
    measure: Measure,
    tmp_dir: Path,
    test_dir: Path,
    test_data_bundle: Bundle,
):
    with (tmp_dir / "input" / "measure.json").open(mode="w+", encoding="utf-8") as f:
        f.write(measure.model_dump_json(indent=4))
    run_fhir_data_evaluator(test_dir, test_data_bundle)
    report_file = next((tmp_dir / "output").glob("**/measure-report.json"), None)
    assert (
        report_file.exists() and report_file.is_file()
    ), "A measure report file should be generated"
    # Test measure report validity
    with report_file.open(mode="r", encoding="utf-8") as f:
        try:
            MeasureReport.model_validate_json(f.read())
        except ValidationError:
            warnings.warn(
                "Ignoring failing validation of MeasureReport due to issue in `fhir-data-evaluator`"
            )
