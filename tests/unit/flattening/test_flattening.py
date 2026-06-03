from typing import Dict

import pytest
from fhir.resources.R4B.elementdefinition import ElementDefinition

from common.model.fhir.idx_structure_definition import StructureDefinitionSnapshot
from common.util.fhir.package.manager import FhirPackageManager
from common.util.http.terminology.client import FhirTerminologyClient
from flattening.core.flattening import (
    FlatteningLookupElement,
    ViewDefinitionColumn,
    ViewDefinitionSnippet,
    flatten_primitive,
    flattening_post_process,
    ViewDefinitionSelect,
    flatten_element,
)
from tests.unit.conftest import profile, elem_def


@pytest.mark.parametrize(
    argnames="profile, elem_def ,expected",
    argvalues=[
        (
            "https://www.medizininformatik-initiative.de/fhir/core/modul-diagnose/StructureDefinition/Diagnose",
            "Condition.recordedDate",
            {
                "Condition.recordedDate": FlatteningLookupElement(
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Condition_recordedDate",
                                path="recordedDate",
                                type="dateTime",
                            )
                        ]
                    )
                ),
            },
        ),
        (
            "https://www.medizininformatik-initiative.de/fhir/core/modul-diagnose/StructureDefinition/Diagnose",
            "Condition.code.coding:icd10-gm.code",
            {
                "Condition.code.coding:icd10-gm.code": FlatteningLookupElement(
                    parent="Condition.code.coding:icd10-gm",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Condition_code_codingIcd10gm_code",
                                path="code",
                                type="code",
                            )
                        ]
                    ),
                ),
            },
        ),
        (
            "https://www.medizininformatik-initiative.de/fhir/core/modul-diagnose/StructureDefinition/Diagnose",
            "Condition.code.coding:icd10-gm.system",
            {
                "Condition.code.coding:icd10-gm.system": FlatteningLookupElement(
                    parent="Condition.code.coding:icd10-gm",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Condition_code_codingIcd10gm_system",
                                path="system",
                                type="uri",
                            )
                        ]
                    ),
                ),
            },
        ),
    ],
    ids=[
        "primitive - recordedDate: Condition.recordedDate",
        "primitive - code: Condition.code.coding:icd10-gm.code",
        "primitive - uri: Condition.code.coding:icd10-gm.system",
    ],
    indirect=["profile", "elem_def"],
)
def test_flatten_primitive(
    profile: StructureDefinitionSnapshot,
    elem_def: ElementDefinition,
    expected: Dict[str, FlatteningLookupElement],
):
    assert flatten_primitive(elem_def.id, profile) == expected


@pytest.mark.parametrize(
    argnames="profile, elem_id ,expected",
    argvalues=[
        (
            "https://www.medizininformatik-initiative.de/fhir/core/modul-prozedur/StructureDefinition/Procedure",
            "Procedure.performed[x]",
            {
                "Procedure.performed[x]": FlatteningLookupElement(
                    view_definition=ViewDefinitionSnippet(
                        select=[],
                    ),
                    children=[
                        "Procedure.performed[x]:performedDateTime",
                        "Procedure.performed[x]:performedPeriod",
                    ],
                ),
                "Procedure.performed[x]:performedDateTime": FlatteningLookupElement(
                    parent="Procedure.performed[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="performed.ofType(dateTime)",
                        select=[
                            ViewDefinitionSelect(
                                column=[
                                    ViewDefinitionColumn(
                                        name="Procedure_performed_X_Performeddatetime",
                                        path="$this",
                                        type="dateTime",
                                    )
                                ]
                            )
                        ],
                    ),
                ),
                "Procedure.performed[x]:performedPeriod": FlatteningLookupElement(
                    parent="Procedure.performed[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="performed.ofType(Period)",
                        select=[],
                    ),
                    children=[
                        "Procedure.performed[x]:performedPeriod.start",
                        "Procedure.performed[x]:performedPeriod.end",
                    ],
                ),
                "Procedure.performed[x]:performedPeriod.start": FlatteningLookupElement(
                    parent="Procedure.performed[x]:performedPeriod",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Procedure_performed_X_Performedperiod_start",
                                path="start",
                                type="dateTime",
                            )
                        ]
                    ),
                ),
                "Procedure.performed[x]:performedPeriod.end": FlatteningLookupElement(
                    parent="Procedure.performed[x]:performedPeriod",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Procedure_performed_X_Performedperiod_end",
                                path="end",
                                type="dateTime",
                            )
                        ]
                    ),
                ),
            },
        ),
        (
            "https://www.medizininformatik-initiative.de/fhir/ext/modul-icu/StructureDefinition/dauer-haemodialysesitzung",
            "Observation.effective[x]",
            {
                "Observation.effective[x]": FlatteningLookupElement(
                    view_definition=ViewDefinitionSnippet(
                        select=[],
                    ),
                    children=[
                        "Observation.effective[x]:effectiveDateTime",
                        "Observation.effective[x]:effectivePeriod",
                    ],
                ),
                "Observation.effective[x]:effectiveDateTime": FlatteningLookupElement(
                    parent="Observation.effective[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="effective.ofType(dateTime)",
                        select=[
                            ViewDefinitionSelect(
                                column=[
                                    ViewDefinitionColumn(
                                        name="Observation_effective_X_Effectivedatetime",
                                        path="$this",
                                        type="dateTime",
                                    )
                                ]
                            )
                        ],
                    ),
                ),
                "Observation.effective[x]:effectivePeriod": FlatteningLookupElement(
                    parent="Observation.effective[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="effective.ofType(Period)",
                        select=[],
                    ),
                    children=[
                        "Observation.effective[x]:effectivePeriod.start",
                        "Observation.effective[x]:effectivePeriod.end",
                    ],
                ),
                "Observation.effective[x]:effectivePeriod.start": FlatteningLookupElement(
                    parent="Observation.effective[x]:effectivePeriod",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Observation_effective_X_Effectiveperiod_start",
                                path="start",
                                type="dateTime",
                            )
                        ]
                    ),
                ),
                "Observation.effective[x]:effectivePeriod.end": FlatteningLookupElement(
                    parent="Observation.effective[x]:effectivePeriod",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Observation_effective_X_Effectiveperiod_end",
                                path="end",
                                type="dateTime",
                            )
                        ]
                    ),
                ),
            },
        ),
        (
            "https://www.medizininformatik-initiative.de/fhir/ext/modul-icu/StructureDefinition/dauer-haemodialysesitzung",
            "Observation.value[x]",
            {
                "Observation.value[x]": FlatteningLookupElement(
                    view_definition=ViewDefinitionSnippet(
                        select=[],
                    ),
                    children=[
                        "Observation.value[x]:valueQuantity",
                    ],
                ),
                "Observation.value[x]:valueQuantity": FlatteningLookupElement(
                    parent="Observation.value[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(Quantity)",
                        select=[],
                    ),
                    children=[
                        "Observation.value[x]:valueQuantity.value",
                        "Observation.value[x]:valueQuantity.code",
                        "Observation.value[x]:valueQuantity.system",
                    ],
                ),
                "Observation.value[x]:valueQuantity.value": FlatteningLookupElement(
                    parent="Observation.value[x]:valueQuantity",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Observation_value_X_Valuequantity_value",
                                path="value",
                                type="code",
                            )
                        ]
                    ),
                ),
                "Observation.value[x]:valueQuantity.code": FlatteningLookupElement(
                    parent="Observation.value[x]:valueQuantity",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Observation_value_X_Valuequantity_code",
                                path="code",
                                type="code",
                            )
                        ]
                    ),
                ),
                "Observation.value[x]:valueQuantity.system": FlatteningLookupElement(
                    parent="Observation.value[x]:valueQuantity",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Observation_value_X_Valuequantity_system",
                                path="system",
                                type="uri",
                            )
                        ]
                    ),
                ),
            },
        ),
    ],
    ids=[
        "Polymorphic time: Procedure.performed[x]",
        "Polymorphic time: Observation.effective[x]",
        "Polymorphic quantity: Observation.value[x]",
    ],
    indirect=["profile"],
)
def test_polymorphic(
    profile: StructureDefinitionSnapshot,
    elem_id: str,
    expected: Dict[str, FlatteningLookupElement],
):
    res = flattening_post_process(flatten_element(elem_id, profile))
    res = sorted(res.items(), key=lambda x: len(x[0]))
    expected = sorted(
        flattening_post_process(expected).items(), key=lambda x: len(x[0])
    )

    assert res == expected


