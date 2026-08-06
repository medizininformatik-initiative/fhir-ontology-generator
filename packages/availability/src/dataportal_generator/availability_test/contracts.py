import abc
import os
import subprocess
import warnings
from pathlib import Path
from typing import Callable

from _pytest.fixtures import FixtureRequest
from fhir.resources.R4B.measure import Measure
from fhir.resources.R4B.measurereport import MeasureReport
from pydantic import ValidationError

from dataportal_generator.common.log.functions import get_logger
from dataportal_generator.common.fhirpath import parse_expr


_logger = get_logger(__name__)


def _duplicate_criteria_expression_is_allowed(
    strat_code_1: str, strat_code_2: str
) -> bool:
    """
    Duplicate expressions are only allowed between pairs of stratifiers generated from the element definition of a
    polymorphic element (e.g. ``element[x]``) that is sliced using its type. In this case there might be slice element
    definitions with a type restriction that is equivalent to a specific typed variant of the polymorphic element (e.g.
    ``elementDataType``). In these cases the same criteria expression is allowed

    :param strat_code_1: Code of first stratifier
    :param strat_code_2: Code of second stratifier
    :return: ``True`` if both on of the stratifiers represent the constellation described above and duplicate
             expressions are allowed
    """
    # Get trailing node ID
    tail_1 = strat_code_1.rsplit(".", maxsplit=1)[-1]
    tail_2 = strat_code_2.rsplit(".", maxsplit=1)[-1]
    # Check if trailing node ID (typed variant of the element) is equal to the slice name (typed slice of the element)
    if tail_1 == tail_2.rsplit(":", maxsplit=1)[-1]:
        return True
    if tail_2 == tail_1.rsplit(":", maxsplit=1)[-1]:
        return True
    return False


class MeasureContractTests(abc.ABC):
    @classmethod
    @abc.abstractmethod
    def measures(cls) -> list[Callable[[FixtureRequest], Measure]]: ...

    # TODO: Only restart fhir-data-evaluator container for each measure and not the entire project
    def run_fhir_data_evaluator(
        self,
        docker_compose_file: str,
        docker_compose_project_name: str,
        availability_tmp_dir: Path,
    ):
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
            env=dict(
                os.environ, AVAILABILITY_TMP_DIR=str(availability_tmp_dir.absolute())
            ),
        )

    def test_stratifier_fhirpath_expression_validity(self, measure: Measure):
        for grp in measure.group:
            for strat in grp.stratifier:
                try:
                    expr_str = strat.criteria.expression
                    parse_expr(expr_str)
                except Exception as exc:
                    raise Exception(
                        f"Failed to parse FHIRPath expression of stratifier '{strat.id}' in group '{grp.id}'"
                    ) from exc

    def test_measure_compatability_with_fde(self, measure: Measure):
        ids = set()
        fde_codes = set()
        errors = list()
        for grp in measure.group:
            criteria = dict()
            for strat in grp.stratifier:
                # Stratifier IDs
                try:
                    assert strat.id not in ids, (
                        "All stratifiers should have a unique ID"
                    )
                    ids.add(strat.id)
                except AssertionError as err:
                    errors.append(err)
                # Stratifier FDE coding
                try:
                    fde_codings = list(
                        filter(
                            lambda c: (
                                c.system == "http://fhir-data-evaluator/strat/system"
                            ),
                            strat.code.coding,
                        )
                    )
                    assert len(fde_codings) == 1, (
                        f"Exactly one FDE stratifier coding should be present (group: {repr(grp.id)}, stratifier: "
                        f"{strat.id})"
                    )
                    fde_code = fde_codings[0].code
                    assert fde_code not in fde_codes, (
                        f"All stratifiers should have a unique FDE code (duplicate: {fde_code})"
                    )
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
                    if c.expression in criteria.keys():
                        encountered_fde_code = criteria[c.expression]
                        if _duplicate_criteria_expression_is_allowed(
                            fde_code, encountered_fde_code
                        ):
                            _logger.debug(
                                f"Duplicate criteria expression allowed for stratifiers with codes '{fde_code}' and "
                                f"'{encountered_fde_code}'"
                            )
                        else:
                            assert False, (
                                f"All stratifiers of a group should have a unique FHIRPath expression (duplicate: "
                                f"'{c.expression}')"
                            )
                    criteria[c.expression] = fde_code
                except AssertionError as err:
                    errors.append(err)
        if errors:
            raise ExceptionGroup(
                f"Measure {repr(measure.name)} is not compatible with FDE", errors
            )

    def test_generating_measure_report(
        self,
        measure: Measure,
        availability_tmp_dir: Path,
        fhir_server_url,
        docker_compose_file: str,
        docker_compose_project_name: str,
    ):
        with (availability_tmp_dir / "input" / "measure.json").open(
            mode="w+", encoding="utf-8"
        ) as f:
            f.write(measure.model_dump_json(indent=4))
        self.run_fhir_data_evaluator(docker_compose_file, docker_compose_project_name, availability_tmp_dir)
        report_file = next(
            (availability_tmp_dir / "output").glob("**/measure-report.json"), None
        )
        assert report_file.exists() and report_file.is_file(), (
            "A measure report file should be generated"
        )
        # Test measure report validity
        with report_file.open(mode="r", encoding="utf-8") as f:
            try:
                MeasureReport.model_validate_json(f.read())
            except ValidationError:
                warnings.warn(
                    "Ignoring failing validation of MeasureReport due to issue in `fhir-data-evaluator`"
                )
