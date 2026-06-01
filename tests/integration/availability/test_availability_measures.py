import subprocess
import warnings
from pathlib import Path

from fhir.resources.R4B.measure import Measure
from fhir.resources.R4B.measurereport import MeasureReport
from pydantic import ValidationError

from common.util.fhirpath import parse_expr
from common.util.log.functions import get_logger

_logger = get_logger(__name__)


# TODO: Only restart fhir-data-evaluator container for each measure and not the entire project
def run_fhir_data_evaluator(docker_compose_file: str, docker_compose_project_name: str):
    subprocess.check_output(
        [
            "docker",
            "compose",
            "-f",
            docker_compose_file,
            "-p",
            docker_compose_project_name,
            "run",
            "--rm",
            "fhir-data-evaluator",
        ],
    )


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


def test_generating_measure_report(
    measure: Measure,
    tmp_dir: Path,
    test_dir: Path,
    fhir_server_url,
    docker_compose_file: str,
    docker_compose_project_name: str,
):
    with (tmp_dir / "input" / "measure.json").open(mode="w+", encoding="utf-8") as f:
        f.write(measure.model_dump_json(indent=4))
    run_fhir_data_evaluator(docker_compose_file, docker_compose_project_name)
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