@pytest.mark.parametrize(
    argnames="profile, elem_id ,expected",
    argvalues=[
        (
            "https://www.medizininformatik-initiative.de/fhir/ext/modul-icu/StructureDefinition/dauer-haemodialysesitzung",
            "Observation.code",
            {
                "Observation.code": FlatteningLookupElement(
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="code",
                        select=[],
                    ),
                    children=[
                        "Observation.code.coding:sct",
                        "Observation.code.coding:loinc",
                        "Observation.code.coding:IEEE-11073",
                    ],
                ),
                "Observation.code.coding:sct": FlatteningLookupElement(
                    parent="Observation.code",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="coding.where(system = 'http://snomed.info/sct')",
                        select=[],
                    ),
                    children=[
                        "Observation.code.coding:sct.system",
                        "Observation.code.coding:sct.code",
                    ],
                ),
                "Observation.code.coding:sct.system": FlatteningLookupElement(
                    parent="Observation.code.coding:sct",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Observation_code_codingSct_system",
                                path="system",
                                type="uri",
                            )
                        ]
                    ),
                ),
                "Observation.code.coding:sct.code": FlatteningLookupElement(
                    parent="Observation.code.coding:sct",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Observation_code_codingSct_code",
                                path="code",
                                type="code",
                            )
                        ]
                    ),
                ),
                "Observation.code.coding:loinc": FlatteningLookupElement(
                    parent="Observation.code",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="coding.where(system = 'http://loinc.org')",
                        select=[],
                    ),
                    children=[
                        "Observation.code.coding:loinc.system",
                        "Observation.code.coding:loinc.code",
                    ],
                ),
                "Observation.code.coding:loinc.system": FlatteningLookupElement(
                    parent="Observation.code.coding:loinc",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Observation_code_codingLoinc_system",
                                path="system",
                                type="uri",
                            )
                        ]
                    ),
                ),
                "Observation.code.coding:loinc.code": FlatteningLookupElement(
                    parent="Observation.code.coding:loinc",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Observation_code_codingLoinc_code",
                                path="code",
                                type="code",
                            )
                        ]
                    ),
                ),
                "Observation.code.coding:IEEE-11073": FlatteningLookupElement(
                    parent="Observation.code",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="coding.where(system = 'urn:iso:std:iso:11073:10101')",
                        select=[],
                    ),
                    children=[
                        "Observation.code.coding:IEEE-11073.system",
                        "Observation.code.coding:IEEE-11073.code",
                    ],
                ),
                "Observation.code.coding:IEEE-11073.system": FlatteningLookupElement(
                    parent="Observation.code.coding:IEEE-11073",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Observation_code_codingIeee11073_system",
                                path="system",
                                type="uri",
                            )
                        ]
                    ),
                ),
                "Observation.code.coding:IEEE-11073.code": FlatteningLookupElement(
                    parent="Observation.code.coding:IEEE-11073",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Observation_code_codingIeee11073_code",
                                path="code",
                                type="code",
                            )
                        ]
                    ),
                ),
            },
        ),
        (
            "https://www.medizininformatik-initiative.de/fhir/core/modul-labor/StructureDefinition/ObservationLab",
            "Observation.code",
            {
                "Observation.code": FlatteningLookupElement(
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="code",
                        select=[],
                    ),
                    children=[
                        "Observation.code.coding",
                    ],
                ),
                "Observation.code.coding": FlatteningLookupElement(
                    parent="Observation.code",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="coding",
                        column=[
                            ViewDefinitionColumn(
                                name="Observation_code_coding_system",
                                path="system",
                            ),
                            ViewDefinitionColumn(
                                name="Observation_code_coding_code",
                                path="code",
                            ),
                        ],
                    ),
                ),
            },
        ),
        (
            "https://www.medizininformatik-initiative.de/fhir/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
            "Encounter.diagnosis.use",
            {
                "Encounter.diagnosis.use": FlatteningLookupElement(
                    parent="Encounter.diagnosis",
                    viewDefinition=ViewDefinitionSnippet(
                        forEachOrNull="use", select=[]
                    ),
                    children=[
                        "Encounter.diagnosis.use.coding:Diagnosetyp",
                        "Encounter.diagnosis.use.coding:DiagnosesubTyp",
                    ],
                ),
                "Encounter.diagnosis.use.coding:Diagnosetyp.code": FlatteningLookupElement(
                    parent="Encounter.diagnosis.use.coding:Diagnosetyp",
                    viewDefinition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Encounter_diagnosis_use_codingDiagnosetyp_code",
                                path="code",
                                type="code",
                            )
                        ]
                    ),
                ),
                "Encounter.diagnosis.use.coding:Diagnosetyp.system": FlatteningLookupElement(
                    parent="Encounter.diagnosis.use.coding:Diagnosetyp",
                    viewDefinition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Encounter_diagnosis_use_codingDiagnosetyp_system",
                                path="system",
                                type="uri",
                            )
                        ]
                    ),
                ),
                "Encounter.diagnosis.use.coding:Diagnosetyp": FlatteningLookupElement(
                    parent="Encounter.diagnosis.use",
                    viewDefinition=ViewDefinitionSnippet(
                        forEachOrNull="coding.where(code = 'referral-diagnosis' or code = 'treatment-diagnosis')",
                        select=[],
                    ),
                    children=[
                        "Encounter.diagnosis.use.coding:Diagnosetyp.code",
                        "Encounter.diagnosis.use.coding:Diagnosetyp.system",
                    ],
                ),
                "Encounter.diagnosis.use.coding:DiagnosesubTyp.code": FlatteningLookupElement(
                    parent="Encounter.diagnosis.use.coding:DiagnosesubTyp",
                    viewDefinition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Encounter_diagnosis_use_codingDiagnosesubtyp_code",
                                path="code",
                                type="code",
                            )
                        ]
                    ),
                ),
                "Encounter.diagnosis.use.coding:DiagnosesubTyp.system": FlatteningLookupElement(
                    parent="Encounter.diagnosis.use.coding:DiagnosesubTyp",
                    viewDefinition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Encounter_diagnosis_use_codingDiagnosesubtyp_system",
                                path="system",
                                type="uri",
                            )
                        ]
                    ),
                ),
                "Encounter.diagnosis.use.coding:DiagnosesubTyp": FlatteningLookupElement(
                    parent="Encounter.diagnosis.use",
                    viewDefinition=ViewDefinitionSnippet(
                        forEachOrNull="coding.where(code = 'surgery-diagnosis' or code = 'department-main-diagnosis' or code = 'cause-of-death' or code = 'infection-control-diagnosis' or code = 'AD' or code = 'DD')",
                        select=[],
                    ),
                    children=[
                        "Encounter.diagnosis.use.coding:DiagnosesubTyp.code",
                        "Encounter.diagnosis.use.coding:DiagnosesubTyp.system",
                    ],
                ),
            },
        ),
    ],
    ids=[
        "Observation.code with slices",
        "Observation.code no slices defined",
        "Encounter.diagnosis.use slice defined by binding",
    ],
    indirect=["profile"],
)
def test_codeable_concept(
    profile: StructureDefinitionSnapshot,
    elem_id: str,
    expected: Dict[str, FlatteningLookupElement],
    client: FhirTerminologyClient,
):
    res = flattening_post_process(flatten_element(elem_id, profile, client=client))
    res = sorted(res.items(), key=lambda x: len(x[0]))
    expected = sorted(
        flattening_post_process(expected).items(), key=lambda x: len(x[0])
    )

    assert res == expected


