import pytest
from _pytest.python import Metafunc

from dataportal_generator.availability_test.contracts import MeasureContractTests


def pytest_generate_tests(metafunc: Metafunc):
    if not (metafunc.cls and issubclass(metafunc.cls, MeasureContractTests)):
        return

    sources = metafunc.cls.measures()

    if ("test_stratifier_fhirpath_expression_validity" == metafunc.definition.name
            or "test_measure_compatability_with_fde" == metafunc.definition.name):
        metafunc.parametrize(
            argnames=["measure"],
            argvalues=[(f,) for f in sources],
            ids=[f.__name__ for f in sources],
            indirect=["measure"],
            scope="module",
        )

    if "test_generating_measure_report" == metafunc.definition.name:
        metafunc.parametrize(
            argnames=["measure", "availability_tmp_dir", "fhir_server_url"],
            argvalues=[pytest.param(f, None, None) for f in sources],
            ids=[f.__name__ for f in sources],
            indirect=["measure", "availability_tmp_dir", "fhir_server_url"],
            scope="module",
        )


pytest_plugins = ["dataportal_generator.availability_test.fixtures"]