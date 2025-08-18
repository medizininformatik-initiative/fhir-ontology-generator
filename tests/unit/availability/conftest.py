import functools
import os.path
from pathlib import Path

import pytest
from _pytest.python import Metafunc
from fhir.resources.R4B.codeableconcept import CodeableConcept
from fhir.resources.R4B.coding import Coding
from fhir.resources.R4B.elementdefinition import ElementDefinition
from fhir.resources.R4B.expression import Expression
from fhir.resources.R4B.measure import MeasureGroupStratifier
from fhir.resources.R4B.structuredefinition import StructureDefinition

from availability.constants.fhir import MII_CDS_PACKAGE_PATTERN
from common.exceptions import NotFoundError
from common.model.fhir.structure_definition import StructureDefinitionSnapshot
from common.util.fhir.package.manager import FhirPackageManager
from common.util.fhir.structure_definition import get_parent_elem_id
from common.util.project import Project

TEST_PROFILE_URL = "https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Specimen"


def _project() -> Project:
    return Project(path=Path(os.path.dirname(__file__)))


@pytest.fixture(scope="session")
def project() -> Project:
    return _project()


@functools.cache
def _package_manager() -> FhirPackageManager:
    pm = _project().package_manager
    pm.restore(inflate=True)
    return pm


@pytest.fixture(scope="session")
def package_manager() -> FhirPackageManager:
    return _package_manager()


@pytest.fixture(scope="session")
def test_profile(package_manager: FhirPackageManager) -> StructureDefinitionSnapshot:
    idx_pattern = {"url": TEST_PROFILE_URL}
    if p := package_manager.find(idx_pattern) is not None:
        return p
    else:
        raise NotFoundError(
            f"Cannot find structure definition of test profile '{idx_pattern['url']}'"
        )


@pytest.fixture
def profile(request, package_manager: FhirPackageManager):
    """
    Fixture that can be used for indirect parameters named 'profile' to resolve any `string` typed value as a
    profile URL or pass on any `StructureDefinition` typed parameters
    """
    match request.param:
        case str() as profile_url:
            return package_manager.find({"url": profile_url})
        case StructureDefinition() as struct_def:
            return struct_def
        case _ as param:
            raise ValueError(
                f"Fixture 'profile' does not support indirect parameters of type {type(param)} [supported_types=[{type(str)}, {type(StructureDefinition)}]]"
            )


@pytest.fixture
def elem_def(request, profile):
    """
    Fixture that can be used for indirect parameters named 'elem_def' to resolve any `string` typed value as a
    profile URL or pass on any `ElementDefinition` typed parameters
    """
    match request.param:
        case str() as elem_id:
            return profile.get_element_by_id(elem_id)
        case ElementDefinition() as elem_def:
            return elem_def
        case _ as param:
            raise ValueError(
                f"Fixture 'elem_def' does not support indirect parameters of type {type(param)} [supported_types=[{type(str)}, {type(ElementDefinition)}]]"
            )