@pytest.mark.parametrize(
    argnames="profile, elem_id ,expected",
    argvalues=[
        (
            "https://www.medizininformatik-initiative.de/fhir/core/modul-diagnose/StructureDefinition/Diagnose",
            "Condition.extension",
            {
                "Condition.extension": FlatteningLookupElement(
                    view_definition=ViewDefinitionSnippet(
                        select=[],
                    ),
                    children=[
                        "Condition.extension:ReferenzPrimaerdiagnose",
                        "Condition.extension:Feststellungsdatum",
                    ],
                ),
                "Condition.extension:ReferenzPrimaerdiagnose": FlatteningLookupElement(
                    parent="Condition.extension",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="extension.where(url = 'http://hl7.org/fhir/StructureDefinition/condition-related')",
                        select=[],
                    ),
                    children=[
                        "Condition.extension:ReferenzPrimaerdiagnose.value[x]",
                    ],
                ),
                "Condition.extension:ReferenzPrimaerdiagnose.value[x]": FlatteningLookupElement(
                    parent="Condition.extension",
                    view_definition=ViewDefinitionSnippet(
                        select=[],
                    ),
                    children=[
                        "Condition.extension:ReferenzPrimaerdiagnose.value[x]:valueReference",
                    ],
                ),
                "Condition.extension:ReferenzPrimaerdiagnose.value[x]:valueReference": FlatteningLookupElement(
                    parent="Condition.extension",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(Reference)",
                        select=[],
                    ),
                    children=[
                        "Condition.extension:ReferenzPrimaerdiagnose.value[x]:valueReference.reference",
                    ],
                ),
                "Condition.extension:ReferenzPrimaerdiagnose.value[x]:valueReference.reference": FlatteningLookupElement(
                    parent="Condition.extension",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Condition_extensionReferenzprimaerdiagnose_value_X_Valuereference_reference",
                                path="reference",
                                type="string",
                            )
                        ]
                    ),
                ),
                "Condition.extension:Feststellungsdatum": FlatteningLookupElement(
                    parent="Condition.extension",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="extension.where(url = 'http://hl7.org/fhir/StructureDefinition/condition-assertedDate')",
                        select=[],
                    ),
                    children=[
                        "Condition.extension:Feststellungsdatum.value[x]",
                    ],
                ),
                "Condition.extension:Feststellungsdatum.value[x]": FlatteningLookupElement(
                    parent="Condition.extension",
                    view_definition=ViewDefinitionSnippet(
                        select=[],
                    ),
                    children=[
                        "Condition.extension:Feststellungsdatum.value[x]:valueDateTime",
                    ],
                ),
                "Condition.extension:Feststellungsdatum.value[x]:valueDateTime": FlatteningLookupElement(
                    parent="Condition.extension",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(dateTime)",
                        select=[
                            ViewDefinitionSelect(
                                column=[
                                    ViewDefinitionColumn(
                                        name="Condition_extensionFeststellungsdatum_value_X_Valuedatetime",
                                        path="$this",
                                        type="dateTime",
                                    )
                                ]
                            )
                        ],
                    ),
                ),
            },
        ),
        (
            "https://www.medizininformatik-initiative.de/fhir/core/modul-medikation/StructureDefinition/Medication",
            "Medication.ingredient",
            {
                "Medication.ingredient": FlatteningLookupElement(
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="ingredient",
                        select=[],
                    ),
                    children=[
                        "Medication.ingredient.extension",
                        "Medication.ingredient.item[x]",
                        "Medication.ingredient.isActive",
                        "Medication.ingredient.strength",
                    ],
                ),
                "Medication.ingredient.extension": FlatteningLookupElement(
                    parent="Medication.ingredient",
                    view_definition=ViewDefinitionSnippet(select=[]),
                    children=[
                        "Medication.ingredient.extension:Wirkstofftyp",
                        "Medication.ingredient.extension:Wirkstoffrelation",
                    ],
                ),
                "Medication.ingredient.extension:Wirkstofftyp": FlatteningLookupElement(
                    parent="Medication.ingredient.extension",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="extension.where(url = 'https://www.medizininformatik-initiative.de/fhir/core/modul-medikation/StructureDefinition/wirkstofftyp')",
                        select=[],
                    ),
                    children=[
                        "Medication.ingredient.extension:Wirkstofftyp.value[x]",
                    ],
                ),
                "Medication.ingredient.extension:Wirkstofftyp.value[x]": FlatteningLookupElement(
                    parent="Medication.ingredient.extension",
                    view_definition=ViewDefinitionSnippet(select=[]),
                    children=[
                        "Medication.ingredient.extension:Wirkstofftyp.value[x]:valueCoding",
                    ],
                ),
                "Medication.ingredient.extension:Wirkstofftyp.value[x]:valueCoding": FlatteningLookupElement(
                    parent="Medication.ingredient.extension",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(Coding)",
                        select=[
                            ViewDefinitionSelect(
                                column=[
                                    ViewDefinitionColumn(
                                        name="Medication_ingredient_extensionWirkstofftyp_value_X_Valuecoding_system",
                                        path="system",
                                    ),
                                    ViewDefinitionColumn(
                                        name="Medication_ingredient_extensionWirkstofftyp_value_X_Valuecoding_code",
                                        path="code",
                                    ),
                                ]
                            )
                        ],
                    ),
                ),
                "Medication.ingredient.extension:Wirkstoffrelation": FlatteningLookupElement(
                    parent="Medication.ingredient.extension",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="extension.where(url = 'https://www.medizininformatik-initiative.de/fhir/core/modul-medikation/StructureDefinition/wirkstoffrelation')",
                        select=[],
                    ),
                    children=[
                        "Medication.ingredient.extension:Wirkstoffrelation.extension",
                    ],
                ),
                "Medication.ingredient.extension:Wirkstoffrelation.extension": FlatteningLookupElement(
                    parent="Medication.ingredient.extension",
                    view_definition=ViewDefinitionSnippet(select=[]),
                    children=[
                        "Medication.ingredient.extension:Wirkstoffrelation.extension:ingredientReference",
                        "Medication.ingredient.extension:Wirkstoffrelation.extension:ingredientUri",
                    ],
                ),
                "Medication.ingredient.extension:Wirkstoffrelation.extension:ingredientReference": FlatteningLookupElement(
                    parent="Medication.ingredient.extension",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="extension.where(url = 'ingredientReference')",
                        select=[],
                    ),
                    children=[
                        "Medication.ingredient.extension:Wirkstoffrelation.extension:ingredientReference.value[x]",
                    ],
                ),
                "Medication.ingredient.extension:Wirkstoffrelation.extension:ingredientReference.value[x]": FlatteningLookupElement(
                    parent="Medication.ingredient.extension",
                    view_definition=ViewDefinitionSnippet(select=[]),
                    children=[
                        "Medication.ingredient.extension:Wirkstoffrelation.extension:ingredientReference.value[x]:valueReference",
                    ],
                ),
                "Medication.ingredient.extension:Wirkstoffrelation.extension:ingredientReference.value[x]:valueReference": FlatteningLookupElement(
                    parent="Medication.ingredient.extension",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(Reference)",
                        select=[],
                    ),
                    children=[
                        "Medication.ingredient.extension:Wirkstoffrelation.extension:ingredientReference.value[x]:valueReference.reference",
                    ],
                ),
                "Medication.ingredient.extension:Wirkstoffrelation.extension:ingredientReference.value[x]:valueReference.reference": FlatteningLookupElement(
                    parent="Medication.ingredient.extension",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Medication_ingredient_extensionWirkstoffrelation_extensionIngredientreference_value_X_Valuereference_reference",
                                path="reference",
                                type="string",
                            )
                        ]
                    ),
                ),
                "Medication.ingredient.extension:Wirkstoffrelation.extension:ingredientUri": FlatteningLookupElement(
                    parent="Medication.ingredient.extension",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="extension.where(url = 'ingredientUri')",
                        select=[],
                    ),
                    children=[
                        "Medication.ingredient.extension:Wirkstoffrelation.extension:ingredientUri.value[x]",
                    ],
                ),
                "Medication.ingredient.extension:Wirkstoffrelation.extension:ingredientUri.value[x]": FlatteningLookupElement(
                    parent="Medication.ingredient.extension",
                    view_definition=ViewDefinitionSnippet(select=[]),
                    children=[
                        "Medication.ingredient.extension:Wirkstoffrelation.extension:ingredientUri.value[x]:valueUri",
                    ],
                ),
                "Medication.ingredient.extension:Wirkstoffrelation.extension:ingredientUri.value[x]:valueUri": FlatteningLookupElement(
                    parent="Medication.ingredient.extension",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(uri)",
                        select=[
                            ViewDefinitionSelect(
                                column=[
                                    ViewDefinitionColumn(
                                        name="Medication_ingredient_extensionWirkstoffrelation_extensionIngredienturi_value_X_Valueuri",
                                        path="$this",
                                        type="uri",
                                    )
                                ]
                            )
                        ],
                    ),
                ),
                "Medication.ingredient.item[x]": FlatteningLookupElement(
                    parent="Medication.ingredient",
                    view_definition=ViewDefinitionSnippet(select=[]),
                    children=[
                        "Medication.ingredient.item[x]:itemCodeableConcept",
                        "Medication.ingredient.item[x]:itemReference",
                    ],
                ),
                "Medication.ingredient.item[x]:itemCodeableConcept": FlatteningLookupElement(
                    parent="Medication.ingredient.item[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="item.ofType(CodeableConcept)",
                        select=[],
                    ),
                    children=[
                        "Medication.ingredient.item[x]:itemCodeableConcept.coding:ASK",
                        "Medication.ingredient.item[x]:itemCodeableConcept.coding:UNII",
                        "Medication.ingredient.item[x]:itemCodeableConcept.coding:CAS",
                        "Medication.ingredient.item[x]:itemCodeableConcept.coding:SNOMED",
                    ],
                ),
                "Medication.ingredient.item[x]:itemCodeableConcept.coding:ASK": FlatteningLookupElement(
                    parent="Medication.ingredient.item[x]:itemCodeableConcept",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="coding.where(system = 'http://fhir.de/CodeSystem/ask')",
                        select=[],
                    ),
                    children=[
                        "Medication.ingredient.item[x]:itemCodeableConcept.coding:ASK.system",
                        "Medication.ingredient.item[x]:itemCodeableConcept.coding:ASK.code",
                    ],
                ),
                "Medication.ingredient.item[x]:itemCodeableConcept.coding:ASK.system": FlatteningLookupElement(
                    parent="Medication.ingredient.item[x]:itemCodeableConcept.coding:ASK",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Medication_ingredient_item_X_Itemcodeableconcept_codingAsk_system",
                                path="system",
                                type="uri",
                            )
                        ]
                    ),
                ),
                "Medication.ingredient.item[x]:itemCodeableConcept.coding:ASK.code": FlatteningLookupElement(
                    parent="Medication.ingredient.item[x]:itemCodeableConcept.coding:ASK",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Medication_ingredient_item_X_Itemcodeableconcept_codingAsk_code",
                                path="code",
                                type="code",
                            )
                        ]
                    ),
                ),
                "Medication.ingredient.item[x]:itemCodeableConcept.coding:UNII": FlatteningLookupElement(
                    parent="Medication.ingredient.item[x]:itemCodeableConcept",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="coding.where(system = 'http://fdasis.nlm.nih.gov')",
                        select=[],
                    ),
                    children=[
                        "Medication.ingredient.item[x]:itemCodeableConcept.coding:UNII.system",
                        "Medication.ingredient.item[x]:itemCodeableConcept.coding:UNII.code",
                    ],
                ),
                "Medication.ingredient.item[x]:itemCodeableConcept.coding:UNII.system": FlatteningLookupElement(
                    parent="Medication.ingredient.item[x]:itemCodeableConcept.coding:UNII",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Medication_ingredient_item_X_Itemcodeableconcept_codingUnii_system",
                                path="system",
                                type="uri",
                            )
                        ]
                    ),
                ),
                "Medication.ingredient.item[x]:itemCodeableConcept.coding:UNII.code": FlatteningLookupElement(
                    parent="Medication.ingredient.item[x]:itemCodeableConcept.coding:UNII",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Medication_ingredient_item_X_Itemcodeableconcept_codingUnii_code",
                                path="code",
                                type="code",
                            )
                        ]
                    ),
                ),
                "Medication.ingredient.item[x]:itemCodeableConcept.coding:CAS": FlatteningLookupElement(
                    parent="Medication.ingredient.item[x]:itemCodeableConcept",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="coding.where(system = 'http://terminology.hl7.org/CodeSystem/CAS')",
                        select=[],
                    ),
                    children=[
                        "Medication.ingredient.item[x]:itemCodeableConcept.coding:CAS.system",
                        "Medication.ingredient.item[x]:itemCodeableConcept.coding:CAS.code",
                    ],
                ),
                "Medication.ingredient.item[x]:itemCodeableConcept.coding:CAS.system": FlatteningLookupElement(
                    parent="Medication.ingredient.item[x]:itemCodeableConcept.coding:CAS",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Medication_ingredient_item_X_Itemcodeableconcept_codingCas_system",
                                path="system",
                                type="uri",
                            )
                        ]
                    ),
                ),
                "Medication.ingredient.item[x]:itemCodeableConcept.coding:CAS.code": FlatteningLookupElement(
                    parent="Medication.ingredient.item[x]:itemCodeableConcept.coding:CAS",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Medication_ingredient_item_X_Itemcodeableconcept_codingCas_code",
                                path="code",
                                type="code",
                            )
                        ]
                    ),
                ),
                "Medication.ingredient.item[x]:itemCodeableConcept.coding:SNOMED": FlatteningLookupElement(
                    parent="Medication.ingredient.item[x]:itemCodeableConcept",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="coding.where(system = 'http://snomed.info/sct')",
                        select=[],
                    ),
                    children=[
                        "Medication.ingredient.item[x]:itemCodeableConcept.coding:SNOMED.system",
                        "Medication.ingredient.item[x]:itemCodeableConcept.coding:SNOMED.code",
                    ],
                ),
                "Medication.ingredient.item[x]:itemCodeableConcept.coding:SNOMED.system": FlatteningLookupElement(
                    parent="Medication.ingredient.item[x]:itemCodeableConcept.coding:SNOMED",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Medication_ingredient_item_X_Itemcodeableconcept_codingSnomed_system",
                                path="system",
                                type="uri",
                            )
                        ]
                    ),
                ),
                "Medication.ingredient.item[x]:itemCodeableConcept.coding:SNOMED.code": FlatteningLookupElement(
                    parent="Medication.ingredient.item[x]:itemCodeableConcept.coding:SNOMED",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Medication_ingredient_item_X_Itemcodeableconcept_codingSnomed_code",
                                path="code",
                                type="code",
                            )
                        ]
                    ),
                ),
                "Medication.ingredient.item[x]:itemReference": FlatteningLookupElement(
                    parent="Medication.ingredient.item[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="item.ofType(Reference)",
                        select=[],
                    ),
                    children=[
                        "Medication.ingredient.item[x]:itemReference.reference",
                    ],
                ),
                "Medication.ingredient.item[x]:itemReference.reference": FlatteningLookupElement(
                    parent="Medication.ingredient.item[x]:itemReference",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Medication_ingredient_item_X_Itemreference_reference",
                                path="reference",
                                type="string",
                            )
                        ]
                    ),
                ),
                "Medication.ingredient.isActive": FlatteningLookupElement(
                    parent="Medication.ingredient",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Medication_ingredient_isActive",
                                path="isActive",
                                type="boolean",
                            )
                        ]
                    ),
                ),
                "Medication.ingredient.strength": FlatteningLookupElement(
                    parent="Medication.ingredient",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="strength",
                        select=[],
                    ),
                    children=[
                        "Medication.ingredient.strength.numerator",
                        "Medication.ingredient.strength.denominator",
                    ],
                ),
                "Medication.ingredient.strength.numerator": FlatteningLookupElement(
                    parent="Medication.ingredient.strength",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="numerator",
                        select=[],
                    ),
                    children=[
                        "Medication.ingredient.strength.numerator.value",
                        "Medication.ingredient.strength.numerator.code",
                        "Medication.ingredient.strength.numerator.system",
                    ],
                ),
                "Medication.ingredient.strength.numerator.value": FlatteningLookupElement(
                    parent="Medication.ingredient.strength.numerator",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Medication_ingredient_strength_numerator_value",
                                path="value",
                                type="code",
                            )
                        ]
                    ),
                ),
                "Medication.ingredient.strength.numerator.code": FlatteningLookupElement(
                    parent="Medication.ingredient.strength.numerator",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Medication_ingredient_strength_numerator_code",
                                path="code",
                                type="code",
                            )
                        ]
                    ),
                ),
                "Medication.ingredient.strength.numerator.system": FlatteningLookupElement(
                    parent="Medication.ingredient.strength.numerator",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Medication_ingredient_strength_numerator_system",
                                path="system",
                                type="uri",
                            )
                        ]
                    ),
                ),
                "Medication.ingredient.strength.denominator": FlatteningLookupElement(
                    parent="Medication.ingredient.strength",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="denominator",
                        select=[],
                    ),
                    children=[
                        "Medication.ingredient.strength.denominator.value",
                        "Medication.ingredient.strength.denominator.code",
                        "Medication.ingredient.strength.denominator.system",
                    ],
                ),
                "Medication.ingredient.strength.denominator.value": FlatteningLookupElement(
                    parent="Medication.ingredient.strength.denominator",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Medication_ingredient_strength_denominator_value",
                                path="value",
                                type="code",
                            )
                        ]
                    ),
                ),
                "Medication.ingredient.strength.denominator.code": FlatteningLookupElement(
                    parent="Medication.ingredient.strength.denominator",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Medication_ingredient_strength_denominator_code",
                                path="code",
                                type="code",
                            )
                        ]
                    ),
                ),
                "Medication.ingredient.strength.denominator.system": FlatteningLookupElement(
                    parent="Medication.ingredient.strength.denominator",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Medication_ingredient_strength_denominator_system",
                                path="system",
                                type="uri",
                            )
                        ]
                    ),
                ),
            },
        ),
    ],
    ids=[
        "Extension defined in separate profile: Condition.extension",
        "Extension defined inplace and extern: Medication.ingredient",
    ],
    indirect=["profile"],
)
def test_extensions(
    profile: StructureDefinitionSnapshot,
    elem_id: str,
    expected: Dict[str, FlatteningLookupElement],
    package_manager: FhirPackageManager,
):
    res = flattening_post_process(
        flatten_element(elem_id, profile, manager=package_manager)
    )
    res = sorted(res.items(), key=lambda x: len(x[0]))
    expected = sorted(
        flattening_post_process(expected).items(), key=lambda x: len(x[0])
    )

    assert res == expected


