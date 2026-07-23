import json
from pathlib import Path
from typing import Dict

import pytest
from fhir.resources.R4B.elementdefinition import ElementDefinition

from common.model.fhir.structure_definition import StructureDefinitionSnapshot
from common.util.http.terminology.client import FhirTerminologyClient
from flattening.core.flattening import (
    FlatteningLookupElement,
    ViewDefinitionColumn,
    ViewDefinitionSnippet,
    flattening_post_process,
    ViewDefinitionSelect,
    FlatteningLookupGenerator,
)


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
    flattening_lookup_generator: FlatteningLookupGenerator,
):
    assert (
        flattening_lookup_generator._flatten_primitive(elem_def.id, profile) == expected
    )


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
                        "Observation.value[x]:valueQuantity.unit",
                        "Observation.value[x]:valueQuantity.comparator",
                    ],
                ),
                "Observation.value[x]:valueQuantity.value": FlatteningLookupElement(
                    parent="Observation.value[x]:valueQuantity",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Observation_value_X_Valuequantity_value",
                                path="value",
                                type="decimal",
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
                "Observation.value[x]:valueQuantity.unit": FlatteningLookupElement(
                    parent="Observation.value[x]:valueQuantity",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Observation_value_X_Valuequantity_unit",
                                path="unit",
                                type="string",
                            )
                        ]
                    ),
                ),
                "Observation.value[x]:valueQuantity.comparator": FlatteningLookupElement(
                    parent="Observation.value[x]:valueQuantity",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Observation_value_X_Valuequantity_comparator",
                                path="comparator",
                                type="code",
                            )
                        ]
                    ),
                ),
            },
        ),
        (
            "https://www.medizininformatik-initiative.de/fhir/ext/modul-molgen/StructureDefinition/empfohlene-folgemassnahme",
            "Task.input.value[x]",
            {
                "Task.input.value[x]": FlatteningLookupElement(
                    parent="Task.input",
                    view_definition=ViewDefinitionSnippet(
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueAddress",
                        "Task.input.value[x]:valueAge",
                        "Task.input.value[x]:valueAnnotation",
                        "Task.input.value[x]:valueAttachment",
                        "Task.input.value[x]:valueBase64Binary",
                        "Task.input.value[x]:valueBoolean",
                        "Task.input.value[x]:valueCanonical",
                        "Task.input.value[x]:valueCode",
                        "Task.input.value[x]:valueCodeableConcept",
                        "Task.input.value[x]:valueCoding",
                        "Task.input.value[x]:valueContactPoint",
                        "Task.input.value[x]:valueContributor",
                        "Task.input.value[x]:valueCount",
                        "Task.input.value[x]:valueDataRequirement",
                        "Task.input.value[x]:valueDate",
                        "Task.input.value[x]:valueDateTime",
                        "Task.input.value[x]:valueDecimal",
                        "Task.input.value[x]:valueDistance",
                        "Task.input.value[x]:valueDosage",
                        "Task.input.value[x]:valueDuration",
                        "Task.input.value[x]:valueInstant",
                        "Task.input.value[x]:valueInteger",
                        "Task.input.value[x]:valueMarkdown",
                        "Task.input.value[x]:valueMeta",
                        "Task.input.value[x]:valueOid",
                        "Task.input.value[x]:valuePeriod",
                        "Task.input.value[x]:valuePositiveInt",
                        "Task.input.value[x]:valueQuantity",
                        "Task.input.value[x]:valueRange",
                        "Task.input.value[x]:valueRatio",
                        "Task.input.value[x]:valueReference",
                        "Task.input.value[x]:valueSampledData",
                        "Task.input.value[x]:valueString",
                        "Task.input.value[x]:valueTime",
                        "Task.input.value[x]:valueTiming",
                        "Task.input.value[x]:valueTriggerDefinition",
                        "Task.input.value[x]:valueUnsignedInt",
                        "Task.input.value[x]:valueUri",
                        "Task.input.value[x]:valueUrl",
                        "Task.input.value[x]:valueUsageContext",
                        "Task.input.value[x]:valueUuid",
                    ],
                ),
                "Task.input.value[x]:valueAddress": FlatteningLookupElement(
                    parent="Task.input.value[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(Address)",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueAddress.city",
                        "Task.input.value[x]:valueAddress.country",
                        "Task.input.value[x]:valueAddress.district",
                        "Task.input.value[x]:valueAddress.line",
                        "Task.input.value[x]:valueAddress.period",
                        "Task.input.value[x]:valueAddress.postalCode",
                        "Task.input.value[x]:valueAddress.state",
                        "Task.input.value[x]:valueAddress.text",
                        "Task.input.value[x]:valueAddress.type",
                        "Task.input.value[x]:valueAddress.use",
                    ],
                ),
                "Task.input.value[x]:valueAddress.city": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueAddress",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueaddress_city",
                                path="city",
                                type="string",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueAddress.country": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueAddress",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueaddress_country",
                                path="country",
                                type="string",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueAddress.district": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueAddress",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueaddress_district",
                                path="district",
                                type="string",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueAddress.line": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueAddress",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="line",
                        select=[
                            ViewDefinitionSelect(
                                column=[
                                    ViewDefinitionColumn(
                                        name="Task_input_value_X_Valueaddress_line",
                                        path="$this",
                                        type="string",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueAddress.period": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueAddress",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="period",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueAddress.period.end",
                        "Task.input.value[x]:valueAddress.period.start",
                    ],
                ),
                "Task.input.value[x]:valueAddress.period.end": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueAddress.period",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueaddress_period_end",
                                path="end",
                                type="dateTime",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueAddress.period.start": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueAddress.period",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueaddress_period_start",
                                path="start",
                                type="dateTime",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueAddress.postalCode": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueAddress",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueaddress_postalCode",
                                path="postalCode",
                                type="string",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueAddress.state": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueAddress",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueaddress_state",
                                path="state",
                                type="string",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueAddress.text": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueAddress",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueaddress_text",
                                path="text",
                                type="string",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueAddress.type": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueAddress",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueaddress_type",
                                path="type",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueAddress.use": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueAddress",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueaddress_use",
                                path="use",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueAge": FlatteningLookupElement(
                    parent="Task.input.value[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(Age)",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueAge.code",
                        "Task.input.value[x]:valueAge.system",
                        "Task.input.value[x]:valueAge.value",
                    ],
                ),
                "Task.input.value[x]:valueAge.code": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueAge",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueage_code",
                                path="code",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueAge.system": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueAge",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueage_system",
                                path="system",
                                type="uri",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueAge.value": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueAge",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueage_value",
                                path="value",
                                type="decimal",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueAnnotation": FlatteningLookupElement(
                    parent="Task.input.value[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(Annotation)",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueAnnotation.author[x]",
                        "Task.input.value[x]:valueAnnotation.text",
                        "Task.input.value[x]:valueAnnotation.time",
                    ],
                ),
                "Task.input.value[x]:valueAnnotation.author[x]": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueAnnotation",
                    view_definition=ViewDefinitionSnippet(
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueAnnotation.author[x]:authorReference",
                        "Task.input.value[x]:valueAnnotation.author[x]:authorString",
                    ],
                ),
                "Task.input.value[x]:valueAnnotation.author[x]:authorReference": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueAnnotation.author[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="author.ofType(Reference)",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueAnnotation.author[x]:authorReference.reference",
                    ],
                ),
                "Task.input.value[x]:valueAnnotation.author[x]:authorReference.reference": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueAnnotation.author[x]:authorReference",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueannotation_author_X_Authorreference_reference",
                                path="reference",
                                type="string",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueAnnotation.author[x]:authorString": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueAnnotation.author[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="author.ofType(string)",
                        select=[
                            ViewDefinitionSelect(
                                column=[
                                    ViewDefinitionColumn(
                                        name="Task_input_value_X_Valueannotation_author_X_Authorstring",
                                        path="$this",
                                        type="string",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueAnnotation.text": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueAnnotation",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueannotation_text",
                                path="text",
                                type="markdown",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueAnnotation.time": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueAnnotation",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueannotation_time",
                                path="time",
                                type="dateTime",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueAttachment": FlatteningLookupElement(
                    parent="Task.input.value[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(Attachment)",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueAttachment.contentType",
                        "Task.input.value[x]:valueAttachment.creation",
                        "Task.input.value[x]:valueAttachment.data",
                        "Task.input.value[x]:valueAttachment.hash",
                        "Task.input.value[x]:valueAttachment.language",
                        "Task.input.value[x]:valueAttachment.size",
                        "Task.input.value[x]:valueAttachment.title",
                        "Task.input.value[x]:valueAttachment.url",
                    ],
                ),
                "Task.input.value[x]:valueAttachment.contentType": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueAttachment",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueattachment_contentType",
                                path="contentType",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueAttachment.creation": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueAttachment",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueattachment_creation",
                                path="creation",
                                type="dateTime",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueAttachment.data": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueAttachment",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueattachment_data",
                                path="data",
                                type="base64Binary",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueAttachment.hash": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueAttachment",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueattachment_hash",
                                path="hash",
                                type="base64Binary",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueAttachment.language": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueAttachment",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueattachment_language",
                                path="language",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueAttachment.size": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueAttachment",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueattachment_size",
                                path="size",
                                type="unsignedInt",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueAttachment.title": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueAttachment",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueattachment_title",
                                path="title",
                                type="string",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueAttachment.url": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueAttachment",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueattachment_url",
                                path="url",
                                type="url",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueBase64Binary": FlatteningLookupElement(
                    parent="Task.input.value[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(base64Binary)",
                        select=[
                            ViewDefinitionSelect(
                                column=[
                                    ViewDefinitionColumn(
                                        name="Task_input_value_X_Valuebase64binary",
                                        path="$this",
                                        type="base64Binary",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueBoolean": FlatteningLookupElement(
                    parent="Task.input.value[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(boolean)",
                        select=[
                            ViewDefinitionSelect(
                                column=[
                                    ViewDefinitionColumn(
                                        name="Task_input_value_X_Valueboolean",
                                        path="$this",
                                        type="boolean",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueCanonical": FlatteningLookupElement(
                    parent="Task.input.value[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(canonical)",
                        select=[
                            ViewDefinitionSelect(
                                column=[
                                    ViewDefinitionColumn(
                                        name="Task_input_value_X_Valuecanonical",
                                        path="$this",
                                        type="canonical",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueCode": FlatteningLookupElement(
                    parent="Task.input.value[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(code)",
                        select=[
                            ViewDefinitionSelect(
                                column=[
                                    ViewDefinitionColumn(
                                        name="Task_input_value_X_Valuecode",
                                        path="$this",
                                        type="code",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueCodeableConcept": FlatteningLookupElement(
                    parent="Task.input.value[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(CodeableConcept)",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueCodeableConcept.coding",
                    ],
                ),
                "Task.input.value[x]:valueCodeableConcept.coding": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueCodeableConcept",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="coding",
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuecodeableconcept_coding_system",
                                path="system",
                                type="uri",
                            ),
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuecodeableconcept_coding_code",
                                path="code",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueCoding": FlatteningLookupElement(
                    parent="Task.input.value[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(Coding)",
                        select=[
                            ViewDefinitionSelect(
                                column=[
                                    ViewDefinitionColumn(
                                        name="Task_input_value_X_Valuecoding_system",
                                        path="system",
                                        type="uri",
                                    ),
                                    ViewDefinitionColumn(
                                        name="Task_input_value_X_Valuecoding_code",
                                        path="code",
                                        type="code",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueContactPoint": FlatteningLookupElement(
                    parent="Task.input.value[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(ContactPoint)",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueContactPoint.period",
                        "Task.input.value[x]:valueContactPoint.rank",
                        "Task.input.value[x]:valueContactPoint.system",
                        "Task.input.value[x]:valueContactPoint.use",
                        "Task.input.value[x]:valueContactPoint.value",
                    ],
                ),
                "Task.input.value[x]:valueContactPoint.period": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueContactPoint",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="period",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueContactPoint.period.end",
                        "Task.input.value[x]:valueContactPoint.period.start",
                    ],
                ),
                "Task.input.value[x]:valueContactPoint.period.end": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueContactPoint.period",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuecontactpoint_period_end",
                                path="end",
                                type="dateTime",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueContactPoint.period.start": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueContactPoint.period",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuecontactpoint_period_start",
                                path="start",
                                type="dateTime",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueContactPoint.rank": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueContactPoint",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuecontactpoint_rank",
                                path="rank",
                                type="positiveInt",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueContactPoint.system": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueContactPoint",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuecontactpoint_system",
                                path="system",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueContactPoint.use": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueContactPoint",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuecontactpoint_use",
                                path="use",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueContactPoint.value": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueContactPoint",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuecontactpoint_value",
                                path="value",
                                type="string",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueContributor": FlatteningLookupElement(
                    parent="Task.input.value[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(Contributor)",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueContributor.name",
                        "Task.input.value[x]:valueContributor.type",
                    ],
                ),
                "Task.input.value[x]:valueContributor.name": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueContributor",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuecontributor_name",
                                path="name",
                                type="string",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueContributor.type": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueContributor",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuecontributor_type",
                                path="type",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueCount": FlatteningLookupElement(
                    parent="Task.input.value[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(Count)",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueCount.code",
                        "Task.input.value[x]:valueCount.system",
                        "Task.input.value[x]:valueCount.value",
                    ],
                ),
                "Task.input.value[x]:valueCount.code": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueCount",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuecount_code",
                                path="code",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueCount.system": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueCount",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuecount_system",
                                path="system",
                                type="uri",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueCount.value": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueCount",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuecount_value",
                                path="value",
                                type="decimal",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDataRequirement": FlatteningLookupElement(
                    parent="Task.input.value[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(DataRequirement)",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueDataRequirement.codeFilter",
                        "Task.input.value[x]:valueDataRequirement.dateFilter",
                        "Task.input.value[x]:valueDataRequirement.limit",
                        "Task.input.value[x]:valueDataRequirement.mustSupport",
                        "Task.input.value[x]:valueDataRequirement.profile",
                        "Task.input.value[x]:valueDataRequirement.sort",
                        "Task.input.value[x]:valueDataRequirement.subject[x]",
                        "Task.input.value[x]:valueDataRequirement.type",
                    ],
                ),
                "Task.input.value[x]:valueDataRequirement.codeFilter": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDataRequirement",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="codeFilter",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueDataRequirement.codeFilter.code",
                        "Task.input.value[x]:valueDataRequirement.codeFilter.path",
                        "Task.input.value[x]:valueDataRequirement.codeFilter.searchParam",
                        "Task.input.value[x]:valueDataRequirement.codeFilter.valueSet",
                    ],
                ),
                "Task.input.value[x]:valueDataRequirement.codeFilter.code": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDataRequirement.codeFilter",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="code",
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedatarequirement_codeFilter_code_system",
                                path="system",
                                type="uri",
                            ),
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedatarequirement_codeFilter_code_code",
                                path="code",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDataRequirement.codeFilter.path": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDataRequirement.codeFilter",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedatarequirement_codeFilter_path",
                                path="path",
                                type="string",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDataRequirement.codeFilter.searchParam": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDataRequirement.codeFilter",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedatarequirement_codeFilter_searchParam",
                                path="searchParam",
                                type="string",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDataRequirement.codeFilter.valueSet": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDataRequirement.codeFilter",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedatarequirement_codeFilter_valueSet",
                                path="valueSet",
                                type="canonical",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDataRequirement.dateFilter": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDataRequirement",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="dateFilter",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueDataRequirement.dateFilter.path",
                        "Task.input.value[x]:valueDataRequirement.dateFilter.searchParam",
                        "Task.input.value[x]:valueDataRequirement.dateFilter.value[x]",
                    ],
                ),
                "Task.input.value[x]:valueDataRequirement.dateFilter.path": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDataRequirement.dateFilter",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedatarequirement_dateFilter_path",
                                path="path",
                                type="string",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDataRequirement.dateFilter.searchParam": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDataRequirement.dateFilter",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedatarequirement_dateFilter_searchParam",
                                path="searchParam",
                                type="string",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDataRequirement.dateFilter.value[x]": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDataRequirement.dateFilter",
                    view_definition=ViewDefinitionSnippet(
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueDataRequirement.dateFilter.value[x]:valueDateTime",
                        "Task.input.value[x]:valueDataRequirement.dateFilter.value[x]:valueDuration",
                        "Task.input.value[x]:valueDataRequirement.dateFilter.value[x]:valuePeriod",
                    ],
                ),
                "Task.input.value[x]:valueDataRequirement.dateFilter.value[x]:valueDateTime": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDataRequirement.dateFilter.value[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(dateTime)",
                        select=[
                            ViewDefinitionSelect(
                                column=[
                                    ViewDefinitionColumn(
                                        name="Task_input_value_X_Valuedatarequirement_dateFilter_value_X_Valuedatetime",
                                        path="$this",
                                        type="dateTime",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDataRequirement.dateFilter.value[x]:valueDuration": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDataRequirement.dateFilter.value[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(Duration)",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueDataRequirement.dateFilter.value[x]:valueDuration.code",
                        "Task.input.value[x]:valueDataRequirement.dateFilter.value[x]:valueDuration.system",
                        "Task.input.value[x]:valueDataRequirement.dateFilter.value[x]:valueDuration.value",
                    ],
                ),
                "Task.input.value[x]:valueDataRequirement.dateFilter.value[x]:valueDuration.code": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDataRequirement.dateFilter.value[x]:valueDuration",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedatarequirement_dateFilter_value_X_Valueduration_code",
                                path="code",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDataRequirement.dateFilter.value[x]:valueDuration.system": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDataRequirement.dateFilter.value[x]:valueDuration",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedatarequirement_dateFilter_value_X_Valueduration_system",
                                path="system",
                                type="uri",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDataRequirement.dateFilter.value[x]:valueDuration.value": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDataRequirement.dateFilter.value[x]:valueDuration",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedatarequirement_dateFilter_value_X_Valueduration_value",
                                path="value",
                                type="decimal",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDataRequirement.dateFilter.value[x]:valuePeriod": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDataRequirement.dateFilter.value[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(Period)",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueDataRequirement.dateFilter.value[x]:valuePeriod.end",
                        "Task.input.value[x]:valueDataRequirement.dateFilter.value[x]:valuePeriod.start",
                    ],
                ),
                "Task.input.value[x]:valueDataRequirement.dateFilter.value[x]:valuePeriod.end": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDataRequirement.dateFilter.value[x]:valuePeriod",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedatarequirement_dateFilter_value_X_Valueperiod_end",
                                path="end",
                                type="dateTime",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDataRequirement.dateFilter.value[x]:valuePeriod.start": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDataRequirement.dateFilter.value[x]:valuePeriod",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedatarequirement_dateFilter_value_X_Valueperiod_start",
                                path="start",
                                type="dateTime",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDataRequirement.limit": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDataRequirement",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedatarequirement_limit",
                                path="limit",
                                type="positiveInt",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDataRequirement.mustSupport": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDataRequirement",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="mustSupport",
                        select=[
                            ViewDefinitionSelect(
                                column=[
                                    ViewDefinitionColumn(
                                        name="Task_input_value_X_Valuedatarequirement_mustSupport",
                                        path="$this",
                                        type="string",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDataRequirement.profile": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDataRequirement",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="profile",
                        select=[
                            ViewDefinitionSelect(
                                column=[
                                    ViewDefinitionColumn(
                                        name="Task_input_value_X_Valuedatarequirement_profile",
                                        path="$this",
                                        type="canonical",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDataRequirement.sort": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDataRequirement",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="sort",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueDataRequirement.sort.direction",
                        "Task.input.value[x]:valueDataRequirement.sort.path",
                    ],
                ),
                "Task.input.value[x]:valueDataRequirement.sort.direction": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDataRequirement.sort",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedatarequirement_sort_direction",
                                path="direction",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDataRequirement.sort.path": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDataRequirement.sort",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedatarequirement_sort_path",
                                path="path",
                                type="string",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDataRequirement.subject[x]": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDataRequirement",
                    view_definition=ViewDefinitionSnippet(
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueDataRequirement.subject[x]:subjectCodeableConcept",
                        "Task.input.value[x]:valueDataRequirement.subject[x]:subjectReference",
                    ],
                ),
                "Task.input.value[x]:valueDataRequirement.subject[x]:subjectCodeableConcept": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDataRequirement.subject[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="subject.ofType(CodeableConcept)",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueDataRequirement.subject[x]:subjectCodeableConcept.coding",
                    ],
                ),
                "Task.input.value[x]:valueDataRequirement.subject[x]:subjectCodeableConcept.coding": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDataRequirement.subject[x]:subjectCodeableConcept",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="coding",
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedatarequirement_subject_X_Subjectcodeableconcept_coding_system",
                                path="system",
                                type="uri",
                            ),
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedatarequirement_subject_X_Subjectcodeableconcept_coding_code",
                                path="code",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDataRequirement.subject[x]:subjectReference": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDataRequirement.subject[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="subject.ofType(Reference)",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueDataRequirement.subject[x]:subjectReference.reference",
                    ],
                ),
                "Task.input.value[x]:valueDataRequirement.subject[x]:subjectReference.reference": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDataRequirement.subject[x]:subjectReference",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedatarequirement_subject_X_Subjectreference_reference",
                                path="reference",
                                type="string",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDataRequirement.type": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDataRequirement",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedatarequirement_type",
                                path="type",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDate": FlatteningLookupElement(
                    parent="Task.input.value[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(date)",
                        select=[
                            ViewDefinitionSelect(
                                column=[
                                    ViewDefinitionColumn(
                                        name="Task_input_value_X_Valuedate",
                                        path="$this",
                                        type="date",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDateTime": FlatteningLookupElement(
                    parent="Task.input.value[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(dateTime)",
                        select=[
                            ViewDefinitionSelect(
                                column=[
                                    ViewDefinitionColumn(
                                        name="Task_input_value_X_Valuedatetime",
                                        path="$this",
                                        type="dateTime",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDecimal": FlatteningLookupElement(
                    parent="Task.input.value[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(decimal)",
                        select=[
                            ViewDefinitionSelect(
                                column=[
                                    ViewDefinitionColumn(
                                        name="Task_input_value_X_Valuedecimal",
                                        path="$this",
                                        type="decimal",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDistance": FlatteningLookupElement(
                    parent="Task.input.value[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(Distance)",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueDistance.code",
                        "Task.input.value[x]:valueDistance.system",
                        "Task.input.value[x]:valueDistance.value",
                    ],
                ),
                "Task.input.value[x]:valueDistance.code": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDistance",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedistance_code",
                                path="code",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDistance.system": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDistance",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedistance_system",
                                path="system",
                                type="uri",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDistance.value": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDistance",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedistance_value",
                                path="value",
                                type="decimal",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage": FlatteningLookupElement(
                    parent="Task.input.value[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(Dosage)",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueDosage.additionalInstruction",
                        "Task.input.value[x]:valueDosage.asNeeded[x]",
                        "Task.input.value[x]:valueDosage.doseAndRate",
                        "Task.input.value[x]:valueDosage.maxDosePerAdministration",
                        "Task.input.value[x]:valueDosage.maxDosePerLifetime",
                        "Task.input.value[x]:valueDosage.maxDosePerPeriod",
                        "Task.input.value[x]:valueDosage.method",
                        "Task.input.value[x]:valueDosage.patientInstruction",
                        "Task.input.value[x]:valueDosage.route",
                        "Task.input.value[x]:valueDosage.sequence",
                        "Task.input.value[x]:valueDosage.site",
                        "Task.input.value[x]:valueDosage.text",
                        "Task.input.value[x]:valueDosage.timing",
                    ],
                ),
                "Task.input.value[x]:valueDosage.additionalInstruction": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="additionalInstruction",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueDosage.additionalInstruction.coding",
                    ],
                ),
                "Task.input.value[x]:valueDosage.additionalInstruction.coding": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.additionalInstruction",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="coding",
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_additionalInstruction_coding_system",
                                path="system",
                                type="uri",
                            ),
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_additionalInstruction_coding_code",
                                path="code",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.asNeeded[x]": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage",
                    view_definition=ViewDefinitionSnippet(
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueDosage.asNeeded[x]:asNeededBoolean",
                        "Task.input.value[x]:valueDosage.asNeeded[x]:asNeededCodeableConcept",
                    ],
                ),
                "Task.input.value[x]:valueDosage.asNeeded[x]:asNeededBoolean": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.asNeeded[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="asNeeded.ofType(boolean)",
                        select=[
                            ViewDefinitionSelect(
                                column=[
                                    ViewDefinitionColumn(
                                        name="Task_input_value_X_Valuedosage_asNeeded_X_Asneededboolean",
                                        path="$this",
                                        type="boolean",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.asNeeded[x]:asNeededCodeableConcept": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.asNeeded[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="asNeeded.ofType(CodeableConcept)",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueDosage.asNeeded[x]:asNeededCodeableConcept.coding",
                    ],
                ),
                "Task.input.value[x]:valueDosage.asNeeded[x]:asNeededCodeableConcept.coding": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.asNeeded[x]:asNeededCodeableConcept",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="coding",
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_asNeeded_X_Asneededcodeableconcept_coding_system",
                                path="system",
                                type="uri",
                            ),
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_asNeeded_X_Asneededcodeableconcept_coding_code",
                                path="code",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.doseAndRate": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="doseAndRate",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueDosage.doseAndRate.dose[x]",
                        "Task.input.value[x]:valueDosage.doseAndRate.rate[x]",
                        "Task.input.value[x]:valueDosage.doseAndRate.type",
                    ],
                ),
                "Task.input.value[x]:valueDosage.doseAndRate.dose[x]": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.doseAndRate",
                    view_definition=ViewDefinitionSnippet(
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueDosage.doseAndRate.dose[x]:doseQuantity",
                        "Task.input.value[x]:valueDosage.doseAndRate.dose[x]:doseRange",
                    ],
                ),
                "Task.input.value[x]:valueDosage.doseAndRate.dose[x]:doseQuantity": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.doseAndRate.dose[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="dose.ofType(Quantity)",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueDosage.doseAndRate.dose[x]:doseQuantity.code",
                        "Task.input.value[x]:valueDosage.doseAndRate.dose[x]:doseQuantity.comparator",
                        "Task.input.value[x]:valueDosage.doseAndRate.dose[x]:doseQuantity.system",
                        "Task.input.value[x]:valueDosage.doseAndRate.dose[x]:doseQuantity.unit",
                        "Task.input.value[x]:valueDosage.doseAndRate.dose[x]:doseQuantity.value",
                    ],
                ),
                "Task.input.value[x]:valueDosage.doseAndRate.dose[x]:doseQuantity.code": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.doseAndRate.dose[x]:doseQuantity",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_doseAndRate_dose_X_Dosequantity_code",
                                path="code",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.doseAndRate.dose[x]:doseQuantity.comparator": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.doseAndRate.dose[x]:doseQuantity",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_doseAndRate_dose_X_Dosequantity_comparator",
                                path="comparator",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.doseAndRate.dose[x]:doseQuantity.system": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.doseAndRate.dose[x]:doseQuantity",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_doseAndRate_dose_X_Dosequantity_system",
                                path="system",
                                type="uri",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.doseAndRate.dose[x]:doseQuantity.unit": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.doseAndRate.dose[x]:doseQuantity",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_doseAndRate_dose_X_Dosequantity_unit",
                                path="unit",
                                type="string",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.doseAndRate.dose[x]:doseQuantity.value": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.doseAndRate.dose[x]:doseQuantity",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_doseAndRate_dose_X_Dosequantity_value",
                                path="value",
                                type="decimal",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.doseAndRate.dose[x]:doseRange": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.doseAndRate.dose[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="dose.ofType(Range)",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueDosage.doseAndRate.dose[x]:doseRange.high",
                        "Task.input.value[x]:valueDosage.doseAndRate.dose[x]:doseRange.low",
                    ],
                ),
                "Task.input.value[x]:valueDosage.doseAndRate.dose[x]:doseRange.high": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.doseAndRate.dose[x]:doseRange",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="high",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueDosage.doseAndRate.dose[x]:doseRange.high.code",
                        "Task.input.value[x]:valueDosage.doseAndRate.dose[x]:doseRange.high.comparator",
                        "Task.input.value[x]:valueDosage.doseAndRate.dose[x]:doseRange.high.system",
                        "Task.input.value[x]:valueDosage.doseAndRate.dose[x]:doseRange.high.unit",
                        "Task.input.value[x]:valueDosage.doseAndRate.dose[x]:doseRange.high.value",
                    ],
                ),
                "Task.input.value[x]:valueDosage.doseAndRate.dose[x]:doseRange.high.code": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.doseAndRate.dose[x]:doseRange.high",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_doseAndRate_dose_X_Doserange_high_code",
                                path="code",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.doseAndRate.dose[x]:doseRange.high.comparator": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.doseAndRate.dose[x]:doseRange.high",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_doseAndRate_dose_X_Doserange_high_comparator",
                                path="comparator",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.doseAndRate.dose[x]:doseRange.high.system": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.doseAndRate.dose[x]:doseRange.high",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_doseAndRate_dose_X_Doserange_high_system",
                                path="system",
                                type="uri",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.doseAndRate.dose[x]:doseRange.high.unit": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.doseAndRate.dose[x]:doseRange.high",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_doseAndRate_dose_X_Doserange_high_unit",
                                path="unit",
                                type="string",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.doseAndRate.dose[x]:doseRange.high.value": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.doseAndRate.dose[x]:doseRange.high",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_doseAndRate_dose_X_Doserange_high_value",
                                path="value",
                                type="decimal",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.doseAndRate.dose[x]:doseRange.low": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.doseAndRate.dose[x]:doseRange",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="low",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueDosage.doseAndRate.dose[x]:doseRange.low.code",
                        "Task.input.value[x]:valueDosage.doseAndRate.dose[x]:doseRange.low.comparator",
                        "Task.input.value[x]:valueDosage.doseAndRate.dose[x]:doseRange.low.system",
                        "Task.input.value[x]:valueDosage.doseAndRate.dose[x]:doseRange.low.unit",
                        "Task.input.value[x]:valueDosage.doseAndRate.dose[x]:doseRange.low.value",
                    ],
                ),
                "Task.input.value[x]:valueDosage.doseAndRate.dose[x]:doseRange.low.code": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.doseAndRate.dose[x]:doseRange.low",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_doseAndRate_dose_X_Doserange_low_code",
                                path="code",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.doseAndRate.dose[x]:doseRange.low.comparator": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.doseAndRate.dose[x]:doseRange.low",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_doseAndRate_dose_X_Doserange_low_comparator",
                                path="comparator",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.doseAndRate.dose[x]:doseRange.low.system": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.doseAndRate.dose[x]:doseRange.low",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_doseAndRate_dose_X_Doserange_low_system",
                                path="system",
                                type="uri",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.doseAndRate.dose[x]:doseRange.low.unit": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.doseAndRate.dose[x]:doseRange.low",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_doseAndRate_dose_X_Doserange_low_unit",
                                path="unit",
                                type="string",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.doseAndRate.dose[x]:doseRange.low.value": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.doseAndRate.dose[x]:doseRange.low",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_doseAndRate_dose_X_Doserange_low_value",
                                path="value",
                                type="decimal",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.doseAndRate.rate[x]": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.doseAndRate",
                    view_definition=ViewDefinitionSnippet(
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateQuantity",
                        "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRange",
                        "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRatio",
                    ],
                ),
                "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateQuantity": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.doseAndRate.rate[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="rate.ofType(Quantity)",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateQuantity.code",
                        "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateQuantity.comparator",
                        "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateQuantity.system",
                        "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateQuantity.unit",
                        "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateQuantity.value",
                    ],
                ),
                "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateQuantity.code": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateQuantity",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_doseAndRate_rate_X_Ratequantity_code",
                                path="code",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateQuantity.comparator": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateQuantity",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_doseAndRate_rate_X_Ratequantity_comparator",
                                path="comparator",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateQuantity.system": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateQuantity",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_doseAndRate_rate_X_Ratequantity_system",
                                path="system",
                                type="uri",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateQuantity.unit": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateQuantity",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_doseAndRate_rate_X_Ratequantity_unit",
                                path="unit",
                                type="string",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateQuantity.value": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateQuantity",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_doseAndRate_rate_X_Ratequantity_value",
                                path="value",
                                type="decimal",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRange": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.doseAndRate.rate[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="rate.ofType(Range)",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRange.high",
                        "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRange.low",
                    ],
                ),
                "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRange.high": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRange",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="high",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRange.high.code",
                        "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRange.high.comparator",
                        "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRange.high.system",
                        "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRange.high.unit",
                        "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRange.high.value",
                    ],
                ),
                "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRange.high.code": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRange.high",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_doseAndRate_rate_X_Raterange_high_code",
                                path="code",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRange.high.comparator": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRange.high",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_doseAndRate_rate_X_Raterange_high_comparator",
                                path="comparator",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRange.high.system": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRange.high",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_doseAndRate_rate_X_Raterange_high_system",
                                path="system",
                                type="uri",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRange.high.unit": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRange.high",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_doseAndRate_rate_X_Raterange_high_unit",
                                path="unit",
                                type="string",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRange.high.value": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRange.high",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_doseAndRate_rate_X_Raterange_high_value",
                                path="value",
                                type="decimal",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRange.low": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRange",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="low",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRange.low.code",
                        "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRange.low.comparator",
                        "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRange.low.system",
                        "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRange.low.unit",
                        "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRange.low.value",
                    ],
                ),
                "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRange.low.code": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRange.low",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_doseAndRate_rate_X_Raterange_low_code",
                                path="code",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRange.low.comparator": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRange.low",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_doseAndRate_rate_X_Raterange_low_comparator",
                                path="comparator",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRange.low.system": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRange.low",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_doseAndRate_rate_X_Raterange_low_system",
                                path="system",
                                type="uri",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRange.low.unit": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRange.low",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_doseAndRate_rate_X_Raterange_low_unit",
                                path="unit",
                                type="string",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRange.low.value": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRange.low",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_doseAndRate_rate_X_Raterange_low_value",
                                path="value",
                                type="decimal",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRatio": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.doseAndRate.rate[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="rate.ofType(Ratio)",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRatio.denominator",
                        "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRatio.numerator",
                    ],
                ),
                "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRatio.denominator": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRatio",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="denominator",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRatio.denominator.code",
                        "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRatio.denominator.comparator",
                        "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRatio.denominator.system",
                        "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRatio.denominator.unit",
                        "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRatio.denominator.value",
                    ],
                ),
                "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRatio.denominator.code": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRatio.denominator",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_doseAndRate_rate_X_Rateratio_denominator_code",
                                path="code",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRatio.denominator.comparator": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRatio.denominator",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_doseAndRate_rate_X_Rateratio_denominator_comparator",
                                path="comparator",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRatio.denominator.system": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRatio.denominator",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_doseAndRate_rate_X_Rateratio_denominator_system",
                                path="system",
                                type="uri",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRatio.denominator.unit": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRatio.denominator",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_doseAndRate_rate_X_Rateratio_denominator_unit",
                                path="unit",
                                type="string",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRatio.denominator.value": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRatio.denominator",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_doseAndRate_rate_X_Rateratio_denominator_value",
                                path="value",
                                type="decimal",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRatio.numerator": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRatio",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="numerator",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRatio.numerator.code",
                        "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRatio.numerator.comparator",
                        "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRatio.numerator.system",
                        "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRatio.numerator.unit",
                        "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRatio.numerator.value",
                    ],
                ),
                "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRatio.numerator.code": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRatio.numerator",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_doseAndRate_rate_X_Rateratio_numerator_code",
                                path="code",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRatio.numerator.comparator": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRatio.numerator",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_doseAndRate_rate_X_Rateratio_numerator_comparator",
                                path="comparator",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRatio.numerator.system": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRatio.numerator",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_doseAndRate_rate_X_Rateratio_numerator_system",
                                path="system",
                                type="uri",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRatio.numerator.unit": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRatio.numerator",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_doseAndRate_rate_X_Rateratio_numerator_unit",
                                path="unit",
                                type="string",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRatio.numerator.value": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.doseAndRate.rate[x]:rateRatio.numerator",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_doseAndRate_rate_X_Rateratio_numerator_value",
                                path="value",
                                type="decimal",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.doseAndRate.type": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.doseAndRate",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="type",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueDosage.doseAndRate.type.coding",
                    ],
                ),
                "Task.input.value[x]:valueDosage.doseAndRate.type.coding": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.doseAndRate.type",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="coding",
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_doseAndRate_type_coding_system",
                                path="system",
                                type="uri",
                            ),
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_doseAndRate_type_coding_code",
                                path="code",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.maxDosePerAdministration": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="maxDosePerAdministration",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueDosage.maxDosePerAdministration.code",
                        "Task.input.value[x]:valueDosage.maxDosePerAdministration.system",
                        "Task.input.value[x]:valueDosage.maxDosePerAdministration.value",
                    ],
                ),
                "Task.input.value[x]:valueDosage.maxDosePerAdministration.code": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.maxDosePerAdministration",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_maxDosePerAdministration_code",
                                path="code",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.maxDosePerAdministration.system": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.maxDosePerAdministration",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_maxDosePerAdministration_system",
                                path="system",
                                type="uri",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.maxDosePerAdministration.value": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.maxDosePerAdministration",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_maxDosePerAdministration_value",
                                path="value",
                                type="decimal",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.maxDosePerLifetime": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="maxDosePerLifetime",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueDosage.maxDosePerLifetime.code",
                        "Task.input.value[x]:valueDosage.maxDosePerLifetime.system",
                        "Task.input.value[x]:valueDosage.maxDosePerLifetime.value",
                    ],
                ),
                "Task.input.value[x]:valueDosage.maxDosePerLifetime.code": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.maxDosePerLifetime",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_maxDosePerLifetime_code",
                                path="code",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.maxDosePerLifetime.system": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.maxDosePerLifetime",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_maxDosePerLifetime_system",
                                path="system",
                                type="uri",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.maxDosePerLifetime.value": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.maxDosePerLifetime",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_maxDosePerLifetime_value",
                                path="value",
                                type="decimal",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.maxDosePerPeriod": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="maxDosePerPeriod",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueDosage.maxDosePerPeriod.denominator",
                        "Task.input.value[x]:valueDosage.maxDosePerPeriod.numerator",
                    ],
                ),
                "Task.input.value[x]:valueDosage.maxDosePerPeriod.denominator": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.maxDosePerPeriod",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="denominator",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueDosage.maxDosePerPeriod.denominator.code",
                        "Task.input.value[x]:valueDosage.maxDosePerPeriod.denominator.comparator",
                        "Task.input.value[x]:valueDosage.maxDosePerPeriod.denominator.system",
                        "Task.input.value[x]:valueDosage.maxDosePerPeriod.denominator.unit",
                        "Task.input.value[x]:valueDosage.maxDosePerPeriod.denominator.value",
                    ],
                ),
                "Task.input.value[x]:valueDosage.maxDosePerPeriod.denominator.code": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.maxDosePerPeriod.denominator",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_maxDosePerPeriod_denominator_code",
                                path="code",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.maxDosePerPeriod.denominator.comparator": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.maxDosePerPeriod.denominator",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_maxDosePerPeriod_denominator_comparator",
                                path="comparator",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.maxDosePerPeriod.denominator.system": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.maxDosePerPeriod.denominator",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_maxDosePerPeriod_denominator_system",
                                path="system",
                                type="uri",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.maxDosePerPeriod.denominator.unit": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.maxDosePerPeriod.denominator",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_maxDosePerPeriod_denominator_unit",
                                path="unit",
                                type="string",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.maxDosePerPeriod.denominator.value": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.maxDosePerPeriod.denominator",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_maxDosePerPeriod_denominator_value",
                                path="value",
                                type="decimal",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.maxDosePerPeriod.numerator": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.maxDosePerPeriod",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="numerator",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueDosage.maxDosePerPeriod.numerator.code",
                        "Task.input.value[x]:valueDosage.maxDosePerPeriod.numerator.comparator",
                        "Task.input.value[x]:valueDosage.maxDosePerPeriod.numerator.system",
                        "Task.input.value[x]:valueDosage.maxDosePerPeriod.numerator.unit",
                        "Task.input.value[x]:valueDosage.maxDosePerPeriod.numerator.value",
                    ],
                ),
                "Task.input.value[x]:valueDosage.maxDosePerPeriod.numerator.code": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.maxDosePerPeriod.numerator",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_maxDosePerPeriod_numerator_code",
                                path="code",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.maxDosePerPeriod.numerator.comparator": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.maxDosePerPeriod.numerator",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_maxDosePerPeriod_numerator_comparator",
                                path="comparator",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.maxDosePerPeriod.numerator.system": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.maxDosePerPeriod.numerator",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_maxDosePerPeriod_numerator_system",
                                path="system",
                                type="uri",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.maxDosePerPeriod.numerator.unit": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.maxDosePerPeriod.numerator",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_maxDosePerPeriod_numerator_unit",
                                path="unit",
                                type="string",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.maxDosePerPeriod.numerator.value": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.maxDosePerPeriod.numerator",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_maxDosePerPeriod_numerator_value",
                                path="value",
                                type="decimal",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.method": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="method",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueDosage.method.coding",
                    ],
                ),
                "Task.input.value[x]:valueDosage.method.coding": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.method",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="coding",
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_method_coding_system",
                                path="system",
                                type="uri",
                            ),
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_method_coding_code",
                                path="code",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.patientInstruction": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_patientInstruction",
                                path="patientInstruction",
                                type="string",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.route": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="route",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueDosage.route.coding",
                    ],
                ),
                "Task.input.value[x]:valueDosage.route.coding": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.route",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="coding",
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_route_coding_system",
                                path="system",
                                type="uri",
                            ),
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_route_coding_code",
                                path="code",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.sequence": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_sequence",
                                path="sequence",
                                type="integer",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.site": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="site",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueDosage.site.coding",
                    ],
                ),
                "Task.input.value[x]:valueDosage.site.coding": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.site",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="coding",
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_site_coding_system",
                                path="system",
                                type="uri",
                            ),
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_site_coding_code",
                                path="code",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.text": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_text",
                                path="text",
                                type="string",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.timing": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="timing",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueDosage.timing.code",
                        "Task.input.value[x]:valueDosage.timing.event",
                        "Task.input.value[x]:valueDosage.timing.repeat",
                    ],
                ),
                "Task.input.value[x]:valueDosage.timing.code": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.timing",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="code",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueDosage.timing.code.coding",
                    ],
                ),
                "Task.input.value[x]:valueDosage.timing.code.coding": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.timing.code",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="coding",
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_timing_code_coding_system",
                                path="system",
                                type="uri",
                            ),
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_timing_code_coding_code",
                                path="code",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.timing.event": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.timing",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="event",
                        select=[
                            ViewDefinitionSelect(
                                column=[
                                    ViewDefinitionColumn(
                                        name="Task_input_value_X_Valuedosage_timing_event",
                                        path="$this",
                                        type="dateTime",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.timing.repeat": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.timing",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="repeat",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueDosage.timing.repeat.bounds[x]",
                        "Task.input.value[x]:valueDosage.timing.repeat.count",
                        "Task.input.value[x]:valueDosage.timing.repeat.countMax",
                        "Task.input.value[x]:valueDosage.timing.repeat.dayOfWeek",
                        "Task.input.value[x]:valueDosage.timing.repeat.duration",
                        "Task.input.value[x]:valueDosage.timing.repeat.durationMax",
                        "Task.input.value[x]:valueDosage.timing.repeat.durationUnit",
                        "Task.input.value[x]:valueDosage.timing.repeat.frequency",
                        "Task.input.value[x]:valueDosage.timing.repeat.frequencyMax",
                        "Task.input.value[x]:valueDosage.timing.repeat.offset",
                        "Task.input.value[x]:valueDosage.timing.repeat.period",
                        "Task.input.value[x]:valueDosage.timing.repeat.periodMax",
                        "Task.input.value[x]:valueDosage.timing.repeat.periodUnit",
                        "Task.input.value[x]:valueDosage.timing.repeat.timeOfDay",
                        "Task.input.value[x]:valueDosage.timing.repeat.when",
                    ],
                ),
                "Task.input.value[x]:valueDosage.timing.repeat.bounds[x]": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.timing.repeat",
                    view_definition=ViewDefinitionSnippet(
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsDuration",
                        "Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsPeriod",
                        "Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsRange",
                    ],
                ),
                "Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsDuration": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.timing.repeat.bounds[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="bounds.ofType(Duration)",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsDuration.code",
                        "Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsDuration.system",
                        "Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsDuration.value",
                    ],
                ),
                "Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsDuration.code": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsDuration",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_timing_repeat_bounds_X_Boundsduration_code",
                                path="code",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsDuration.system": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsDuration",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_timing_repeat_bounds_X_Boundsduration_system",
                                path="system",
                                type="uri",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsDuration.value": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsDuration",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_timing_repeat_bounds_X_Boundsduration_value",
                                path="value",
                                type="decimal",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsPeriod": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.timing.repeat.bounds[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="bounds.ofType(Period)",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsPeriod.end",
                        "Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsPeriod.start",
                    ],
                ),
                "Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsPeriod.end": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsPeriod",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_timing_repeat_bounds_X_Boundsperiod_end",
                                path="end",
                                type="dateTime",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsPeriod.start": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsPeriod",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_timing_repeat_bounds_X_Boundsperiod_start",
                                path="start",
                                type="dateTime",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsRange": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.timing.repeat.bounds[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="bounds.ofType(Range)",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsRange.high",
                        "Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsRange.low",
                    ],
                ),
                "Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsRange.high": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsRange",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="high",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsRange.high.code",
                        "Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsRange.high.comparator",
                        "Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsRange.high.system",
                        "Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsRange.high.unit",
                        "Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsRange.high.value",
                    ],
                ),
                "Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsRange.high.code": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsRange.high",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_timing_repeat_bounds_X_Boundsrange_high_code",
                                path="code",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsRange.high.comparator": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsRange.high",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_timing_repeat_bounds_X_Boundsrange_high_comparator",
                                path="comparator",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsRange.high.system": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsRange.high",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_timing_repeat_bounds_X_Boundsrange_high_system",
                                path="system",
                                type="uri",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsRange.high.unit": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsRange.high",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_timing_repeat_bounds_X_Boundsrange_high_unit",
                                path="unit",
                                type="string",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsRange.high.value": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsRange.high",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_timing_repeat_bounds_X_Boundsrange_high_value",
                                path="value",
                                type="decimal",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsRange.low": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsRange",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="low",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsRange.low.code",
                        "Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsRange.low.comparator",
                        "Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsRange.low.system",
                        "Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsRange.low.unit",
                        "Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsRange.low.value",
                    ],
                ),
                "Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsRange.low.code": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsRange.low",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_timing_repeat_bounds_X_Boundsrange_low_code",
                                path="code",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsRange.low.comparator": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsRange.low",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_timing_repeat_bounds_X_Boundsrange_low_comparator",
                                path="comparator",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsRange.low.system": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsRange.low",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_timing_repeat_bounds_X_Boundsrange_low_system",
                                path="system",
                                type="uri",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsRange.low.unit": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsRange.low",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_timing_repeat_bounds_X_Boundsrange_low_unit",
                                path="unit",
                                type="string",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsRange.low.value": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.timing.repeat.bounds[x]:boundsRange.low",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_timing_repeat_bounds_X_Boundsrange_low_value",
                                path="value",
                                type="decimal",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.timing.repeat.count": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.timing.repeat",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_timing_repeat_count",
                                path="count",
                                type="positiveInt",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.timing.repeat.countMax": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.timing.repeat",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_timing_repeat_countMax",
                                path="countMax",
                                type="positiveInt",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.timing.repeat.dayOfWeek": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.timing.repeat",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="dayOfWeek",
                        select=[
                            ViewDefinitionSelect(
                                column=[
                                    ViewDefinitionColumn(
                                        name="Task_input_value_X_Valuedosage_timing_repeat_dayOfWeek",
                                        path="$this",
                                        type="code",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.timing.repeat.duration": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.timing.repeat",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_timing_repeat_duration",
                                path="duration",
                                type="decimal",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.timing.repeat.durationMax": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.timing.repeat",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_timing_repeat_durationMax",
                                path="durationMax",
                                type="decimal",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.timing.repeat.durationUnit": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.timing.repeat",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_timing_repeat_durationUnit",
                                path="durationUnit",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.timing.repeat.frequency": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.timing.repeat",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_timing_repeat_frequency",
                                path="frequency",
                                type="positiveInt",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.timing.repeat.frequencyMax": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.timing.repeat",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_timing_repeat_frequencyMax",
                                path="frequencyMax",
                                type="positiveInt",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.timing.repeat.offset": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.timing.repeat",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_timing_repeat_offset",
                                path="offset",
                                type="unsignedInt",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.timing.repeat.period": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.timing.repeat",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_timing_repeat_period",
                                path="period",
                                type="decimal",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.timing.repeat.periodMax": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.timing.repeat",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_timing_repeat_periodMax",
                                path="periodMax",
                                type="decimal",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.timing.repeat.periodUnit": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.timing.repeat",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuedosage_timing_repeat_periodUnit",
                                path="periodUnit",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.timing.repeat.timeOfDay": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.timing.repeat",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="timeOfDay",
                        select=[
                            ViewDefinitionSelect(
                                column=[
                                    ViewDefinitionColumn(
                                        name="Task_input_value_X_Valuedosage_timing_repeat_timeOfDay",
                                        path="$this",
                                        type="time",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDosage.timing.repeat.when": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDosage.timing.repeat",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="when",
                        select=[
                            ViewDefinitionSelect(
                                column=[
                                    ViewDefinitionColumn(
                                        name="Task_input_value_X_Valuedosage_timing_repeat_when",
                                        path="$this",
                                        type="code",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDuration": FlatteningLookupElement(
                    parent="Task.input.value[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(Duration)",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueDuration.code",
                        "Task.input.value[x]:valueDuration.system",
                        "Task.input.value[x]:valueDuration.value",
                    ],
                ),
                "Task.input.value[x]:valueDuration.code": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDuration",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueduration_code",
                                path="code",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDuration.system": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDuration",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueduration_system",
                                path="system",
                                type="uri",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueDuration.value": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueDuration",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueduration_value",
                                path="value",
                                type="decimal",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueInstant": FlatteningLookupElement(
                    parent="Task.input.value[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(instant)",
                        select=[
                            ViewDefinitionSelect(
                                column=[
                                    ViewDefinitionColumn(
                                        name="Task_input_value_X_Valueinstant",
                                        path="$this",
                                        type="instant",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueInteger": FlatteningLookupElement(
                    parent="Task.input.value[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(integer)",
                        select=[
                            ViewDefinitionSelect(
                                column=[
                                    ViewDefinitionColumn(
                                        name="Task_input_value_X_Valueinteger",
                                        path="$this",
                                        type="integer",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueMarkdown": FlatteningLookupElement(
                    parent="Task.input.value[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(markdown)",
                        select=[
                            ViewDefinitionSelect(
                                column=[
                                    ViewDefinitionColumn(
                                        name="Task_input_value_X_Valuemarkdown",
                                        path="$this",
                                        type="markdown",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueMeta": FlatteningLookupElement(
                    parent="Task.input.value[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(Meta)",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueMeta.lastUpdated",
                        "Task.input.value[x]:valueMeta.profile",
                        "Task.input.value[x]:valueMeta.security",
                        "Task.input.value[x]:valueMeta.source",
                        "Task.input.value[x]:valueMeta.tag",
                    ],
                ),
                "Task.input.value[x]:valueMeta.lastUpdated": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueMeta",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuemeta_lastUpdated",
                                path="lastUpdated",
                                type="instant",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueMeta.profile": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueMeta",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="profile",
                        select=[
                            ViewDefinitionSelect(
                                column=[
                                    ViewDefinitionColumn(
                                        name="Task_input_value_X_Valuemeta_profile",
                                        path="$this",
                                        type="canonical",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueMeta.security": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueMeta",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="security",
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuemeta_security_system",
                                path="system",
                                type="uri",
                            ),
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuemeta_security_code",
                                path="code",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueMeta.source": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueMeta",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuemeta_source",
                                path="source",
                                type="uri",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueMeta.tag": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueMeta",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="tag",
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuemeta_tag_system",
                                path="system",
                                type="uri",
                            ),
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuemeta_tag_code",
                                path="code",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueOid": FlatteningLookupElement(
                    parent="Task.input.value[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(oid)",
                        select=[
                            ViewDefinitionSelect(
                                column=[
                                    ViewDefinitionColumn(
                                        name="Task_input_value_X_Valueoid",
                                        path="$this",
                                        type="oid",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valuePeriod": FlatteningLookupElement(
                    parent="Task.input.value[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(Period)",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valuePeriod.end",
                        "Task.input.value[x]:valuePeriod.start",
                    ],
                ),
                "Task.input.value[x]:valuePeriod.end": FlatteningLookupElement(
                    parent="Task.input.value[x]:valuePeriod",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueperiod_end",
                                path="end",
                                type="dateTime",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valuePeriod.start": FlatteningLookupElement(
                    parent="Task.input.value[x]:valuePeriod",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueperiod_start",
                                path="start",
                                type="dateTime",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valuePositiveInt": FlatteningLookupElement(
                    parent="Task.input.value[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(positiveInt)",
                        select=[
                            ViewDefinitionSelect(
                                column=[
                                    ViewDefinitionColumn(
                                        name="Task_input_value_X_Valuepositiveint",
                                        path="$this",
                                        type="positiveInt",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueQuantity": FlatteningLookupElement(
                    parent="Task.input.value[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(Quantity)",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueQuantity.code",
                        "Task.input.value[x]:valueQuantity.comparator",
                        "Task.input.value[x]:valueQuantity.system",
                        "Task.input.value[x]:valueQuantity.unit",
                        "Task.input.value[x]:valueQuantity.value",
                    ],
                ),
                "Task.input.value[x]:valueQuantity.code": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueQuantity",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuequantity_code",
                                path="code",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueQuantity.comparator": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueQuantity",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuequantity_comparator",
                                path="comparator",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueQuantity.system": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueQuantity",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuequantity_system",
                                path="system",
                                type="uri",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueQuantity.unit": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueQuantity",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuequantity_unit",
                                path="unit",
                                type="string",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueQuantity.value": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueQuantity",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuequantity_value",
                                path="value",
                                type="decimal",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueRange": FlatteningLookupElement(
                    parent="Task.input.value[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(Range)",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueRange.high",
                        "Task.input.value[x]:valueRange.low",
                    ],
                ),
                "Task.input.value[x]:valueRange.high": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueRange",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="high",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueRange.high.code",
                        "Task.input.value[x]:valueRange.high.comparator",
                        "Task.input.value[x]:valueRange.high.system",
                        "Task.input.value[x]:valueRange.high.unit",
                        "Task.input.value[x]:valueRange.high.value",
                    ],
                ),
                "Task.input.value[x]:valueRange.high.code": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueRange.high",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuerange_high_code",
                                path="code",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueRange.high.comparator": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueRange.high",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuerange_high_comparator",
                                path="comparator",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueRange.high.system": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueRange.high",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuerange_high_system",
                                path="system",
                                type="uri",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueRange.high.unit": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueRange.high",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuerange_high_unit",
                                path="unit",
                                type="string",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueRange.high.value": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueRange.high",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuerange_high_value",
                                path="value",
                                type="decimal",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueRange.low": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueRange",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="low",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueRange.low.code",
                        "Task.input.value[x]:valueRange.low.comparator",
                        "Task.input.value[x]:valueRange.low.system",
                        "Task.input.value[x]:valueRange.low.unit",
                        "Task.input.value[x]:valueRange.low.value",
                    ],
                ),
                "Task.input.value[x]:valueRange.low.code": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueRange.low",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuerange_low_code",
                                path="code",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueRange.low.comparator": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueRange.low",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuerange_low_comparator",
                                path="comparator",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueRange.low.system": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueRange.low",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuerange_low_system",
                                path="system",
                                type="uri",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueRange.low.unit": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueRange.low",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuerange_low_unit",
                                path="unit",
                                type="string",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueRange.low.value": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueRange.low",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuerange_low_value",
                                path="value",
                                type="decimal",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueRatio": FlatteningLookupElement(
                    parent="Task.input.value[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(Ratio)",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueRatio.denominator",
                        "Task.input.value[x]:valueRatio.numerator",
                    ],
                ),
                "Task.input.value[x]:valueRatio.denominator": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueRatio",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="denominator",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueRatio.denominator.code",
                        "Task.input.value[x]:valueRatio.denominator.comparator",
                        "Task.input.value[x]:valueRatio.denominator.system",
                        "Task.input.value[x]:valueRatio.denominator.unit",
                        "Task.input.value[x]:valueRatio.denominator.value",
                    ],
                ),
                "Task.input.value[x]:valueRatio.denominator.code": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueRatio.denominator",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueratio_denominator_code",
                                path="code",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueRatio.denominator.comparator": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueRatio.denominator",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueratio_denominator_comparator",
                                path="comparator",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueRatio.denominator.system": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueRatio.denominator",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueratio_denominator_system",
                                path="system",
                                type="uri",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueRatio.denominator.unit": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueRatio.denominator",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueratio_denominator_unit",
                                path="unit",
                                type="string",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueRatio.denominator.value": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueRatio.denominator",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueratio_denominator_value",
                                path="value",
                                type="decimal",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueRatio.numerator": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueRatio",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="numerator",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueRatio.numerator.code",
                        "Task.input.value[x]:valueRatio.numerator.comparator",
                        "Task.input.value[x]:valueRatio.numerator.system",
                        "Task.input.value[x]:valueRatio.numerator.unit",
                        "Task.input.value[x]:valueRatio.numerator.value",
                    ],
                ),
                "Task.input.value[x]:valueRatio.numerator.code": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueRatio.numerator",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueratio_numerator_code",
                                path="code",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueRatio.numerator.comparator": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueRatio.numerator",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueratio_numerator_comparator",
                                path="comparator",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueRatio.numerator.system": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueRatio.numerator",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueratio_numerator_system",
                                path="system",
                                type="uri",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueRatio.numerator.unit": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueRatio.numerator",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueratio_numerator_unit",
                                path="unit",
                                type="string",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueRatio.numerator.value": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueRatio.numerator",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueratio_numerator_value",
                                path="value",
                                type="decimal",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueReference": FlatteningLookupElement(
                    parent="Task.input.value[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(Reference)",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueReference.reference",
                    ],
                ),
                "Task.input.value[x]:valueReference.reference": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueReference",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuereference_reference",
                                path="reference",
                                type="string",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueSampledData": FlatteningLookupElement(
                    parent="Task.input.value[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(SampledData)",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueSampledData.data",
                        "Task.input.value[x]:valueSampledData.dimensions",
                        "Task.input.value[x]:valueSampledData.factor",
                        "Task.input.value[x]:valueSampledData.lowerLimit",
                        "Task.input.value[x]:valueSampledData.origin",
                        "Task.input.value[x]:valueSampledData.period",
                        "Task.input.value[x]:valueSampledData.upperLimit",
                    ],
                ),
                "Task.input.value[x]:valueSampledData.data": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueSampledData",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuesampleddata_data",
                                path="data",
                                type="string",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueSampledData.dimensions": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueSampledData",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuesampleddata_dimensions",
                                path="dimensions",
                                type="positiveInt",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueSampledData.factor": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueSampledData",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuesampleddata_factor",
                                path="factor",
                                type="decimal",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueSampledData.lowerLimit": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueSampledData",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuesampleddata_lowerLimit",
                                path="lowerLimit",
                                type="decimal",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueSampledData.origin": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueSampledData",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="origin",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueSampledData.origin.code",
                        "Task.input.value[x]:valueSampledData.origin.system",
                        "Task.input.value[x]:valueSampledData.origin.value",
                    ],
                ),
                "Task.input.value[x]:valueSampledData.origin.code": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueSampledData.origin",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuesampleddata_origin_code",
                                path="code",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueSampledData.origin.system": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueSampledData.origin",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuesampleddata_origin_system",
                                path="system",
                                type="uri",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueSampledData.origin.value": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueSampledData.origin",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuesampleddata_origin_value",
                                path="value",
                                type="decimal",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueSampledData.period": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueSampledData",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuesampleddata_period",
                                path="period",
                                type="decimal",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueSampledData.upperLimit": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueSampledData",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuesampleddata_upperLimit",
                                path="upperLimit",
                                type="decimal",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueString": FlatteningLookupElement(
                    parent="Task.input.value[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(string)",
                        select=[
                            ViewDefinitionSelect(
                                column=[
                                    ViewDefinitionColumn(
                                        name="Task_input_value_X_Valuestring",
                                        path="$this",
                                        type="string",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTime": FlatteningLookupElement(
                    parent="Task.input.value[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(time)",
                        select=[
                            ViewDefinitionSelect(
                                column=[
                                    ViewDefinitionColumn(
                                        name="Task_input_value_X_Valuetime",
                                        path="$this",
                                        type="time",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTiming": FlatteningLookupElement(
                    parent="Task.input.value[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(Timing)",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueTiming.code",
                        "Task.input.value[x]:valueTiming.event",
                        "Task.input.value[x]:valueTiming.repeat",
                    ],
                ),
                "Task.input.value[x]:valueTiming.code": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTiming",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="code",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueTiming.code.coding",
                    ],
                ),
                "Task.input.value[x]:valueTiming.code.coding": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTiming.code",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="coding",
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetiming_code_coding_system",
                                path="system",
                                type="uri",
                            ),
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetiming_code_coding_code",
                                path="code",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTiming.event": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTiming",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="event",
                        select=[
                            ViewDefinitionSelect(
                                column=[
                                    ViewDefinitionColumn(
                                        name="Task_input_value_X_Valuetiming_event",
                                        path="$this",
                                        type="dateTime",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTiming.repeat": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTiming",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="repeat",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueTiming.repeat.bounds[x]",
                        "Task.input.value[x]:valueTiming.repeat.count",
                        "Task.input.value[x]:valueTiming.repeat.countMax",
                        "Task.input.value[x]:valueTiming.repeat.dayOfWeek",
                        "Task.input.value[x]:valueTiming.repeat.duration",
                        "Task.input.value[x]:valueTiming.repeat.durationMax",
                        "Task.input.value[x]:valueTiming.repeat.durationUnit",
                        "Task.input.value[x]:valueTiming.repeat.frequency",
                        "Task.input.value[x]:valueTiming.repeat.frequencyMax",
                        "Task.input.value[x]:valueTiming.repeat.offset",
                        "Task.input.value[x]:valueTiming.repeat.period",
                        "Task.input.value[x]:valueTiming.repeat.periodMax",
                        "Task.input.value[x]:valueTiming.repeat.periodUnit",
                        "Task.input.value[x]:valueTiming.repeat.timeOfDay",
                        "Task.input.value[x]:valueTiming.repeat.when",
                    ],
                ),
                "Task.input.value[x]:valueTiming.repeat.bounds[x]": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTiming.repeat",
                    view_definition=ViewDefinitionSnippet(
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsDuration",
                        "Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsPeriod",
                        "Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsRange",
                    ],
                ),
                "Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsDuration": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTiming.repeat.bounds[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="bounds.ofType(Duration)",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsDuration.code",
                        "Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsDuration.system",
                        "Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsDuration.value",
                    ],
                ),
                "Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsDuration.code": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsDuration",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetiming_repeat_bounds_X_Boundsduration_code",
                                path="code",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsDuration.system": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsDuration",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetiming_repeat_bounds_X_Boundsduration_system",
                                path="system",
                                type="uri",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsDuration.value": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsDuration",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetiming_repeat_bounds_X_Boundsduration_value",
                                path="value",
                                type="decimal",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsPeriod": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTiming.repeat.bounds[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="bounds.ofType(Period)",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsPeriod.end",
                        "Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsPeriod.start",
                    ],
                ),
                "Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsPeriod.end": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsPeriod",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetiming_repeat_bounds_X_Boundsperiod_end",
                                path="end",
                                type="dateTime",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsPeriod.start": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsPeriod",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetiming_repeat_bounds_X_Boundsperiod_start",
                                path="start",
                                type="dateTime",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsRange": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTiming.repeat.bounds[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="bounds.ofType(Range)",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsRange.high",
                        "Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsRange.low",
                    ],
                ),
                "Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsRange.high": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsRange",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="high",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsRange.high.code",
                        "Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsRange.high.comparator",
                        "Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsRange.high.system",
                        "Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsRange.high.unit",
                        "Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsRange.high.value",
                    ],
                ),
                "Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsRange.high.code": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsRange.high",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetiming_repeat_bounds_X_Boundsrange_high_code",
                                path="code",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsRange.high.comparator": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsRange.high",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetiming_repeat_bounds_X_Boundsrange_high_comparator",
                                path="comparator",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsRange.high.system": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsRange.high",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetiming_repeat_bounds_X_Boundsrange_high_system",
                                path="system",
                                type="uri",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsRange.high.unit": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsRange.high",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetiming_repeat_bounds_X_Boundsrange_high_unit",
                                path="unit",
                                type="string",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsRange.high.value": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsRange.high",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetiming_repeat_bounds_X_Boundsrange_high_value",
                                path="value",
                                type="decimal",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsRange.low": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsRange",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="low",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsRange.low.code",
                        "Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsRange.low.comparator",
                        "Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsRange.low.system",
                        "Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsRange.low.unit",
                        "Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsRange.low.value",
                    ],
                ),
                "Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsRange.low.code": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsRange.low",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetiming_repeat_bounds_X_Boundsrange_low_code",
                                path="code",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsRange.low.comparator": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsRange.low",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetiming_repeat_bounds_X_Boundsrange_low_comparator",
                                path="comparator",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsRange.low.system": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsRange.low",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetiming_repeat_bounds_X_Boundsrange_low_system",
                                path="system",
                                type="uri",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsRange.low.unit": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsRange.low",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetiming_repeat_bounds_X_Boundsrange_low_unit",
                                path="unit",
                                type="string",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsRange.low.value": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTiming.repeat.bounds[x]:boundsRange.low",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetiming_repeat_bounds_X_Boundsrange_low_value",
                                path="value",
                                type="decimal",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTiming.repeat.count": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTiming.repeat",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetiming_repeat_count",
                                path="count",
                                type="positiveInt",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTiming.repeat.countMax": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTiming.repeat",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetiming_repeat_countMax",
                                path="countMax",
                                type="positiveInt",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTiming.repeat.dayOfWeek": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTiming.repeat",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="dayOfWeek",
                        select=[
                            ViewDefinitionSelect(
                                column=[
                                    ViewDefinitionColumn(
                                        name="Task_input_value_X_Valuetiming_repeat_dayOfWeek",
                                        path="$this",
                                        type="code",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTiming.repeat.duration": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTiming.repeat",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetiming_repeat_duration",
                                path="duration",
                                type="decimal",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTiming.repeat.durationMax": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTiming.repeat",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetiming_repeat_durationMax",
                                path="durationMax",
                                type="decimal",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTiming.repeat.durationUnit": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTiming.repeat",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetiming_repeat_durationUnit",
                                path="durationUnit",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTiming.repeat.frequency": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTiming.repeat",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetiming_repeat_frequency",
                                path="frequency",
                                type="positiveInt",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTiming.repeat.frequencyMax": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTiming.repeat",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetiming_repeat_frequencyMax",
                                path="frequencyMax",
                                type="positiveInt",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTiming.repeat.offset": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTiming.repeat",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetiming_repeat_offset",
                                path="offset",
                                type="unsignedInt",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTiming.repeat.period": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTiming.repeat",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetiming_repeat_period",
                                path="period",
                                type="decimal",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTiming.repeat.periodMax": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTiming.repeat",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetiming_repeat_periodMax",
                                path="periodMax",
                                type="decimal",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTiming.repeat.periodUnit": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTiming.repeat",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetiming_repeat_periodUnit",
                                path="periodUnit",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTiming.repeat.timeOfDay": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTiming.repeat",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="timeOfDay",
                        select=[
                            ViewDefinitionSelect(
                                column=[
                                    ViewDefinitionColumn(
                                        name="Task_input_value_X_Valuetiming_repeat_timeOfDay",
                                        path="$this",
                                        type="time",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTiming.repeat.when": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTiming.repeat",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="when",
                        select=[
                            ViewDefinitionSelect(
                                column=[
                                    ViewDefinitionColumn(
                                        name="Task_input_value_X_Valuetiming_repeat_when",
                                        path="$this",
                                        type="code",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition": FlatteningLookupElement(
                    parent="Task.input.value[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(TriggerDefinition)",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueTriggerDefinition.data",
                        "Task.input.value[x]:valueTriggerDefinition.name",
                        "Task.input.value[x]:valueTriggerDefinition.timing[x]",
                        "Task.input.value[x]:valueTriggerDefinition.type",
                    ],
                ),
                "Task.input.value[x]:valueTriggerDefinition.data": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="data",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueTriggerDefinition.data.codeFilter",
                        "Task.input.value[x]:valueTriggerDefinition.data.dateFilter",
                        "Task.input.value[x]:valueTriggerDefinition.data.limit",
                        "Task.input.value[x]:valueTriggerDefinition.data.mustSupport",
                        "Task.input.value[x]:valueTriggerDefinition.data.profile",
                        "Task.input.value[x]:valueTriggerDefinition.data.sort",
                        "Task.input.value[x]:valueTriggerDefinition.data.subject[x]",
                        "Task.input.value[x]:valueTriggerDefinition.data.type",
                    ],
                ),
                "Task.input.value[x]:valueTriggerDefinition.data.codeFilter": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.data",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="codeFilter",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueTriggerDefinition.data.codeFilter.code",
                        "Task.input.value[x]:valueTriggerDefinition.data.codeFilter.path",
                        "Task.input.value[x]:valueTriggerDefinition.data.codeFilter.searchParam",
                        "Task.input.value[x]:valueTriggerDefinition.data.codeFilter.valueSet",
                    ],
                ),
                "Task.input.value[x]:valueTriggerDefinition.data.codeFilter.code": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.data.codeFilter",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="code",
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetriggerdefinition_data_codeFilter_code_system",
                                path="system",
                                type="uri",
                            ),
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetriggerdefinition_data_codeFilter_code_code",
                                path="code",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition.data.codeFilter.path": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.data.codeFilter",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetriggerdefinition_data_codeFilter_path",
                                path="path",
                                type="string",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition.data.codeFilter.searchParam": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.data.codeFilter",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetriggerdefinition_data_codeFilter_searchParam",
                                path="searchParam",
                                type="string",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition.data.codeFilter.valueSet": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.data.codeFilter",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetriggerdefinition_data_codeFilter_valueSet",
                                path="valueSet",
                                type="canonical",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition.data.dateFilter": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.data",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="dateFilter",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueTriggerDefinition.data.dateFilter.path",
                        "Task.input.value[x]:valueTriggerDefinition.data.dateFilter.searchParam",
                        "Task.input.value[x]:valueTriggerDefinition.data.dateFilter.value[x]",
                    ],
                ),
                "Task.input.value[x]:valueTriggerDefinition.data.dateFilter.path": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.data.dateFilter",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetriggerdefinition_data_dateFilter_path",
                                path="path",
                                type="string",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition.data.dateFilter.searchParam": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.data.dateFilter",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetriggerdefinition_data_dateFilter_searchParam",
                                path="searchParam",
                                type="string",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition.data.dateFilter.value[x]": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.data.dateFilter",
                    view_definition=ViewDefinitionSnippet(
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueTriggerDefinition.data.dateFilter.value[x]:valueDateTime",
                        "Task.input.value[x]:valueTriggerDefinition.data.dateFilter.value[x]:valueDuration",
                        "Task.input.value[x]:valueTriggerDefinition.data.dateFilter.value[x]:valuePeriod",
                    ],
                ),
                "Task.input.value[x]:valueTriggerDefinition.data.dateFilter.value[x]:valueDateTime": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.data.dateFilter.value[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(dateTime)",
                        select=[
                            ViewDefinitionSelect(
                                column=[
                                    ViewDefinitionColumn(
                                        name="Task_input_value_X_Valuetriggerdefinition_data_dateFilter_value_X_Valuedatetime",
                                        path="$this",
                                        type="dateTime",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition.data.dateFilter.value[x]:valueDuration": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.data.dateFilter.value[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(Duration)",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueTriggerDefinition.data.dateFilter.value[x]:valueDuration.code",
                        "Task.input.value[x]:valueTriggerDefinition.data.dateFilter.value[x]:valueDuration.system",
                        "Task.input.value[x]:valueTriggerDefinition.data.dateFilter.value[x]:valueDuration.value",
                    ],
                ),
                "Task.input.value[x]:valueTriggerDefinition.data.dateFilter.value[x]:valueDuration.code": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.data.dateFilter.value[x]:valueDuration",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetriggerdefinition_data_dateFilter_value_X_Valueduration_code",
                                path="code",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition.data.dateFilter.value[x]:valueDuration.system": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.data.dateFilter.value[x]:valueDuration",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetriggerdefinition_data_dateFilter_value_X_Valueduration_system",
                                path="system",
                                type="uri",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition.data.dateFilter.value[x]:valueDuration.value": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.data.dateFilter.value[x]:valueDuration",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetriggerdefinition_data_dateFilter_value_X_Valueduration_value",
                                path="value",
                                type="decimal",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition.data.dateFilter.value[x]:valuePeriod": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.data.dateFilter.value[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(Period)",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueTriggerDefinition.data.dateFilter.value[x]:valuePeriod.end",
                        "Task.input.value[x]:valueTriggerDefinition.data.dateFilter.value[x]:valuePeriod.start",
                    ],
                ),
                "Task.input.value[x]:valueTriggerDefinition.data.dateFilter.value[x]:valuePeriod.end": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.data.dateFilter.value[x]:valuePeriod",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetriggerdefinition_data_dateFilter_value_X_Valueperiod_end",
                                path="end",
                                type="dateTime",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition.data.dateFilter.value[x]:valuePeriod.start": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.data.dateFilter.value[x]:valuePeriod",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetriggerdefinition_data_dateFilter_value_X_Valueperiod_start",
                                path="start",
                                type="dateTime",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition.data.limit": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.data",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetriggerdefinition_data_limit",
                                path="limit",
                                type="positiveInt",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition.data.mustSupport": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.data",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="mustSupport",
                        select=[
                            ViewDefinitionSelect(
                                column=[
                                    ViewDefinitionColumn(
                                        name="Task_input_value_X_Valuetriggerdefinition_data_mustSupport",
                                        path="$this",
                                        type="string",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition.data.profile": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.data",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="profile",
                        select=[
                            ViewDefinitionSelect(
                                column=[
                                    ViewDefinitionColumn(
                                        name="Task_input_value_X_Valuetriggerdefinition_data_profile",
                                        path="$this",
                                        type="canonical",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition.data.sort": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.data",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="sort",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueTriggerDefinition.data.sort.direction",
                        "Task.input.value[x]:valueTriggerDefinition.data.sort.path",
                    ],
                ),
                "Task.input.value[x]:valueTriggerDefinition.data.sort.direction": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.data.sort",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetriggerdefinition_data_sort_direction",
                                path="direction",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition.data.sort.path": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.data.sort",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetriggerdefinition_data_sort_path",
                                path="path",
                                type="string",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition.data.subject[x]": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.data",
                    view_definition=ViewDefinitionSnippet(
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueTriggerDefinition.data.subject[x]:subjectCodeableConcept",
                        "Task.input.value[x]:valueTriggerDefinition.data.subject[x]:subjectReference",
                    ],
                ),
                "Task.input.value[x]:valueTriggerDefinition.data.subject[x]:subjectCodeableConcept": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.data.subject[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="subject.ofType(CodeableConcept)",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueTriggerDefinition.data.subject[x]:subjectCodeableConcept.coding",
                    ],
                ),
                "Task.input.value[x]:valueTriggerDefinition.data.subject[x]:subjectCodeableConcept.coding": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.data.subject[x]:subjectCodeableConcept",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="coding",
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetriggerdefinition_data_subject_X_Subjectcodeableconcept_coding_system",
                                path="system",
                                type="uri",
                            ),
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetriggerdefinition_data_subject_X_Subjectcodeableconcept_coding_code",
                                path="code",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition.data.subject[x]:subjectReference": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.data.subject[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="subject.ofType(Reference)",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueTriggerDefinition.data.subject[x]:subjectReference.reference",
                    ],
                ),
                "Task.input.value[x]:valueTriggerDefinition.data.subject[x]:subjectReference.reference": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.data.subject[x]:subjectReference",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetriggerdefinition_data_subject_X_Subjectreference_reference",
                                path="reference",
                                type="string",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition.data.type": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.data",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetriggerdefinition_data_type",
                                path="type",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition.name": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetriggerdefinition_name",
                                path="name",
                                type="string",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition.timing[x]": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition",
                    view_definition=ViewDefinitionSnippet(
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingDate",
                        "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingDateTime",
                        "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingReference",
                        "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming",
                    ],
                ),
                "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingDate": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.timing[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="timing.ofType(date)",
                        select=[
                            ViewDefinitionSelect(
                                column=[
                                    ViewDefinitionColumn(
                                        name="Task_input_value_X_Valuetriggerdefinition_timing_X_Timingdate",
                                        path="$this",
                                        type="date",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingDateTime": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.timing[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="timing.ofType(dateTime)",
                        select=[
                            ViewDefinitionSelect(
                                column=[
                                    ViewDefinitionColumn(
                                        name="Task_input_value_X_Valuetriggerdefinition_timing_X_Timingdatetime",
                                        path="$this",
                                        type="dateTime",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingReference": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.timing[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="timing.ofType(Reference)",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingReference.reference",
                    ],
                ),
                "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingReference.reference": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.timing[x]:timingReference",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetriggerdefinition_timing_X_Timingreference_reference",
                                path="reference",
                                type="string",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.timing[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="timing.ofType(Timing)",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.code",
                        "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.event",
                        "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat",
                    ],
                ),
                "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.code": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="code",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.code.coding",
                    ],
                ),
                "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.code.coding": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.code",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="coding",
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetriggerdefinition_timing_X_Timingtiming_code_coding_system",
                                path="system",
                                type="uri",
                            ),
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetriggerdefinition_timing_X_Timingtiming_code_coding_code",
                                path="code",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.event": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="event",
                        select=[
                            ViewDefinitionSelect(
                                column=[
                                    ViewDefinitionColumn(
                                        name="Task_input_value_X_Valuetriggerdefinition_timing_X_Timingtiming_event",
                                        path="$this",
                                        type="dateTime",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="repeat",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]",
                        "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.count",
                        "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.countMax",
                        "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.dayOfWeek",
                        "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.duration",
                        "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.durationMax",
                        "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.durationUnit",
                        "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.frequency",
                        "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.frequencyMax",
                        "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.offset",
                        "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.period",
                        "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.periodMax",
                        "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.periodUnit",
                        "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.timeOfDay",
                        "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.when",
                    ],
                ),
                "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat",
                    view_definition=ViewDefinitionSnippet(
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsDuration",
                        "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsPeriod",
                        "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsRange",
                    ],
                ),
                "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsDuration": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="bounds.ofType(Duration)",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsDuration.code",
                        "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsDuration.system",
                        "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsDuration.value",
                    ],
                ),
                "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsDuration.code": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsDuration",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetriggerdefinition_timing_X_Timingtiming_repeat_bounds_X_Boundsduration_code",
                                path="code",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsDuration.system": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsDuration",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetriggerdefinition_timing_X_Timingtiming_repeat_bounds_X_Boundsduration_system",
                                path="system",
                                type="uri",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsDuration.value": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsDuration",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetriggerdefinition_timing_X_Timingtiming_repeat_bounds_X_Boundsduration_value",
                                path="value",
                                type="decimal",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsPeriod": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="bounds.ofType(Period)",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsPeriod.end",
                        "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsPeriod.start",
                    ],
                ),
                "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsPeriod.end": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsPeriod",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetriggerdefinition_timing_X_Timingtiming_repeat_bounds_X_Boundsperiod_end",
                                path="end",
                                type="dateTime",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsPeriod.start": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsPeriod",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetriggerdefinition_timing_X_Timingtiming_repeat_bounds_X_Boundsperiod_start",
                                path="start",
                                type="dateTime",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsRange": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="bounds.ofType(Range)",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsRange.high",
                        "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsRange.low",
                    ],
                ),
                "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsRange.high": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsRange",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="high",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsRange.high.code",
                        "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsRange.high.comparator",
                        "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsRange.high.system",
                        "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsRange.high.unit",
                        "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsRange.high.value",
                    ],
                ),
                "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsRange.high.code": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsRange.high",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetriggerdefinition_timing_X_Timingtiming_repeat_bounds_X_Boundsrange_high_code",
                                path="code",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsRange.high.comparator": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsRange.high",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetriggerdefinition_timing_X_Timingtiming_repeat_bounds_X_Boundsrange_high_comparator",
                                path="comparator",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsRange.high.system": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsRange.high",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetriggerdefinition_timing_X_Timingtiming_repeat_bounds_X_Boundsrange_high_system",
                                path="system",
                                type="uri",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsRange.high.unit": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsRange.high",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetriggerdefinition_timing_X_Timingtiming_repeat_bounds_X_Boundsrange_high_unit",
                                path="unit",
                                type="string",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsRange.high.value": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsRange.high",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetriggerdefinition_timing_X_Timingtiming_repeat_bounds_X_Boundsrange_high_value",
                                path="value",
                                type="decimal",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsRange.low": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsRange",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="low",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsRange.low.code",
                        "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsRange.low.comparator",
                        "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsRange.low.system",
                        "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsRange.low.unit",
                        "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsRange.low.value",
                    ],
                ),
                "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsRange.low.code": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsRange.low",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetriggerdefinition_timing_X_Timingtiming_repeat_bounds_X_Boundsrange_low_code",
                                path="code",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsRange.low.comparator": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsRange.low",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetriggerdefinition_timing_X_Timingtiming_repeat_bounds_X_Boundsrange_low_comparator",
                                path="comparator",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsRange.low.system": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsRange.low",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetriggerdefinition_timing_X_Timingtiming_repeat_bounds_X_Boundsrange_low_system",
                                path="system",
                                type="uri",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsRange.low.unit": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsRange.low",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetriggerdefinition_timing_X_Timingtiming_repeat_bounds_X_Boundsrange_low_unit",
                                path="unit",
                                type="string",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsRange.low.value": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.bounds[x]:boundsRange.low",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetriggerdefinition_timing_X_Timingtiming_repeat_bounds_X_Boundsrange_low_value",
                                path="value",
                                type="decimal",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.count": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetriggerdefinition_timing_X_Timingtiming_repeat_count",
                                path="count",
                                type="positiveInt",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.countMax": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetriggerdefinition_timing_X_Timingtiming_repeat_countMax",
                                path="countMax",
                                type="positiveInt",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.dayOfWeek": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="dayOfWeek",
                        select=[
                            ViewDefinitionSelect(
                                column=[
                                    ViewDefinitionColumn(
                                        name="Task_input_value_X_Valuetriggerdefinition_timing_X_Timingtiming_repeat_dayOfWeek",
                                        path="$this",
                                        type="code",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.duration": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetriggerdefinition_timing_X_Timingtiming_repeat_duration",
                                path="duration",
                                type="decimal",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.durationMax": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetriggerdefinition_timing_X_Timingtiming_repeat_durationMax",
                                path="durationMax",
                                type="decimal",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.durationUnit": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetriggerdefinition_timing_X_Timingtiming_repeat_durationUnit",
                                path="durationUnit",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.frequency": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetriggerdefinition_timing_X_Timingtiming_repeat_frequency",
                                path="frequency",
                                type="positiveInt",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.frequencyMax": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetriggerdefinition_timing_X_Timingtiming_repeat_frequencyMax",
                                path="frequencyMax",
                                type="positiveInt",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.offset": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetriggerdefinition_timing_X_Timingtiming_repeat_offset",
                                path="offset",
                                type="unsignedInt",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.period": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetriggerdefinition_timing_X_Timingtiming_repeat_period",
                                path="period",
                                type="decimal",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.periodMax": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetriggerdefinition_timing_X_Timingtiming_repeat_periodMax",
                                path="periodMax",
                                type="decimal",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.periodUnit": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetriggerdefinition_timing_X_Timingtiming_repeat_periodUnit",
                                path="periodUnit",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.timeOfDay": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="timeOfDay",
                        select=[
                            ViewDefinitionSelect(
                                column=[
                                    ViewDefinitionColumn(
                                        name="Task_input_value_X_Valuetriggerdefinition_timing_X_Timingtiming_repeat_timeOfDay",
                                        path="$this",
                                        type="time",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat.when": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition.timing[x]:timingTiming.repeat",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="when",
                        select=[
                            ViewDefinitionSelect(
                                column=[
                                    ViewDefinitionColumn(
                                        name="Task_input_value_X_Valuetriggerdefinition_timing_X_Timingtiming_repeat_when",
                                        path="$this",
                                        type="code",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueTriggerDefinition.type": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueTriggerDefinition",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valuetriggerdefinition_type",
                                path="type",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueUnsignedInt": FlatteningLookupElement(
                    parent="Task.input.value[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(unsignedInt)",
                        select=[
                            ViewDefinitionSelect(
                                column=[
                                    ViewDefinitionColumn(
                                        name="Task_input_value_X_Valueunsignedint",
                                        path="$this",
                                        type="unsignedInt",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueUri": FlatteningLookupElement(
                    parent="Task.input.value[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(uri)",
                        select=[
                            ViewDefinitionSelect(
                                column=[
                                    ViewDefinitionColumn(
                                        name="Task_input_value_X_Valueuri",
                                        path="$this",
                                        type="uri",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueUrl": FlatteningLookupElement(
                    parent="Task.input.value[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(url)",
                        select=[
                            ViewDefinitionSelect(
                                column=[
                                    ViewDefinitionColumn(
                                        name="Task_input_value_X_Valueurl",
                                        path="$this",
                                        type="url",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueUsageContext": FlatteningLookupElement(
                    parent="Task.input.value[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(UsageContext)",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueUsageContext.code",
                        "Task.input.value[x]:valueUsageContext.value[x]",
                    ],
                ),
                "Task.input.value[x]:valueUsageContext.code": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueUsageContext",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="code",
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueusagecontext_code_system",
                                path="system",
                                type="uri",
                            ),
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueusagecontext_code_code",
                                path="code",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueUsageContext.value[x]": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueUsageContext",
                    view_definition=ViewDefinitionSnippet(
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueUsageContext.value[x]:valueCodeableConcept",
                        "Task.input.value[x]:valueUsageContext.value[x]:valueQuantity",
                        "Task.input.value[x]:valueUsageContext.value[x]:valueRange",
                        "Task.input.value[x]:valueUsageContext.value[x]:valueReference",
                    ],
                ),
                "Task.input.value[x]:valueUsageContext.value[x]:valueCodeableConcept": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueUsageContext.value[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(CodeableConcept)",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueUsageContext.value[x]:valueCodeableConcept.coding",
                    ],
                ),
                "Task.input.value[x]:valueUsageContext.value[x]:valueCodeableConcept.coding": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueUsageContext.value[x]:valueCodeableConcept",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="coding",
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueusagecontext_value_X_Valuecodeableconcept_coding_system",
                                path="system",
                                type="uri",
                            ),
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueusagecontext_value_X_Valuecodeableconcept_coding_code",
                                path="code",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueUsageContext.value[x]:valueQuantity": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueUsageContext.value[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(Quantity)",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueUsageContext.value[x]:valueQuantity.code",
                        "Task.input.value[x]:valueUsageContext.value[x]:valueQuantity.comparator",
                        "Task.input.value[x]:valueUsageContext.value[x]:valueQuantity.system",
                        "Task.input.value[x]:valueUsageContext.value[x]:valueQuantity.unit",
                        "Task.input.value[x]:valueUsageContext.value[x]:valueQuantity.value",
                    ],
                ),
                "Task.input.value[x]:valueUsageContext.value[x]:valueQuantity.code": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueUsageContext.value[x]:valueQuantity",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueusagecontext_value_X_Valuequantity_code",
                                path="code",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueUsageContext.value[x]:valueQuantity.comparator": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueUsageContext.value[x]:valueQuantity",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueusagecontext_value_X_Valuequantity_comparator",
                                path="comparator",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueUsageContext.value[x]:valueQuantity.system": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueUsageContext.value[x]:valueQuantity",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueusagecontext_value_X_Valuequantity_system",
                                path="system",
                                type="uri",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueUsageContext.value[x]:valueQuantity.unit": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueUsageContext.value[x]:valueQuantity",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueusagecontext_value_X_Valuequantity_unit",
                                path="unit",
                                type="string",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueUsageContext.value[x]:valueQuantity.value": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueUsageContext.value[x]:valueQuantity",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueusagecontext_value_X_Valuequantity_value",
                                path="value",
                                type="decimal",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueUsageContext.value[x]:valueRange": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueUsageContext.value[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(Range)",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueUsageContext.value[x]:valueRange.high",
                        "Task.input.value[x]:valueUsageContext.value[x]:valueRange.low",
                    ],
                ),
                "Task.input.value[x]:valueUsageContext.value[x]:valueRange.high": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueUsageContext.value[x]:valueRange",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="high",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueUsageContext.value[x]:valueRange.high.code",
                        "Task.input.value[x]:valueUsageContext.value[x]:valueRange.high.comparator",
                        "Task.input.value[x]:valueUsageContext.value[x]:valueRange.high.system",
                        "Task.input.value[x]:valueUsageContext.value[x]:valueRange.high.unit",
                        "Task.input.value[x]:valueUsageContext.value[x]:valueRange.high.value",
                    ],
                ),
                "Task.input.value[x]:valueUsageContext.value[x]:valueRange.high.code": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueUsageContext.value[x]:valueRange.high",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueusagecontext_value_X_Valuerange_high_code",
                                path="code",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueUsageContext.value[x]:valueRange.high.comparator": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueUsageContext.value[x]:valueRange.high",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueusagecontext_value_X_Valuerange_high_comparator",
                                path="comparator",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueUsageContext.value[x]:valueRange.high.system": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueUsageContext.value[x]:valueRange.high",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueusagecontext_value_X_Valuerange_high_system",
                                path="system",
                                type="uri",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueUsageContext.value[x]:valueRange.high.unit": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueUsageContext.value[x]:valueRange.high",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueusagecontext_value_X_Valuerange_high_unit",
                                path="unit",
                                type="string",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueUsageContext.value[x]:valueRange.high.value": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueUsageContext.value[x]:valueRange.high",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueusagecontext_value_X_Valuerange_high_value",
                                path="value",
                                type="decimal",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueUsageContext.value[x]:valueRange.low": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueUsageContext.value[x]:valueRange",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="low",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueUsageContext.value[x]:valueRange.low.code",
                        "Task.input.value[x]:valueUsageContext.value[x]:valueRange.low.comparator",
                        "Task.input.value[x]:valueUsageContext.value[x]:valueRange.low.system",
                        "Task.input.value[x]:valueUsageContext.value[x]:valueRange.low.unit",
                        "Task.input.value[x]:valueUsageContext.value[x]:valueRange.low.value",
                    ],
                ),
                "Task.input.value[x]:valueUsageContext.value[x]:valueRange.low.code": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueUsageContext.value[x]:valueRange.low",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueusagecontext_value_X_Valuerange_low_code",
                                path="code",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueUsageContext.value[x]:valueRange.low.comparator": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueUsageContext.value[x]:valueRange.low",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueusagecontext_value_X_Valuerange_low_comparator",
                                path="comparator",
                                type="code",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueUsageContext.value[x]:valueRange.low.system": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueUsageContext.value[x]:valueRange.low",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueusagecontext_value_X_Valuerange_low_system",
                                path="system",
                                type="uri",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueUsageContext.value[x]:valueRange.low.unit": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueUsageContext.value[x]:valueRange.low",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueusagecontext_value_X_Valuerange_low_unit",
                                path="unit",
                                type="string",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueUsageContext.value[x]:valueRange.low.value": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueUsageContext.value[x]:valueRange.low",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueusagecontext_value_X_Valuerange_low_value",
                                path="value",
                                type="decimal",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueUsageContext.value[x]:valueReference": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueUsageContext.value[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(Reference)",
                        select=[],
                    ),
                    children=[
                        "Task.input.value[x]:valueUsageContext.value[x]:valueReference.reference",
                    ],
                ),
                "Task.input.value[x]:valueUsageContext.value[x]:valueReference.reference": FlatteningLookupElement(
                    parent="Task.input.value[x]:valueUsageContext.value[x]:valueReference",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Task_input_value_X_Valueusagecontext_value_X_Valuereference_reference",
                                path="reference",
                                type="string",
                            ),
                        ],
                    ),
                ),
                "Task.input.value[x]:valueUuid": FlatteningLookupElement(
                    parent="Task.input.value[x]",
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(uuid)",
                        select=[
                            ViewDefinitionSelect(
                                column=[
                                    ViewDefinitionColumn(
                                        name="Task_input_value_X_Valueuuid",
                                        path="$this",
                                        type="uuid",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
            },
        ),
        (
            "https://www.medizininformatik-initiative.de/fhir/core/modul-labor/StructureDefinition/ObservationLab",
            "Observation.effective[x]",
            {
                "Observation.effective[x]": FlatteningLookupElement(
                    viewDefinition=ViewDefinitionSnippet(select=[]),
                    children=["Observation.effective[x]:effectiveDateTime"],
                ),
                "Observation.effective[x].extension": FlatteningLookupElement(
                    parent="Observation.effective[x]",
                    viewDefinition=ViewDefinitionSnippet(select=[]),
                    children=[
                        "Observation.effective[x].extension:QuelleKlinischesBezugsdatum"
                    ],
                ),
                "Observation.effective[x].extension:QuelleKlinischesBezugsdatum": FlatteningLookupElement(
                    parent="Observation.effective[x].extension",
                    viewDefinition=ViewDefinitionSnippet(
                        forEachOrNull="extension.where(url = 'https://www.medizininformatik-initiative.de/fhir/core/modul-labor/StructureDefinition/QuelleKlinischesBezugsdatum')",
                        select=[],
                    ),
                    children=[
                        "Observation.effective[x].extension:QuelleKlinischesBezugsdatum.value[x]"
                    ],
                ),
                "Observation.effective[x].extension:QuelleKlinischesBezugsdatum.value[x]": FlatteningLookupElement(
                    parent="Observation.effective[x].extension",
                    viewDefinition=ViewDefinitionSnippet(select=[]),
                    children=[
                        "Observation.effective[x].extension:QuelleKlinischesBezugsdatum.value[x]:valueCoding"
                    ],
                ),
                "Observation.effective[x].extension:QuelleKlinischesBezugsdatum.value[x]:valueCoding": FlatteningLookupElement(
                    parent="Observation.effective[x].extension",
                    viewDefinition=ViewDefinitionSnippet(
                        forEachOrNull="value.ofType(Coding)",
                        select=[
                            ViewDefinitionSelect(
                                column=[
                                    ViewDefinitionColumn(
                                        name="Observation_effective_X__extensionQuelleklinischesbezugsdatum_value_X_Valuecoding_system",
                                        path="system",
                                        type="uri",
                                    ),
                                    ViewDefinitionColumn(
                                        name="Observation_effective_X__extensionQuelleklinischesbezugsdatum_value_X_Valuecoding_code",
                                        path="code",
                                        type="code",
                                    ),
                                ]
                            )
                        ],
                    ),
                ),
                "Observation.effective[x]:effectiveDateTime": FlatteningLookupElement(
                    parent="Observation.effective[x]",
                    viewDefinition=ViewDefinitionSnippet(
                        forEachOrNull="effective.ofType(dateTime)",
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
            },
        ),
    ],
    ids=[
        "Polymorphic time: Procedure.performed[x]",
        "Polymorphic time: Observation.effective[x]",
        "Polymorphic quantity: Observation.value[x]",
        "Polymorphic with all types: molgen empfohlene-folgemassnahme",
        "Polymorphic with sliced extension element",
    ],
    indirect=["profile"],
)
def test_polymorphic(
    profile: StructureDefinitionSnapshot,
    elem_id: str,
    expected: Dict[str, FlatteningLookupElement],
    flattening_lookup_generator: FlatteningLookupGenerator,
):
    res = flattening_post_process(
        flattening_lookup_generator._flatten_element(elem_id, profile)
    )
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
                                type="uri",
                            ),
                            ViewDefinitionColumn(
                                name="Observation_code_coding_code",
                                path="code",
                                type="code",
                            ),
                            # no more elements to test config rules too
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
    flattening_lookup_generator: FlatteningLookupGenerator,
):
    res = flattening_post_process(
        flattening_lookup_generator._flatten_element(elem_id, profile, client=client)
    )
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
                                        type="uri",
                                    ),
                                    ViewDefinitionColumn(
                                        name="Medication_ingredient_extensionWirkstofftyp_value_X_Valuecoding_code",
                                        path="code",
                                        type="code",
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
                        "Medication.ingredient.strength.numerator.unit",
                        "Medication.ingredient.strength.numerator.comparator",
                    ],
                ),
                "Medication.ingredient.strength.numerator.value": FlatteningLookupElement(
                    parent="Medication.ingredient.strength.numerator",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Medication_ingredient_strength_numerator_value",
                                path="value",
                                type="decimal",
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
                "Medication.ingredient.strength.numerator.unit": FlatteningLookupElement(
                    parent="Medication.ingredient.strength.numerator",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Medication_ingredient_strength_numerator_unit",
                                path="unit",
                                type="string",
                            )
                        ]
                    ),
                ),
                "Medication.ingredient.strength.numerator.comparator": FlatteningLookupElement(
                    parent="Medication.ingredient.strength.numerator",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Medication_ingredient_strength_numerator_comparator",
                                path="comparator",
                                type="code",
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
                        "Medication.ingredient.strength.denominator.unit",
                        "Medication.ingredient.strength.denominator.comparator",
                    ],
                ),
                "Medication.ingredient.strength.denominator.value": FlatteningLookupElement(
                    parent="Medication.ingredient.strength.denominator",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Medication_ingredient_strength_denominator_value",
                                path="value",
                                type="decimal",
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
                "Medication.ingredient.strength.denominator.unit": FlatteningLookupElement(
                    parent="Medication.ingredient.strength.denominator",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Medication_ingredient_strength_denominator_unit",
                                path="unit",
                                type="string",
                            )
                        ]
                    ),
                ),
                "Medication.ingredient.strength.denominator.comparator": FlatteningLookupElement(
                    parent="Medication.ingredient.strength.denominator",
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Medication_ingredient_strength_denominator_comparator",
                                path="comparator",
                                type="code",
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
    flattening_lookup_generator: FlatteningLookupGenerator,
):
    res = flattening_post_process(
        flattening_lookup_generator._flatten_element(elem_id, profile)
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
                                type="uri",
                            ),
                            ViewDefinitionColumn(
                                name="Patient_identifierVersichertennummer_pkv_type_coding_code",
                                path="code",
                                type="code",
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
                                type="uri",
                            ),
                            ViewDefinitionColumn(
                                name="Patient_identifierPatientennummer_type_coding_code",
                                path="code",
                                type="code",
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
                                type="uri",
                            ),
                            ViewDefinitionColumn(
                                name="Patient_identifierVersichertenid_type_coding_code",
                                path="code",
                                type="code",
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
                                type="uri",
                            ),
                            ViewDefinitionColumn(
                                name="Patient_identifierVersichertenidgkv_type_coding_code",
                                path="code",
                                type="code",
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
    flattening_lookup_generator: FlatteningLookupGenerator,
):
    res = flattening_post_process(
        flattening_lookup_generator._flatten_element(
            elem_id,
            profile,
            type=elem_type,
        )
    )
    res = sorted(res.items(), key=lambda x: (len(x[0]), x[0]))
    expected = sorted(
        flattening_post_process(expected).items(), key=lambda x: (len(x[0]), x[0])
    )

    assert res == expected