def pytest_generate_tests(metafunc: Metafunc):
    """
    Generates tests dynamically based on the collected querying metadata files within the project directory
    """
    manager = _package_manager()
    snapshot = manager.find({"url": TEST_PROFILE_URL})

    if (
        "test__append_filter_from_profile_discriminated_elem"
        == metafunc.definition.name
    ):
        test_elems = [
            (
                "Specimen.extension:festgestellteDiagnose",
                "Specimen.extension",
                "Specimen.extension('https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Diagnose')",
            ),
            (
                "Specimen.container.additive[x]:additiveReference",
                "Specimen.container.additive",
                "Specimen.container.additive.where($this.resolve().meta.profile.exists($this = 'https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Substance'))",
            ),
        ]
        test_data = []
        ids = []
        for elem_id, base_expr, expected in test_elems:
            elem_def = snapshot.get_element_by_id(elem_id)
            parent_elem_def = snapshot.get_element_by_id(get_parent_elem_id(elem_def))
            test_data.append(
                pytest.param(
                    base_expr,
                    elem_def,
                    parent_elem_def.slicing.discriminator[0],
                    snapshot,
                    manager,
                    expected,
                )
            )
            ids.append(f"{snapshot.name}::{elem_id}")
        metafunc.parametrize(
            argnames=(
                "base_expr",
                "elem_def",
                "discr",
                "snapshot",
                "manager",
                "expected",
            ),
            argvalues=test_data,
            ids=ids,
            scope="session",
        )

    if (
        "test__get_filter_from_pattern_or_value_discriminated_elem"
        == metafunc.definition.name
    ):
        test_elems = [
            (
                "pattern_slicing_with_pattern_and_no_indirection",
                "https://www.medizininformatik-initiative.de/fhir/core/modul-person/StructureDefinition/Patient",
                "Patient.address:Postfach",
                "where(type = 'postal')",
            ),
            (
                "value_slicing_with_fixed_and_indirection_len_1",
                "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
                "Encounter.extension:Aufnahmegrund.extension:DritteStelle",
                "where(url = 'DritteStelle')",
            ),
            (
                "value_slicing_with_fixed_and_indirection_len_2",
                "https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Specimen",
                "Specimen.processing:lagerprozess",
                "where(procedure.coding.exists(system = 'http://snomed.info/sct' and code = '1186936003'))",
            ),
            (
                "pattern_slicing_with_binding_and_no_indirection",
                "https://www.medizininformatik-initiative.de/fhir/core/modul-person/StructureDefinition/Vitalstatus",
                "Observation.value[x].coding:Vitalstatus",
                "where(memberOf('https://www.medizininformatik-initiative.de/fhir/core/modul-person/ValueSet/Vitalstatus'))",
            ),
        ]
        test_data = []
        ids = []
        for test_id, snapshot_url, elem_id, expected in test_elems:
            snapshot = manager.find({"url": snapshot_url}, MII_CDS_PACKAGE_PATTERN)
            elem_def = snapshot.get_element_by_id(elem_id)
            discr_path = (
                snapshot.get_element_by_id(get_parent_elem_id(elem_def))
                .slicing.discriminator[0]
                .path.replace("$this.", "")
            )
            test_data.append(
                pytest.param(
                    elem_def,
                    discr_path,
                    snapshot,
                    expected,
                )
            )
            ids.append(test_id)
        metafunc.parametrize(
            argnames=("elem_def", "discr_path", "snapshot", "expected"),
            argvalues=test_data,
            ids=ids,
            scope="session",
        )

    # if "test__append_filter_for_slice" == metafunc.definition.name:
    #    test_elems = [
    #        (
    #            "pattern_slicing_with_pattern_in_subelement",
    #            "Specimen.processing",
    #            "Specimen.processing:lagerprozess",
    #            "Specimen.processing.where(procedure.coding.exists(system = 'http://snomed.info/sct' and code = '1186936003'))",
    #        ),
    #        (
    #            "type_slicing",
    #            "Specimen.collection.fastingStatus",
    #            "Specimen.collection.fastingStatus[x]:fastingStatusCodeableConcept",
    #            "Specimen.collection.fastingStatus.ofType(CodeableConcept)",
    #        ),
    #        (
    #            ""
    #        )
    #        # TODO: Add examples for discriminator types 'exists', 'value', and 'profile'. ATM there are no examples in
    #        #       the MII CDS profiles
    #    ]
    #    test_data = []
    #    ids = []
    #    for test_id, base_expr, elem_id, expected in test_elems:
    #        elem_def = snapshot.get_element_by_id(elem_id)
    #        test_data.append(
    #            pytest.param(
    #                base_expr,
    #                elem_def,
    #                snapshot,
    #                manager,
    #                expected,
    #            )
    #        )
    #        ids.append(test_id)
    #    metafunc.parametrize(
    #        argnames=("base_expr", "slice_elem_def", "snapshot", "manager", "expected"),
    #        argvalues=test_data,
    #        ids=ids,
    #        scope="session",
    #    )

    # if "test__generate_stratifiers_for_extension_elements" == metafunc.definition.name:
    #     test_elems = [
    #         (
    #             "extension-with-valueDateTime",
    #             "https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/EinstellungBlutversorgung",
    #             "Specimen.extension('https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/EinstellungBlutversorgung')",
    #             ["Specimen.collection:einstellungBlutversorgung"],
    #             [
    #                 (
    #                     "Specimen.collection:einstellungBlutversorgung.valueDateTime",
    #                     "Specimen.collection.extension('https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/EinstellungBlutversorgung').value.ofType(dateTime).hasValue()",
    #                 ),
    #             ],
    #             [],
    #         ),
    #         (
    #             "extension-with-valueReference",
    #             "https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Diagnose",
    #             "Specimen.extension('https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Diagnose')",
    #             ["Specimen.extension:festgestellteDiagnose"],
    #             [
    #                 (
    #                     "Specimen.extension:festgestellteDiagnose.valueReference->Condition",
    #                     "Specimen.extension('https://www.medizininformatik-initiative.de/fhir/ext/modul-biobank/StructureDefinition/Diagnose').value.ofType(Reference).resolve().ofType(Condition).meta.profile.exists($this = 'http://hl7.org/fhir/StructureDefinition/Condition' or $this = 'https://www.medizininformatik-initiative.de/fhir/core/modul-person/StructureDefinition/Todesursache' or $this = 'https://www.medizininformatik-initiative.de/fhir/core/modul-diagnose/StructureDefinition/Diagnose')",
    #                 ),
    #             ],
    #             pytest.mark.skip(
    #                 "Reference stratification by supported profiles is currently disabled"
    #             ),
    #         ),
    #     ]
    #     test_data = []
    #     ids = []
    #     for test_id, ext_url, base_expr, chained_elem_id, expected, marks in test_elems:
    #         ext_snapshot = manager.find({"url": ext_url})
    #         expected = [
    #             MeasureGroupStratifier(
    #                 criteria=Expression(language="text/fhirpath", expression=expr),
    #                 code=CodeableConcept(
    #                     coding=[
    #                         Coding(
    #                             system="http://fhir-data-evaluator/strat/system",
    #                             code=strat_id,
    #                         )
    #                     ]
    #                 ),
    #             )
    #             for strat_id, expr in expected
    #         ]
    #         test_data.append(
    #             pytest.param(
    #                 ext_snapshot,
    #                 base_expr,
    #                 manager,
    #                 chained_elem_id,
    #                 expected,
    #                 marks=marks,
    #             )
    #         )
    #         ids.append(test_id)
    #     metafunc.parametrize(
    #         argnames=(
    #             "ext_snapshot",
    #             "base_expr",
    #             "manager",
    #             "chained_elem_id",
    #             "expected",
    #         ),
    #         argvalues=test_data,
    #         ids=ids,
    #         scope="session",
    #     )