#
# @pytest.mark.parametrize(
#     argnames="profile, elem_id, elem_type, expected",
#     argvalues=[
#         (
#             "https://www.medizininformatik-initiative.de/fhir/ext/modul-bildgebung/StructureDefinition/mii-pr-bildgebung-radiologische-beobachtung",
#             "Observation.value[x]:valueQuantity",
#             "Quantity",
#             {
#                 "Observation.value[x]:valueQuantity": FlatteningLookupElement(
#                     parent="Observation.value[x]",
#                     view_definition=ViewDefinitionSnippet(
#                         for_each_or_null="value.ofType(Quantity)",
#                         select=[],
#                     ),
#                     children=[
#                         "Observation.value[x]:valueQuantity.value",
#                         "Observation.value[x]:valueQuantity.code",
#                         "Observation.value[x]:valueQuantity.system",
#                     ],
#                 ),
#                 "Observation.value[x]:valueQuantity.value": FlatteningLookupElement(
#                     parent="Observation.value[x]:valueQuantity",
#                     view_definition=ViewDefinitionSnippet(
#                         column=[
#                             ViewDefinitionColumn(
#                                 name="Observation_value_X_Valuequantity_value",
#                                 path="value",
#                                 type="code",
#                             )
#                         ]
#                     ),
#                 ),
#                 "Observation.value[x]:valueQuantity.code": FlatteningLookupElement(
#                     parent="Observation.value[x]:valueQuantity",
#                     view_definition=ViewDefinitionSnippet(
#                         column=[
#                             ViewDefinitionColumn(
#                                 name="Observation_value_X_Valuequantity_code",
#                                 path="code",
#                                 type="code",
#                             )
#                         ]
#                     ),
#                 ),
#                 "Observation.value[x]:valueQuantity.system": FlatteningLookupElement(
#                     parent="Observation.value[x]:valueQuantity",
#                     view_definition=ViewDefinitionSnippet(
#                         column=[
#                             ViewDefinitionColumn(
#                                 name="Observation_value_X_Valuequantity_system",
#                                 path="system",
#                                 type="uri",
#                             )
#                         ]
#                     ),
#                 ),
#             },
#         )
#     ],
#     ids=[
#         "Quantity and all its descendents (Count, Duration, Distance, SimpleQuantity, MoneyQuantity)",
#     ],
#     indirect=["profile"],
# )
# def test_generic_complex_flattening(
#     profile: StructureDefinitionSnapshot,
#     elem_id: str,
#     elem_type: str,
#     expected: Dict[str, FlatteningLookupElement],
#     package_manager: FhirPackageManager,
#     client: FhirTerminologyClient,
# ):
#     res = flattening_post_process(
#         flatten_element(elem_id, profile, manager=package_manager, type=elem_type, client=client)
#     )
#     res = sorted(res.items(), key=lambda x: len(x[0]))
#     expected = sorted(
#         flattening_post_process(expected).items(), key=lambda x: len(x[0])
#     )
#
#     assert res == expected