def test_profile_with_random_slicename_for_type(flattening_lookup_generator):
    profile_path = Path(__file__).parent / "profile_with_random_sliceName_for_type.json"

    with profile_path.open("r", encoding="utf-8") as f:
        profile_dict = json.load(f)

    expected_lookup_elements = {
        "Observation.value[x]": FlatteningLookupElement(
            viewDefinition=ViewDefinitionSnippet(
                select=[],
            ),
            children=[
                "Observation.value[x]:totallyRandomSliceName",
                "Observation.value[x]:valueQuantity",
            ],
        ),
        "Observation.value[x]:totallyRandomSliceName": FlatteningLookupElement(
            parent="Observation.value[x]",
            viewDefinition=ViewDefinitionSnippet(
                forEachOrNull="value.ofType(Quantity)",
                select=[],
            ),
            children=[
                "Observation.value[x]:totallyRandomSliceName.code",
                "Observation.value[x]:totallyRandomSliceName.comparator",
                "Observation.value[x]:totallyRandomSliceName.system",
                "Observation.value[x]:totallyRandomSliceName.unit",
                "Observation.value[x]:totallyRandomSliceName.value",
            ],
        ),
        "Observation.value[x]:totallyRandomSliceName.code": FlatteningLookupElement(
            parent="Observation.value[x]:totallyRandomSliceName",
            viewDefinition=ViewDefinitionSnippet(
                column=[
                    ViewDefinitionColumn(
                        name="Observation_value_X_Totallyrandomslicename_code",
                        path="code",
                        type="code",
                    )
                ],
            ),
        ),
        "Observation.value[x]:totallyRandomSliceName.comparator": FlatteningLookupElement(
            parent="Observation.value[x]:totallyRandomSliceName",
            viewDefinition=ViewDefinitionSnippet(
                column=[
                    ViewDefinitionColumn(
                        name="Observation_value_X_Totallyrandomslicename_comparator",
                        path="comparator",
                        type="code",
                    )
                ],
            ),
        ),
        "Observation.value[x]:totallyRandomSliceName.system": FlatteningLookupElement(
            parent="Observation.value[x]:totallyRandomSliceName",
            viewDefinition=ViewDefinitionSnippet(
                column=[
                    ViewDefinitionColumn(
                        name="Observation_value_X_Totallyrandomslicename_system",
                        path="system",
                        type="uri",
                    )
                ],
            ),
        ),
        "Observation.value[x]:totallyRandomSliceName.unit": FlatteningLookupElement(
            parent="Observation.value[x]:totallyRandomSliceName",
            viewDefinition=ViewDefinitionSnippet(
                column=[
                    ViewDefinitionColumn(
                        name="Observation_value_X_Totallyrandomslicename_unit",
                        path="unit",
                        type="string",
                    )
                ],
            ),
        ),
        "Observation.value[x]:totallyRandomSliceName.value": FlatteningLookupElement(
            parent="Observation.value[x]:totallyRandomSliceName",
            viewDefinition=ViewDefinitionSnippet(
                column=[
                    ViewDefinitionColumn(
                        name="Observation_value_X_Totallyrandomslicename_value",
                        path="value",
                        type="decimal",
                    )
                ],
            ),
        ),
        "Observation.value[x]:valueQuantity": FlatteningLookupElement(
            parent="Observation.value[x]",
            viewDefinition=ViewDefinitionSnippet(
                forEachOrNull="value.ofType(Quantity)",
                select=[],
            ),
            children=[
                "Observation.value[x]:valueQuantity.code",
                "Observation.value[x]:valueQuantity.comparator",
                "Observation.value[x]:valueQuantity.system",
                "Observation.value[x]:valueQuantity.unit",
                "Observation.value[x]:valueQuantity.value",
            ],
        ),
        "Observation.value[x]:valueQuantity.code": FlatteningLookupElement(
            parent="Observation.value[x]:valueQuantity",
            viewDefinition=ViewDefinitionSnippet(
                column=[
                    ViewDefinitionColumn(
                        name="Observation_value_X_Valuequantity_code",
                        path="code",
                        type="code",
                    )
                ],
            ),
        ),
        "Observation.value[x]:valueQuantity.comparator": FlatteningLookupElement(
            parent="Observation.value[x]:valueQuantity",
            viewDefinition=ViewDefinitionSnippet(
                column=[
                    ViewDefinitionColumn(
                        name="Observation_value_X_Valuequantity_comparator",
                        path="comparator",
                        type="code",
                    )
                ],
            ),
        ),
        "Observation.value[x]:valueQuantity.system": FlatteningLookupElement(
            parent="Observation.value[x]:valueQuantity",
            viewDefinition=ViewDefinitionSnippet(
                column=[
                    ViewDefinitionColumn(
                        name="Observation_value_X_Valuequantity_system",
                        path="system",
                        type="uri",
                    )
                ],
            ),
        ),
        "Observation.value[x]:valueQuantity.unit": FlatteningLookupElement(
            parent="Observation.value[x]:valueQuantity",
            viewDefinition=ViewDefinitionSnippet(
                column=[
                    ViewDefinitionColumn(
                        name="Observation_value_X_Valuequantity_unit",
                        path="unit",
                        type="string",
                    )
                ],
            ),
        ),
        "Observation.value[x]:valueQuantity.value": FlatteningLookupElement(
            parent="Observation.value[x]:valueQuantity",
            viewDefinition=ViewDefinitionSnippet(
                column=[
                    ViewDefinitionColumn(
                        name="Observation_value_X_Valuequantity_value",
                        path="value",
                        type="decimal",
                    )
                ],
            ),
        ),
    }

    profile_broken = StructureDefinitionSnapshot.model_validate(profile_dict)

    lookup = sorted(
        flattening_post_process(
            flattening_lookup_generator._flatten_element(
                element_id="Observation.value[x]", profile=profile_broken
            )
        ).items(),
        key=lambda x: (len(x[0]), x[0]),
    )

    expected = sorted(
        flattening_post_process(expected_lookup_elements).items(),
        key=lambda x: (len(x[0]), x[0]),
    )

    assert lookup == expected