@pytest.mark.parametrize(
    argnames="profile, elem_id, elem_type, expected",
    argvalues=[
        (
            "https://gematik.de/fhir/isik/StructureDefinition/ISiKPatient",
            "Patient.identifier",
            "Identifier",
            {
                "Patient.identifier:Versichertennummer_PKV.use": FlatteningLookupElement(
                    parent="Patient.identifier:Versichertennummer_PKV",
                    viewDefinition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Patient_identifierVersichertennummer_pkv_use",
                                path="use",
                                type="code",
                            )
                        ]
                    ),
                ),
                "Patient.identifier:Versichertennummer_PKV.type": FlatteningLookupElement(
                    parent="Patient.identifier:Versichertennummer_PKV",
                    viewDefinition=ViewDefinitionSnippet(
                        forEachOrNull="type", select=[]
                    ),
                    children=["Patient.identifier:Versichertennummer_PKV.type.coding"],
                ),
                "Patient.identifier:Versichertennummer_PKV.type.coding": FlatteningLookupElement(
                    parent="Patient.identifier:Versichertennummer_PKV.type",
                    viewDefinition=ViewDefinitionSnippet(
                        forEachOrNull="coding",
                        column=[
                            ViewDefinitionColumn(
                                name="Patient_identifierVersichertennummer_pkv_type_coding_system",
                                path="system",
                            ),
                            ViewDefinitionColumn(
                                name="Patient_identifierVersichertennummer_pkv_type_coding_code",
                                path="code",
                            ),
                        ],
                    ),
                ),
                "Patient.identifier:Versichertennummer_PKV.system": FlatteningLookupElement(
                    parent="Patient.identifier:Versichertennummer_PKV",
                    viewDefinition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Patient_identifierVersichertennummer_pkv_system",
                                path="system",
                                type="uri",
                            )
                        ]
                    ),
                ),
                "Patient.identifier:Versichertennummer_PKV.value": FlatteningLookupElement(
                    parent="Patient.identifier:Versichertennummer_PKV",
                    viewDefinition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Patient_identifierVersichertennummer_pkv_value",
                                path="value",
                                type="string",
                            )
                        ]
                    ),
                ),
                "Patient.identifier:Versichertennummer_PKV.period.start": FlatteningLookupElement(
                    parent="Patient.identifier:Versichertennummer_PKV.period",
                    viewDefinition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Patient_identifierVersichertennummer_pkv_period_start",
                                path="start",
                                type="dateTime",
                            )
                        ]
                    ),
                ),
                "Patient.identifier:Versichertennummer_PKV.period.end": FlatteningLookupElement(
                    parent="Patient.identifier:Versichertennummer_PKV.period",
                    viewDefinition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Patient_identifierVersichertennummer_pkv_period_end",
                                path="end",
                                type="dateTime",
                            )
                        ]
                    ),
                ),
                "Patient.identifier:Versichertennummer_PKV.period": FlatteningLookupElement(
                    parent="Patient.identifier:Versichertennummer_PKV",
                    viewDefinition=ViewDefinitionSnippet(
                        forEachOrNull="period", select=[]
                    ),
                    children=[
                        "Patient.identifier:Versichertennummer_PKV.period.start",
                        "Patient.identifier:Versichertennummer_PKV.period.end",
                    ],
                ),
                "Patient.identifier:Versichertennummer_PKV.assigner.reference": FlatteningLookupElement(
                    parent="Patient.identifier:Versichertennummer_PKV.assigner",
                    viewDefinition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Patient_identifierVersichertennummer_pkv_assigner_reference",
                                path="reference",
                                type="string",
                            )
                        ]
                    ),
                ),
                "Patient.identifier:Versichertennummer_PKV.assigner": FlatteningLookupElement(
                    parent="Patient.identifier:Versichertennummer_PKV",
                    viewDefinition=ViewDefinitionSnippet(
                        forEachOrNull="assigner", select=[]
                    ),
                    children=[
                        "Patient.identifier:Versichertennummer_PKV.assigner.reference"
                    ],
                ),
                "Patient.identifier:Versichertennummer_PKV": FlatteningLookupElement(
                    parent="Patient.identifier",
                    viewDefinition=ViewDefinitionSnippet(
                        forEachOrNull="$this.where(type.coding.system = 'http://fhir.de/CodeSystem/identifier-type-de-basis')",
                        select=[],
                    ),
                    children=[
                        "Patient.identifier:Versichertennummer_PKV.use",
                        "Patient.identifier:Versichertennummer_PKV.type",
                        "Patient.identifier:Versichertennummer_PKV.system",
                        "Patient.identifier:Versichertennummer_PKV.value",
                        "Patient.identifier:Versichertennummer_PKV.period",
                        "Patient.identifier:Versichertennummer_PKV.assigner",
                    ],
                ),
                "Patient.identifier:Patientennummer.use": FlatteningLookupElement(
                    parent="Patient.identifier:Patientennummer",
                    viewDefinition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Patient_identifierPatientennummer_use",
                                path="use",
                                type="code",
                            )
                        ]
                    ),
                ),
                "Patient.identifier:Patientennummer.type": FlatteningLookupElement(
                    parent="Patient.identifier:Patientennummer",
                    viewDefinition=ViewDefinitionSnippet(
                        forEachOrNull="type", select=[]
                    ),
                    children=["Patient.identifier:Patientennummer.type.coding"],
                ),
                "Patient.identifier:Patientennummer.type.coding": FlatteningLookupElement(
                    parent="Patient.identifier:Patientennummer.type",
                    viewDefinition=ViewDefinitionSnippet(
                        forEachOrNull="coding",
                        column=[
                            ViewDefinitionColumn(
                                name="Patient_identifierPatientennummer_type_coding_system",
                                path="system",
                            ),
                            ViewDefinitionColumn(
                                name="Patient_identifierPatientennummer_type_coding_code",
                                path="code",
                            ),
                        ],
                    ),
                ),
                "Patient.identifier:Patientennummer.system": FlatteningLookupElement(
                    parent="Patient.identifier:Patientennummer",
                    viewDefinition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Patient_identifierPatientennummer_system",
                                path="system",
                                type="uri",
                            )
                        ]
                    ),
                ),
                "Patient.identifier:Patientennummer.value": FlatteningLookupElement(
                    parent="Patient.identifier:Patientennummer",
                    viewDefinition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Patient_identifierPatientennummer_value",
                                path="value",
                                type="string",
                            )
                        ]
                    ),
                ),
                "Patient.identifier:Patientennummer.period.start": FlatteningLookupElement(
                    parent="Patient.identifier:Patientennummer.period",
                    viewDefinition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Patient_identifierPatientennummer_period_start",
                                path="start",
                                type="dateTime",
                            )
                        ]
                    ),
                ),
                "Patient.identifier:Patientennummer.period.end": FlatteningLookupElement(
                    parent="Patient.identifier:Patientennummer.period",
                    viewDefinition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Patient_identifierPatientennummer_period_end",
                                path="end",
                                type="dateTime",
                            )
                        ]
                    ),
                ),
                "Patient.identifier:Patientennummer.period": FlatteningLookupElement(
                    parent="Patient.identifier:Patientennummer",
                    viewDefinition=ViewDefinitionSnippet(
                        forEachOrNull="period", select=[]
                    ),
                    children=[
                        "Patient.identifier:Patientennummer.period.start",
                        "Patient.identifier:Patientennummer.period.end",
                    ],
                ),
                "Patient.identifier:Patientennummer.assigner.reference": FlatteningLookupElement(
                    parent="Patient.identifier:Patientennummer.assigner",
                    viewDefinition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Patient_identifierPatientennummer_assigner_reference",
                                path="reference",
                                type="string",
                            )
                        ]
                    ),
                ),
                "Patient.identifier:Patientennummer.assigner": FlatteningLookupElement(
                    parent="Patient.identifier:Patientennummer",
                    viewDefinition=ViewDefinitionSnippet(
                        forEachOrNull="assigner", select=[]
                    ),
                    children=["Patient.identifier:Patientennummer.assigner.reference"],
                ),
                "Patient.identifier:Patientennummer": FlatteningLookupElement(
                    parent="Patient.identifier",
                    viewDefinition=ViewDefinitionSnippet(
                        forEachOrNull="$this.where(type.coding.system = 'http://terminology.hl7.org/CodeSystem/v2-0203')",
                        select=[],
                    ),
                    children=[
                        "Patient.identifier:Patientennummer.use",
                        "Patient.identifier:Patientennummer.type",
                        "Patient.identifier:Patientennummer.system",
                        "Patient.identifier:Patientennummer.value",
                        "Patient.identifier:Patientennummer.period",
                        "Patient.identifier:Patientennummer.assigner",
                    ],
                ),
                "Patient.identifier:VersichertenId.use": FlatteningLookupElement(
                    parent="Patient.identifier:VersichertenId",
                    viewDefinition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Patient_identifierVersichertenid_use",
                                path="use",
                                type="code",
                            )
                        ]
                    ),
                ),
                "Patient.identifier:VersichertenId.type": FlatteningLookupElement(
                    parent="Patient.identifier:VersichertenId",
                    viewDefinition=ViewDefinitionSnippet(
                        forEachOrNull="type", select=[]
                    ),
                    children=["Patient.identifier:VersichertenId.type.coding"],
                ),
                "Patient.identifier:VersichertenId.type.coding": FlatteningLookupElement(
                    parent="Patient.identifier:VersichertenId.type",
                    viewDefinition=ViewDefinitionSnippet(
                        forEachOrNull="coding",
                        column=[
                            ViewDefinitionColumn(
                                name="Patient_identifierVersichertenid_type_coding_system",
                                path="system",
                            ),
                            ViewDefinitionColumn(
                                name="Patient_identifierVersichertenid_type_coding_code",
                                path="code",
                            ),
                        ],
                    ),
                ),
                "Patient.identifier:VersichertenId.system": FlatteningLookupElement(
                    parent="Patient.identifier:VersichertenId",
                    viewDefinition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Patient_identifierVersichertenid_system",
                                path="system",
                                type="uri",
                            )
                        ]
                    ),
                ),
                "Patient.identifier:VersichertenId.value": FlatteningLookupElement(
                    parent="Patient.identifier:VersichertenId",
                    viewDefinition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Patient_identifierVersichertenid_value",
                                path="value",
                                type="string",
                            )
                        ]
                    ),
                ),
                "Patient.identifier:VersichertenId.period.start": FlatteningLookupElement(
                    parent="Patient.identifier:VersichertenId.period",
                    viewDefinition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Patient_identifierVersichertenid_period_start",
                                path="start",
                                type="dateTime",
                            )
                        ]
                    ),
                ),
                "Patient.identifier:VersichertenId.period.end": FlatteningLookupElement(
                    parent="Patient.identifier:VersichertenId.period",
                    viewDefinition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Patient_identifierVersichertenid_period_end",
                                path="end",
                                type="dateTime",
                            )
                        ]
                    ),
                ),
                "Patient.identifier:VersichertenId.period": FlatteningLookupElement(
                    parent="Patient.identifier:VersichertenId",
                    viewDefinition=ViewDefinitionSnippet(
                        forEachOrNull="period", select=[]
                    ),
                    children=[
                        "Patient.identifier:VersichertenId.period.start",
                        "Patient.identifier:VersichertenId.period.end",
                    ],
                ),
                "Patient.identifier:VersichertenId.assigner.reference": FlatteningLookupElement(
                    parent="Patient.identifier:VersichertenId.assigner",
                    viewDefinition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Patient_identifierVersichertenid_assigner_reference",
                                path="reference",
                                type="string",
                            )
                        ]
                    ),
                ),
                "Patient.identifier:VersichertenId.assigner": FlatteningLookupElement(
                    parent="Patient.identifier:VersichertenId",
                    viewDefinition=ViewDefinitionSnippet(
                        forEachOrNull="assigner", select=[]
                    ),
                    children=["Patient.identifier:VersichertenId.assigner.reference"],
                ),
                "Patient.identifier:VersichertenId": FlatteningLookupElement(
                    parent="Patient.identifier",
                    viewDefinition=ViewDefinitionSnippet(
                        forEachOrNull="$this.where(type.coding.system = 'http://fhir.de/sid/gkv/kvid-10')",
                        select=[],
                    ),
                    children=[
                        "Patient.identifier:VersichertenId.use",
                        "Patient.identifier:VersichertenId.type",
                        "Patient.identifier:VersichertenId.system",
                        "Patient.identifier:VersichertenId.value",
                        "Patient.identifier:VersichertenId.period",
                        "Patient.identifier:VersichertenId.assigner",
                    ],
                ),
                "Patient.identifier:VersichertenId-GKV.use": FlatteningLookupElement(
                    parent="Patient.identifier:VersichertenId-GKV",
                    viewDefinition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Patient_identifierVersichertenidgkv_use",
                                path="use",
                                type="code",
                            )
                        ]
                    ),
                ),
                "Patient.identifier:VersichertenId-GKV.type": FlatteningLookupElement(
                    parent="Patient.identifier:VersichertenId-GKV",
                    viewDefinition=ViewDefinitionSnippet(
                        forEachOrNull="type", select=[]
                    ),
                    children=["Patient.identifier:VersichertenId-GKV.type.coding"],
                ),
                "Patient.identifier:VersichertenId-GKV.type.coding": FlatteningLookupElement(
                    parent="Patient.identifier:VersichertenId-GKV.type",
                    viewDefinition=ViewDefinitionSnippet(
                        forEachOrNull="coding",
                        column=[
                            ViewDefinitionColumn(
                                name="Patient_identifierVersichertenidgkv_type_coding_system",
                                path="system",
                            ),
                            ViewDefinitionColumn(
                                name="Patient_identifierVersichertenidgkv_type_coding_code",
                                path="code",
                            ),
                        ],
                    ),
                ),
                "Patient.identifier:VersichertenId-GKV.system": FlatteningLookupElement(
                    parent="Patient.identifier:VersichertenId-GKV",
                    viewDefinition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Patient_identifierVersichertenidgkv_system",
                                path="system",
                                type="uri",
                            )
                        ]
                    ),
                ),
                "Patient.identifier:VersichertenId-GKV.value": FlatteningLookupElement(
                    parent="Patient.identifier:VersichertenId-GKV",
                    viewDefinition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Patient_identifierVersichertenidgkv_value",
                                path="value",
                                type="string",
                            )
                        ]
                    ),
                ),
                "Patient.identifier:VersichertenId-GKV.period.start": FlatteningLookupElement(
                    parent="Patient.identifier:VersichertenId-GKV.period",
                    viewDefinition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Patient_identifierVersichertenidgkv_period_start",
                                path="start",
                                type="dateTime",
                            )
                        ]
                    ),
                ),
                "Patient.identifier:VersichertenId-GKV.period.end": FlatteningLookupElement(
                    parent="Patient.identifier:VersichertenId-GKV.period",
                    viewDefinition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Patient_identifierVersichertenidgkv_period_end",
                                path="end",
                                type="dateTime",
                            )
                        ]
                    ),
                ),
                "Patient.identifier:VersichertenId-GKV.period": FlatteningLookupElement(
                    parent="Patient.identifier:VersichertenId-GKV",
                    viewDefinition=ViewDefinitionSnippet(
                        forEachOrNull="period", select=[]
                    ),
                    children=[
                        "Patient.identifier:VersichertenId-GKV.period.start",
                        "Patient.identifier:VersichertenId-GKV.period.end",
                    ],
                ),
                "Patient.identifier:VersichertenId-GKV.assigner.reference": FlatteningLookupElement(
                    parent="Patient.identifier:VersichertenId-GKV.assigner",
                    viewDefinition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Patient_identifierVersichertenidgkv_assigner_reference",
                                path="reference",
                                type="string",
                            )
                        ]
                    ),
                ),
                "Patient.identifier:VersichertenId-GKV.assigner": FlatteningLookupElement(
                    parent="Patient.identifier:VersichertenId-GKV",
                    viewDefinition=ViewDefinitionSnippet(
                        forEachOrNull="assigner", select=[]
                    ),
                    children=[
                        "Patient.identifier:VersichertenId-GKV.assigner.reference"
                    ],
                ),
                "Patient.identifier:VersichertenId-GKV": FlatteningLookupElement(
                    parent="Patient.identifier",
                    viewDefinition=ViewDefinitionSnippet(
                        forEachOrNull="$this.where(type.coding.system = 'http://fhir.de/sid/gkv/kvid-10')",
                        select=[],
                    ),
                    children=[
                        "Patient.identifier:VersichertenId-GKV.use",
                        "Patient.identifier:VersichertenId-GKV.type",
                        "Patient.identifier:VersichertenId-GKV.system",
                        "Patient.identifier:VersichertenId-GKV.value",
                        "Patient.identifier:VersichertenId-GKV.period",
                        "Patient.identifier:VersichertenId-GKV.assigner",
                    ],
                ),
                "Patient.identifier": FlatteningLookupElement(
                    viewDefinition=ViewDefinitionSnippet(
                        forEachOrNull="identifier", select=[]
                    ),
                    children=[
                        "Patient.identifier:VersichertenId",
                        "Patient.identifier:Patientennummer",
                        "Patient.identifier:Versichertennummer_PKV",
                        "Patient.identifier:VersichertenId-GKV",
                    ],
                ),
            },
        )
    ],
    ids=["Test Patient identifier ISIK Gematik"],
    indirect=["profile"],
)
def test_identifier(
    profile: StructureDefinitionSnapshot,
    elem_id: str,
    elem_type: str,
    expected: Dict[str, FlatteningLookupElement],
    package_manager: FhirPackageManager,
    client: FhirTerminologyClient,
):
    res = flattening_post_process(
        flatten_element(
            elem_id, profile, manager=package_manager, type=elem_type, client=client
        )
    )
    res = sorted(res.items(), key=lambda x: (len(x[0]), x[0]))
    expected = sorted(
        flattening_post_process(expected).items(), key=lambda x: (len(x[0]), x[0])
    )

    assert res == expected
