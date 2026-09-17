from typing import Mapping, Optional

import pytest
from fhir.resources.R4B.codeableconcept import CodeableConcept
from fhir.resources.R4B.coding import Coding
from fhir.resources.R4B.elementdefinition import (
    ElementDefinition,
    ElementDefinitionBinding,
    ElementDefinitionSlicing,
    ElementDefinitionSlicingDiscriminator,
    ElementDefinitionType,
)
from fhir.resources.R4B.identifier import Identifier

from flattening.core.flattening import (
    FlatteningLookupElement,
    FlatteningLookupGenerator,
    ViewDefinitionColumn,
    ViewDefinitionSelect,
    ViewDefinitionSnippet,
    flattening_get_parent,
    flattening_post_process,
    is_leafless_branch_root,
    prune_leafless_branches,
)
from flattening.model.FlatteningLookupModels import FlatteningLookup
from tests.unit.flattening.builders import build_profile

@pytest.mark.parametrize(
    argnames="element_id, lookup, expected",
    argvalues=[
        pytest.param(
            "Observation.extension:foo",
            {},
            {},
            id="element_id missing from lookup -> dropped",
        ),
        pytest.param(
            "Condition.code.coding:icd10-gm.code",
            {
                "Condition.code.coding:icd10-gm.code": FlatteningLookupElement(
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
            "unchanged",
            id="primitive leaf with top-level column, no children -> kept",
        ),
        pytest.param(
            # A LookupElement which has no children or a column should not get dropped if it has a select element
            "Account.coverage.extension:Abrechnungsart.value[x]:valueCoding",
            {
                "Account.coverage.extension:Abrechnungsart.value[x]:valueCoding": FlatteningLookupElement(
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(Coding)",
                        select=[
                            ViewDefinitionSelect(
                                column=[
                                    ViewDefinitionColumn(
                                        name="Account_coverage_extensionAbrechnungsart_value_X_Valuecoding_system",
                                        path="system",
                                        type="uri",
                                    )
                                ]
                            )
                        ],
                    ),
                ),
            },
            "unchanged",
            id="polymorphic leaf with non-empty select, no children -> kept",
        ),
        pytest.param(
            "Observation.effective[x].extension:QuelleKlinischesBezugsdatum",
            {
                "Observation.effective[x].extension:QuelleKlinischesBezugsdatum": FlatteningLookupElement(
                    view_definition=ViewDefinitionSnippet(select=[]),
                    children=[
                        "Observation.effective[x].extension:QuelleKlinischesBezugsdatum.value[x]"
                    ],
                ),
                "Observation.effective[x].extension:QuelleKlinischesBezugsdatum.value[x]": FlatteningLookupElement(
                    view_definition=ViewDefinitionSnippet(select=[]),
                    children=[
                        "Observation.effective[x].extension:QuelleKlinischesBezugsdatum.value[x]:valueCoding"
                    ],
                ),
                "Observation.effective[x].extension:QuelleKlinischesBezugsdatum.value[x]:valueCoding": FlatteningLookupElement(
                    view_definition=ViewDefinitionSnippet(
                        select=[ViewDefinitionSelect(column=[])]
                    ),
                ),
            },
            "unchanged",
            id="empty select + children, child resolves -> kept",
        ),
        pytest.param(
            # This is the original issue: an extension's value[x] has no defined/assumed types
            # (e.g. `DiagnosticReport.extension:related-report.value[x]` for
            # `workflow-relatedArtifact`), so it ends up with an empty `select` and either no
            # children or children that don't resolve to anything in the lookup. Keeping it
            # produces a `ViewDefinition.select` entry that is never filled.
            "DiagnosticReport.extension:related-report.value[x]",
            {
                "DiagnosticReport.extension:related-report.value[x]": FlatteningLookupElement(
                    view_definition=ViewDefinitionSnippet(select=[]),
                ),
            },
            {},
            id="empty select, no children -> dropped (the original #523 bug)",
        ),
        pytest.param(
            "DiagnosticReport.extension:related-report.value[x]",
            {
                "DiagnosticReport.extension:related-report.value[x]": FlatteningLookupElement(
                    view_definition=ViewDefinitionSnippet(select=[]),
                    children=[
                        "DiagnosticReport.extension:related-report.value[x]:valueCoding"
                    ],
                ),
                # the referenced child never made it into the lookup (e.g. it was excluded or
                # dropped further down the chain)
            },
            {},
            id="empty select, children present but none resolve -> dropped",
        ),
    ],
)
def test_filter_for_empty_select(element_id, lookup, expected):
    result = prune_leafless_branches(element_id, lookup)
    if expected == "unchanged":
        assert result == lookup
    else:
        assert result == expected


@pytest.mark.parametrize(
    argnames="flat_element_id, lookup, expected",
    argvalues=[
        pytest.param(
            "Observation.code.coding:sct",
            {
                "Observation.code": FlatteningLookupElement(
                    view_definition=ViewDefinitionSnippet(select=[]),
                    children=["Observation.code.coding:sct"],
                ),
                "Observation.code.coding:sct": FlatteningLookupElement(
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
            },
            "Observation.code",
            id="element listed in a parent's children -> parent returned",
        ),
        pytest.param(
            "Observation.code",
            {
                "Observation.code": FlatteningLookupElement(
                    view_definition=ViewDefinitionSnippet(select=[]),
                ),
            },
            None,
            id="root element referenced by nobody -> None",
        ),
        pytest.param(
            "Observation.code",
            {},
            None,
            id="empty lookup -> None",
        ),
        pytest.param(
            "Observation.code.coding:sct",
            {
                "Observation.code": FlatteningLookupElement(
                    view_definition=ViewDefinitionSnippet(select=[]),
                    children=["Observation.code.coding:loinc"],
                ),
                "Observation.other": FlatteningLookupElement(
                    view_definition=ViewDefinitionSnippet(select=[]),
                    children=["Observation.other.child"],
                ),
            },
            None,
            id="element present as a key but not listed as anyone's child -> None",
        ),
    ],
)
def test_flattening_get_parent(flat_element_id, lookup, expected):
    assert flattening_get_parent(flat_element_id, lookup) == expected


@pytest.mark.parametrize(
    argnames="element_id, lookup, expected",
    argvalues=[
        pytest.param(
            "Observation.code",
            {},
            False,
            id="element missing from lookup -> False",
        ),
        pytest.param(
            "Observation.code",
            {
                "Observation.code": FlatteningLookupElement(
                    view_definition=ViewDefinitionSnippet(select=[]),
                    children=["Observation.code.coding"],
                ),
                "Observation.code.coding": FlatteningLookupElement(
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Observation_code_coding_code",
                                path="code",
                                type="code",
                            )
                        ]
                    ),
                ),
            },
            False,
            id="has at least one resolvable child -> not leafless",
        ),
        pytest.param(
            "Observation.code",
            {
                "Observation.code": FlatteningLookupElement(
                    view_definition=ViewDefinitionSnippet(select=[]),
                    children=["Observation.code.coding"],
                ),
                # "Observation.code.coding" was already removed / never added
            },
            True,
            id="children listed but none resolve in the lookup -> leafless",
        ),
        pytest.param(
            "Observation.code",
            {
                "Observation.code": FlatteningLookupElement(
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Observation_code", path="code", type="code"
                            )
                        ]
                    ),
                ),
            },
            False,
            id="no children but has its own column -> not leafless",
        ),
        pytest.param(
            # Same regression fixture as the "polymorphic leaf with non-empty select" case
            # in test_filter_for_empty_select: columns wrapped inside `select` still count
            # as valid content.
            "Account.coverage.extension:Abrechnungsart.value[x]:valueCoding",
            {
                "Account.coverage.extension:Abrechnungsart.value[x]:valueCoding": FlatteningLookupElement(
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="value.ofType(Coding)",
                        select=[
                            ViewDefinitionSelect(
                                column=[
                                    ViewDefinitionColumn(
                                        name="Account_coverage_extensionAbrechnungsart_value_X_Valuecoding_system",
                                        path="system",
                                        type="uri",
                                    )
                                ]
                            )
                        ],
                    ),
                ),
            },
            False,
            id="no children, no top-level column, but non-empty select -> not leafless",
        ),
        pytest.param(
            "Observation.extension:foo",
            {
                "Observation.extension:foo": FlatteningLookupElement(
                    view_definition=ViewDefinitionSnippet(select=[]),
                ),
            },
            True,
            id="no children, no column, empty select -> leafless",
        ),
        pytest.param(
            "Observation.extension:foo",
            {
                "Observation.extension:foo": FlatteningLookupElement(
                    view_definition=ViewDefinitionSnippet(),
                ),
            },
            True,
            id="no children, no column, select unset -> leafless",
        ),
    ],
)
def test_is_leafless_branch_root(element_id, lookup, expected):
    assert is_leafless_branch_root(element_id, lookup) is expected


@pytest.mark.parametrize(
    argnames="lookup, expected",
    argvalues=[
        pytest.param(
            {
                "Observation.value[x]": FlatteningLookupElement(
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Observation_value_X_", path="value", type="string"
                            )
                        ]
                    ),
                ),
            },
            {
                "Observation.value[x]": FlatteningLookupElement(
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Observation_value_X_", path="value", type="string"
                            )
                        ]
                    ),
                    children=None,
                ),
            },
            id="single leaf with a column -> kept, empty children normalized to None",
        ),
        pytest.param(
            {
                "Observation.extension:foo": FlatteningLookupElement(
                    view_definition=ViewDefinitionSnippet(select=[]),
                ),
            },
            {},
            id="leafless root with no children -> removed",
        ),
        pytest.param(
            # Root -> Root.mid -> Root.mid.leaf, none of which carry a column/select of
            # their own. Once the leaf is pruned, "mid" loses its only child and becomes
            # leafless itself, and once "mid" is pruned "Root" does too: deletion
            # propagates upward until nothing is left.
            {
                "Root": FlatteningLookupElement(
                    view_definition=ViewDefinitionSnippet(select=[]),
                    children=["Root.mid"],
                ),
                "Root.mid": FlatteningLookupElement(
                    view_definition=ViewDefinitionSnippet(select=[]),
                    children=["Root.mid.leaf"],
                ),
                "Root.mid.leaf": FlatteningLookupElement(
                    view_definition=ViewDefinitionSnippet(select=[]),
                ),
            },
            {},
            id="chain of nested leafless branches collapses all the way to empty",
        ),
        pytest.param(
            # Same chain as above, but "Root" has a second, valid child ("Root.other").
            # Deletion must stop at "Root" instead of removing it too.
            {
                "Root": FlatteningLookupElement(
                    view_definition=ViewDefinitionSnippet(select=[]),
                    children=["Root.mid", "Root.other"],
                ),
                "Root.mid": FlatteningLookupElement(
                    view_definition=ViewDefinitionSnippet(select=[]),
                    children=["Root.mid.leaf"],
                ),
                "Root.mid.leaf": FlatteningLookupElement(
                    view_definition=ViewDefinitionSnippet(select=[]),
                ),
                "Root.other": FlatteningLookupElement(
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Root_other", path="other", type="string"
                            )
                        ]
                    ),
                ),
            },
            {
                "Root": FlatteningLookupElement(
                    view_definition=ViewDefinitionSnippet(select=[]),
                    children=["Root.other"],
                ),
                "Root.other": FlatteningLookupElement(
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Root_other", path="other", type="string"
                            )
                        ]
                    ),
                    children=None,
                ),
            },
            id="upward deletion stops at an ancestor with a remaining valid child",
        ),
        pytest.param(
            # "resolve()" must remove the element *and* its children outright, even
            # though the child on its own has real content (a column).
            {
                "Observation.subject": FlatteningLookupElement(
                    view_definition=ViewDefinitionSnippet(
                        for_each_or_null="subject.resolve()", select=[]
                    ),
                    children=["Observation.subject.reference"],
                ),
                "Observation.subject.reference": FlatteningLookupElement(
                    view_definition=ViewDefinitionSnippet(
                        column=[
                            ViewDefinitionColumn(
                                name="Observation_subject_reference",
                                path="reference",
                                type="string",
                            )
                        ]
                    ),
                ),
            },
            {},
            id="resolve() in forEachOrNull removes the element and its children",
        ),
    ],
)
def test_flattening_post_process(lookup, expected):
    assert flattening_post_process(lookup) == expected


# --- _flatten_polymorphic / _generate_flattening_polymorphic_child ---------------------


def test_flatten_polymorphic_creates_one_child_per_declared_type(
    generator: FlatteningLookupGenerator,
):
    """
    With no slices defined in the profile, one child is assumed per type listed on the
    element itself
    """
    profile = build_profile(
        "Observation",
        [
            ElementDefinition(
                id="Observation.value[x]",
                path="Observation.value",
                min=0,
                max="1",
                type=[
                    ElementDefinitionType(code="dateTime"),
                    ElementDefinitionType(code="boolean"),
                ],
            ),
        ],
    )

    result = generator._flatten_polymorphic("Observation.value[x]", profile)

    assert set(result.keys()) == {
        "Observation.value[x]",
        "Observation.value[x]:valueDateTime",
        "Observation.value[x]:valueBoolean",
    }
    assert set(result["Observation.value[x]"].children) == {
        "Observation.value[x]:valueDateTime",
        "Observation.value[x]:valueBoolean",
    }
    assert result["Observation.value[x]:valueDateTime"] == FlatteningLookupElement(
        parent="Observation.value[x]",
        view_definition=ViewDefinitionSnippet(
            for_each_or_null="value.ofType(dateTime)",
            select=[
                ViewDefinitionSelect(
                    column=[
                        ViewDefinitionColumn(
                            name="Observation_value_X_Valuedatetime",
                            path="$this",
                            type="dateTime",
                        )
                    ]
                )
            ],
        ),
    )


def test_flatten_polymorphic_honors_explicit_slice_for_a_type_not_listed_on_the_element(
    generator: FlatteningLookupGenerator,
):
    """
    A slice the profile explicitly defines is flattened even if its type isn't one of the
    types declared on the polymorphic element itself - the two sets of children are
    unified, not intersected.
    """
    profile = build_profile(
        "Observation",
        [
            ElementDefinition(
                id="Observation.value[x]",
                path="Observation.value",
                min=0,
                max="1",
                type=[ElementDefinitionType(code="dateTime")],
            ),
            ElementDefinition(
                id="Observation.value[x]:valueString",
                path="Observation.value",
                sliceName="valueString",
                min=0,
                max="1",
                type=[ElementDefinitionType(code="string")],
            ),
        ],
    )

    result = generator._flatten_polymorphic("Observation.value[x]", profile)

    assert set(result["Observation.value[x]"].children) == {
        "Observation.value[x]:valueDateTime",
        "Observation.value[x]:valueString",
    }


def test_flatten_polymorphic_same_type_declared_and_sliced_is_not_duplicated(
    generator: FlatteningLookupGenerator,
):
    """
    A type that is defined in profile as a slice and listed as a possible type
    """
    profile = build_profile(
        "Observation",
        [
            ElementDefinition(
                id="Observation.value[x]",
                path="Observation.value",
                min=0,
                max="1",
                type=[ElementDefinitionType(code="boolean")],
            ),
            ElementDefinition(
                id="Observation.value[x]:valueBoolean",
                path="Observation.value",
                sliceName="valueBoolean",
                min=0,
                max="1",
                type=[ElementDefinitionType(code="boolean")],
            ),
        ],
    )

    result = generator._flatten_polymorphic("Observation.value[x]", profile)

    assert result["Observation.value[x]"].children == [
        "Observation.value[x]:valueBoolean"
    ]


def test_flatten_polymorphic_dropped_entirely_when_every_type_is_excluded(
    generator: FlatteningLookupGenerator,
):
    """
    If none of the possible types produce a usable child (e.g. because they're all
    configured as excluded types), the polymorphic element itself is pruned rather than
    left behind as an empty, useless branch.
    """
    generator.config.excluded_types = ["boolean"]
    profile = build_profile(
        "Observation",
        [
            ElementDefinition(
                id="Observation.value[x]",
                path="Observation.value",
                min=0,
                max="1",
                type=[ElementDefinitionType(code="boolean")],
            ),
        ],
    )

    result = generator._flatten_polymorphic("Observation.value[x]", profile)

    assert result == {}


def test_generate_flattening_polymorphic_child_wraps_primitive_column_in_select(
    generator: FlatteningLookupGenerator,
):
    """
    `_generate_flattening_polymorphic_child` for a primitive type takes the `.column`
    produced by flattening of the primitive child and moves the child's columns under its `select`.
    """
    profile = build_profile(
        "Observation",
        [
            ElementDefinition(
                id="Observation.value[x]",
                path="Observation.value",
                min=0,
                max="1",
                type=[ElementDefinitionType(code="boolean")],
            ),
        ],
    )

    result = generator._generate_flattening_polymorphic_child(
        element_id="Observation.value[x]:valueBoolean",
        profile=profile,
        polymorphic_parent_id="Observation.value[x]",
        type="boolean",
    )

    assert result == {
        "Observation.value[x]:valueBoolean": FlatteningLookupElement(
            parent="Observation.value[x]",
            view_definition=ViewDefinitionSnippet(
                for_each_or_null="value.ofType(boolean)",
                select=[
                    ViewDefinitionSelect(
                        column=[
                            ViewDefinitionColumn(
                                name="Observation_value_X_Valueboolean",
                                path="$this",
                                type="boolean",
                            )
                        ]
                    )
                ],
            ),
        )
    }


def test_generate_flattening_polymorphic_child_keeps_grandchildren_for_a_complex_type(
    generator: FlatteningLookupGenerator,
):
    """
    For a complex type (here Period, via the default config's required children)
    return flattened required children by config and itself (with no column or select)
    """
    profile = build_profile("Observation", [])

    result = generator._generate_flattening_polymorphic_child(
        element_id="Observation.value[x]:valuePeriod",
        profile=profile,
        polymorphic_parent_id="Observation.value[x]",
        type="Period",
    )

    assert set(result.keys()) == {
        "Observation.value[x]:valuePeriod",
        "Observation.value[x]:valuePeriod.start",
        "Observation.value[x]:valuePeriod.end",
    }
    child = result["Observation.value[x]:valuePeriod"]
    assert child.view_definition.select == []
    assert set(child.children) == {
        "Observation.value[x]:valuePeriod.start",
        "Observation.value[x]:valuePeriod.end",
    }


# --- _flatten_coding -----------------------------------------------------------------
_CODE = ElementDefinition(
    id="Observation.code",
    path="Observation.code",
    type=[ElementDefinitionType(code="CodeableConcept")],
)


def test_flatten_coding_not_defined_in_profile_uses_generic_columns(
    generator: FlatteningLookupGenerator,
):
    """
    A "pseudo" Coding that isn't an element of the profile at all (e.g. assumed to exist
    under an extension's value[x]) still gets the generic code/system/version/display/
    userSelected columns.
    """
    profile = build_profile("Observation", [_CODE])

    result = generator._flatten_coding("Observation.code.coding", profile)

    assert result == {
        "Observation.code.coding": FlatteningLookupElement(
            parent="Observation.code",
            view_definition=ViewDefinitionSnippet(
                for_each_or_null="coding",
                column=[
                    ViewDefinitionColumn(
                        name="Observation_code_coding_code", path="code", type="code"
                    ),
                    ViewDefinitionColumn(
                        name="Observation_code_coding_system",
                        path="system",
                        type="uri",
                    ),
                    ViewDefinitionColumn(
                        name="Observation_code_coding_version",
                        path="version",
                        type="string",
                    ),
                    ViewDefinitionColumn(
                        name="Observation_code_coding_display",
                        path="display",
                        type="string",
                    ),
                    ViewDefinitionColumn(
                        name="Observation_code_coding_userSelected",
                        path="userSelected",
                        type="boolean",
                    ),
                ],
            ),
        )
    }


def test_flatten_coding_without_slicing_uses_generic_columns(
    generator: FlatteningLookupGenerator,
):
    """
    A Coding that is defined in the profile but has no slices of its own is flattened the
    same generic way as a pseudo Coding.
    """
    profile = build_profile(
        "Observation",
        [
            _CODE,
            ElementDefinition(
                id="Observation.code.coding",
                path="Observation.code.coding",
                type=[ElementDefinitionType(code="Coding")],
            ),
        ],
    )

    result = generator._flatten_coding("Observation.code.coding", profile)

    assert (
        result["Observation.code.coding"].view_definition.for_each_or_null == "coding"
    )
    assert result["Observation.code.coding"].view_definition.column is not None


def test_flatten_coding_slice_without_extractable_discriminator_is_dropped(
    generator: FlatteningLookupGenerator,
):
    """
    A slice whose discriminator can't be resolved into a FHIRPath filter (here: no
    fixed/pattern value and no binding anywhere) is dropped entirely, rather than falling
    back to the same generic (unfiltered) flattening as an unsliced Coding -- an unfiltered
    fallback would collide with sibling slices that share the same base path, since nothing
    would distinguish them anymore
    """
    profile = build_profile(
        "Observation",
        [
            _CODE,
            ElementDefinition(
                id="Observation.code.coding",
                path="Observation.code.coding",
                type=[ElementDefinitionType(code="Coding")],
                slicing=ElementDefinitionSlicing(
                    discriminator=[
                        ElementDefinitionSlicingDiscriminator(
                            type="value", path="system"
                        )
                    ],
                    rules="open",
                ),
            ),
            ElementDefinition(
                id="Observation.code.coding:foo",
                path="Observation.code.coding",
                sliceName="foo",
                type=[ElementDefinitionType(code="Coding")],
            ),
        ],
    )

    result = generator._flatten_coding("Observation.code.coding:foo", profile)

    assert result == {}


def test_flatten_coding_slice_with_pattern_discriminator_flattens_children(
    generator: FlatteningLookupGenerator,
):
    """
    A slice discriminated by a fixed/pattern value on `.system` gets a `where()` filter
    built from it, flattens the children the profile explicitly defines, and fills in any
    of the generically-required Coding children (version/display/userSelected) that the
    profile leaves undefined.
    """
    profile = build_profile(
        "Observation",
        [
            _CODE,
            ElementDefinition(
                id="Observation.code.coding",
                path="Observation.code.coding",
                type=[ElementDefinitionType(code="Coding")],
                slicing=ElementDefinitionSlicing(
                    discriminator=[
                        ElementDefinitionSlicingDiscriminator(
                            type="value", path="system"
                        )
                    ],
                    rules="open",
                ),
            ),
            ElementDefinition(
                id="Observation.code.coding:sct",
                path="Observation.code.coding",
                sliceName="sct",
                type=[ElementDefinitionType(code="Coding")],
            ),
            ElementDefinition(
                id="Observation.code.coding:sct.system",
                path="Observation.code.coding.system",
                patternUri="http://snomed.info/sct",
                type=[ElementDefinitionType(code="uri")],
            ),
        ],
    )

    result = generator._flatten_coding("Observation.code.coding:sct", profile)

    slice_el = result["Observation.code.coding:sct"]
    assert slice_el.view_definition.for_each_or_null == (
        "coding.where(system = 'http://snomed.info/sct')"
    )
    assert set(slice_el.children) == {
        "Observation.code.coding:sct.system",
        "Observation.code.coding:sct.version",
        "Observation.code.coding:sct.display",
        "Observation.code.coding:sct.userSelected",
        "Observation.code.coding:sct.code",
    }
    # explicitly defined
    assert (
        result["Observation.code.coding:sct.system"].view_definition.column[0].path
        == "system"
    )
    # not defined in the profile, filled from config
    assert (
        result["Observation.code.coding:sct.version"].view_definition.column[0].path
        == "version"
    )


def test_flatten_coding_slice_parent_points_to_codeable_concept_not_to_coding_collection(
    generator: FlatteningLookupGenerator,
):
    """
    When flattened as part of a CodeableConcept, a Coding slice's `parent` skips the
    intermediate `.coding` collection element (which never gets its own lookup entry) and
    points straight at the CodeableConcept, using the explicit `codeable_concept_parent`
    rather than the slice's structural parent.
    """
    profile = build_profile(
        "Observation",
        [
            _CODE,
            ElementDefinition(
                id="Observation.code.coding",
                path="Observation.code.coding",
                type=[ElementDefinitionType(code="Coding")],
                slicing=ElementDefinitionSlicing(
                    discriminator=[
                        ElementDefinitionSlicingDiscriminator(
                            type="value", path="system"
                        )
                    ],
                    rules="open",
                ),
            ),
            ElementDefinition(
                id="Observation.code.coding:sct",
                path="Observation.code.coding",
                sliceName="sct",
                type=[ElementDefinitionType(code="Coding")],
            ),
            ElementDefinition(
                id="Observation.code.coding:sct.system",
                path="Observation.code.coding.system",
                patternUri="http://snomed.info/sct",
                type=[ElementDefinitionType(code="uri")],
            ),
        ],
    )

    result = generator._flatten_coding(
        "Observation.code.coding:sct",
        profile,
        codeable_concept_parent="Observation.code",
    )

    assert result["Observation.code.coding:sct"].parent == "Observation.code"


class _FakeTerminologyClient:
    """Minimal stand-in for `FhirTerminologyClient`, returning a fixed set of expanded codes"""

    def __init__(self, codes: list[str]):
        self._codes = codes

    def expand_value_set(self, url: str, version: str = None):
        return {"expansion": {"contains": [{"code": c} for c in self._codes]}}


def test_flatten_coding_slice_discriminated_by_required_binding(
    generator: FlatteningLookupGenerator,
):
    """
    A discriminator naming `.code`, where `.code` carries a *required* binding (and no
    fixed/pattern value anywhere), is trusted outright. `.code` here is `Coding.code`, a
    plain `code` primitive rather than `Coding`/`CodeableConcept` -- our terminology engine
    (Pathling) can't evaluate `memberOf()` against that, so the bound value set is expanded
    and the filter lists the allowed codes explicitly instead.
    """
    generator.client = _FakeTerminologyClient(["c1", "c2"])
    profile = build_profile(
        "Observation",
        [
            _CODE,
            ElementDefinition(
                id="Observation.code.coding",
                path="Observation.code.coding",
                type=[ElementDefinitionType(code="Coding")],
                slicing=ElementDefinitionSlicing(
                    discriminator=[
                        ElementDefinitionSlicingDiscriminator(type="value", path="code")
                    ],
                    rules="open",
                ),
            ),
            ElementDefinition(
                id="Observation.code.coding:loinc",
                path="Observation.code.coding",
                sliceName="loinc",
                type=[ElementDefinitionType(code="Coding")],
            ),
            ElementDefinition(
                id="Observation.code.coding:loinc.code",
                path="Observation.code.coding.code",
                type=[ElementDefinitionType(code="code")],
                binding=ElementDefinitionBinding(
                    strength="required",
                    valueSet="http://hl7.org/fhir/ValueSet/observation-codes",
                ),
            ),
        ],
    )

    result = generator._flatten_coding("Observation.code.coding:loinc", profile)

    assert result["Observation.code.coding:loinc"].view_definition.for_each_or_null == (
        "coding.where(code.exists($this = 'c1' or $this = 'c2'))"
    )


def test_flatten_coding_slice_discriminated_by_non_required_binding_is_used_as_last_resort(
    generator: FlatteningLookupGenerator,
):
    """
    A non-required binding (`preferred`, `extensible`, ...) is only trusted as a last
    resort, used solely because nothing more specific (fixed/pattern) exists anywhere in
    the slice - "a weak binding is still better than no filter at all". With nothing else
    defined, it still produces the same expanded-value-set filter a required binding would.
    """
    generator.client = _FakeTerminologyClient(["c1"])
    profile = build_profile(
        "Observation",
        [
            _CODE,
            ElementDefinition(
                id="Observation.code.coding",
                path="Observation.code.coding",
                type=[ElementDefinitionType(code="Coding")],
                slicing=ElementDefinitionSlicing(
                    discriminator=[
                        ElementDefinitionSlicingDiscriminator(type="value", path="code")
                    ],
                    rules="open",
                ),
            ),
            ElementDefinition(
                id="Observation.code.coding:loinc",
                path="Observation.code.coding",
                sliceName="loinc",
                type=[ElementDefinitionType(code="Coding")],
            ),
            ElementDefinition(
                id="Observation.code.coding:loinc.code",
                path="Observation.code.coding.code",
                type=[ElementDefinitionType(code="code")],
                binding=ElementDefinitionBinding(
                    strength="preferred",
                    valueSet="http://hl7.org/fhir/ValueSet/observation-codes",
                ),
            ),
        ],
    )

    result = generator._flatten_coding("Observation.code.coding:loinc", profile)

    assert result == {}


def test_flatten_coding_slice_discriminated_by_required_binding_on_coding_uses_member_of(
    generator: FlatteningLookupGenerator,
):
    """
    A required binding declared directly on a `Coding`-typed element (rather than on its
    `.code`/`.system` primitives) *is* something Pathling can evaluate `memberOf()`
    against, so that's what the filter uses -- no need to expand the value set for it.
    """
    profile = build_profile(
        "Observation",
        [
            _CODE,
            ElementDefinition(
                id="Observation.code.coding",
                path="Observation.code.coding",
                type=[ElementDefinitionType(code="Coding")],
                slicing=ElementDefinitionSlicing(
                    discriminator=[
                        ElementDefinitionSlicingDiscriminator(
                            type="value", path="$this"
                        )
                    ],
                    rules="open",
                ),
            ),
            ElementDefinition(
                id="Observation.code.coding:loinc",
                path="Observation.code.coding",
                sliceName="loinc",
                type=[ElementDefinitionType(code="Coding")],
                binding=ElementDefinitionBinding(
                    strength="required",
                    valueSet="http://hl7.org/fhir/ValueSet/observation-codes",
                ),
            ),
        ],
    )

    result = generator._flatten_coding("Observation.code.coding:loinc", profile)

    assert result["Observation.code.coding:loinc"].view_definition.for_each_or_null == (
        "coding.where(memberOf('http://hl7.org/fhir/ValueSet/observation-codes'))"
    )


def test_flatten_coding_slice_discriminated_by_system_and_code_combines_both(
    generator: FlatteningLookupGenerator,
):
    """
    Filter built from code and system, concat by "and"
    """
    profile = build_profile(
        "Observation",
        [
            _CODE,
            ElementDefinition(
                id="Observation.code.coding",
                path="Observation.code.coding",
                type=[ElementDefinitionType(code="Coding")],
                slicing=ElementDefinitionSlicing(
                    discriminator=[
                        ElementDefinitionSlicingDiscriminator(
                            type="value", path="system"
                        ),
                        ElementDefinitionSlicingDiscriminator(
                            type="value", path="code"
                        ),
                    ],
                    rules="open",
                ),
            ),
            ElementDefinition(
                id="Observation.code.coding:sct",
                path="Observation.code.coding",
                sliceName="sct",
                type=[ElementDefinitionType(code="Coding")],
            ),
            ElementDefinition(
                id="Observation.code.coding:sct.system",
                path="Observation.code.coding.system",
                patternUri="http://snomed.info/sct",
                type=[ElementDefinitionType(code="uri")],
            ),
            ElementDefinition(
                id="Observation.code.coding:sct.code",
                path="Observation.code.coding.code",
                patternCode="184099003",
                type=[ElementDefinitionType(code="code")],
            ),
        ],
    )

    result = generator._flatten_coding("Observation.code.coding:sct", profile)

    assert result["Observation.code.coding:sct"].view_definition.for_each_or_null == (
        "coding.where(system = 'http://snomed.info/sct' and code = '184099003')"
    )


# --- _flatten_codeable_concept ---------------------------------------------------------

_CODING_SLICED_BY_SYSTEM = ElementDefinition(
    id="Observation.code.coding",
    path="Observation.code.coding",
    type=[ElementDefinitionType(code="Coding")],
    slicing=ElementDefinitionSlicing(
        discriminator=[
            ElementDefinitionSlicingDiscriminator(type="value", path="system")
        ],
        rules="open",
    ),
)


def test_flatten_codeable_concept_flattens_defined_coding_slices(
    generator: FlatteningLookupGenerator,
):
    """
    A `.coding` with slices defined gets one child per slice, each flattened via
    `_flatten_coding`; the CodeableConcept itself carries no columns of its own.
    """
    profile = build_profile(
        "Observation",
        [
            _CODE,
            _CODING_SLICED_BY_SYSTEM,
            ElementDefinition(
                id="Observation.code.coding:sct",
                path="Observation.code.coding",
                sliceName="sct",
                type=[ElementDefinitionType(code="Coding")],
            ),
            ElementDefinition(
                id="Observation.code.coding:sct.system",
                path="Observation.code.coding.system",
                patternUri="http://snomed.info/sct",
                type=[ElementDefinitionType(code="uri")],
            ),
        ],
    )

    result = generator._flatten_codeable_concept("Observation.code", profile)

    assert result["Observation.code"] == FlatteningLookupElement(
        view_definition=ViewDefinitionSnippet(for_each_or_null="code", select=[]),
        children=["Observation.code.coding:sct"],
    )
    assert result["Observation.code.coding:sct"].view_definition.for_each_or_null == (
        "coding.where(system = 'http://snomed.info/sct')"
    )


def test_flatten_codeable_concept_falls_back_to_generic_coding_without_slices(
    generator: FlatteningLookupGenerator,
):
    """
    A `.coding` with no slices defined falls back to a single generic `.coding` child,
    same as when `.coding` isn't defined at all.
    """
    profile = build_profile(
        "Observation",
        [
            _CODE,
            ElementDefinition(
                id="Observation.code.coding",
                path="Observation.code.coding",
                type=[ElementDefinitionType(code="Coding")],
            ),
        ],
    )

    result = generator._flatten_codeable_concept("Observation.code", profile)

    assert result["Observation.code"].children == ["Observation.code.coding"]
    assert result["Observation.code.coding"].view_definition.column is not None


def test_flatten_codeable_concept_falls_back_to_generic_coding_without_coding_element(
    generator: FlatteningLookupGenerator,
):
    """
    No `.coding` element defined in the profile at all -> same generic fallback as an
    empty slicing.
    """
    profile = build_profile("Observation", [_CODE])

    result = generator._flatten_codeable_concept("Observation.code", profile)

    assert result["Observation.code"].children == ["Observation.code.coding"]
    assert result["Observation.code.coding"].view_definition.column is not None


def test_flatten_codeable_concept_prunes_itself_when_every_slice_fails(
    generator: FlatteningLookupGenerator,
):
    """
    If every slice fails to flatten (here: "Coding" is an excluded type), the
    CodeableConcept itself is dropped rather than left behind with empty children.
    """
    generator.config.excluded_types = ["Coding"]
    profile = build_profile(
        "Observation",
        [
            _CODE,
            _CODING_SLICED_BY_SYSTEM,
            ElementDefinition(
                id="Observation.code.coding:sct",
                path="Observation.code.coding",
                sliceName="sct",
                type=[ElementDefinitionType(code="Coding")],
            ),
        ],
    )

    result = generator._flatten_codeable_concept("Observation.code", profile)

    assert result == {}


# --- _flatten_identifier ----------------------------------------------------------------

_PATIENT_IDENTIFIER_SLICED = ElementDefinition(
    id="Patient.identifier",
    path="Patient.identifier",
    type=[ElementDefinitionType(code="Identifier")],
    slicing=ElementDefinitionSlicing(rules="open"),
)


def test_flatten_identifier_not_in_profile_returns_empty(
    generator: FlatteningLookupGenerator,
):
    """
    No element definition at all for the given id -> nothing to flatten.
    """
    profile = build_profile("Patient", [])

    result = generator._flatten_identifier("Patient.identifier", profile)

    assert result == {}


def test_flatten_identifier_slice_list_filters_out_non_identifier_slices(
    generator: FlatteningLookupGenerator,
):
    """
    When `.identifier` is sliced, only slices actually typed as Identifier are flattened
    as children - a same-named slice of a different type is ignored.
    """
    profile = build_profile(
        "Patient",
        [
            _PATIENT_IDENTIFIER_SLICED,
            ElementDefinition(
                id="Patient.identifier:mrn",
                path="Patient.identifier",
                sliceName="mrn",
                type=[ElementDefinitionType(code="Identifier")],
            ),
            ElementDefinition(
                id="Patient.identifier:decoy",
                path="Patient.identifier",
                sliceName="decoy",
                type=[ElementDefinitionType(code="CodeableConcept")],
            ),
        ],
    )

    result = generator._flatten_identifier("Patient.identifier", profile)

    assert result["Patient.identifier"].children == ["Patient.identifier:mrn"]
    assert result["Patient.identifier"].view_definition.for_each_or_null == "identifier"


def test_flatten_identifier_unsliced_flattens_all_required_children(
    generator: FlatteningLookupGenerator,
):
    """
    An unsliced identifier gets one child per entry in the default config's required
    Identifier children (use/type/system/value/period/assigner).
    """
    profile = build_profile(
        "Patient",
        [
            ElementDefinition(
                id="Patient.identifier",
                path="Patient.identifier",
                type=[ElementDefinitionType(code="Identifier")],
            ),
        ],
    )

    result = generator._flatten_identifier("Patient.identifier", profile)

    assert set(result["Patient.identifier"].children) == {
        "Patient.identifier.use",
        "Patient.identifier.type",
        "Patient.identifier.system",
        "Patient.identifier.value",
        "Patient.identifier.period",
        "Patient.identifier.assigner",
    }
    assert result["Patient.identifier"].view_definition.for_each_or_null == "identifier"


def test_flatten_identifier_slice_uses_its_own_discriminator_when_present(
    generator: FlatteningLookupGenerator,
):
    """
    A slice with a `patternIdentifier` discriminates on itself (`$this`)
    """
    profile = build_profile(
        "Patient",
        [
            _PATIENT_IDENTIFIER_SLICED,
            ElementDefinition(
                id="Patient.identifier:mrn",
                path="Patient.identifier",
                sliceName="mrn",
                type=[ElementDefinitionType(code="Identifier")],
                patternIdentifier=Identifier(system="http://example.org/mrn"),
            ),
        ],
    )

    result = generator._flatten_identifier("Patient.identifier:mrn", profile)

    assert result["Patient.identifier:mrn"].view_definition.for_each_or_null == (
        "$this.where(system = 'http://example.org/mrn')"
    )


def test_flatten_identifier_slice_that_fails_to_flatten_is_not_listed_as_a_child(
    generator: FlatteningLookupGenerator,
):
    """
    A slice is only added to `children` once it's actually been flattened - a slice that
    fails (here: "Identifier" is an excluded type) leaves no dangling reference behind.
    """
    generator.config.excluded_types = ["Identifier"]
    profile = build_profile(
        "Patient",
        [
            _PATIENT_IDENTIFIER_SLICED,
            ElementDefinition(
                id="Patient.identifier:mrn",
                path="Patient.identifier",
                sliceName="mrn",
                type=[ElementDefinitionType(code="Identifier")],
            ),
        ],
    )

    result = generator._flatten_identifier("Patient.identifier", profile)

    assert result["Patient.identifier"].children == []
    assert "Patient.identifier:mrn" not in result


# --- _flatten_backbone_element -----------------------------------------------------------

_COMPONENT_SLICED = ElementDefinition(
    id="Observation.component",
    path="Observation.component",
    type=[ElementDefinitionType(code="BackboneElement")],
    slicing=ElementDefinitionSlicing(rules="open"),
)


def test_flatten_backbone_element_unsliced_uses_all_direct_children(
    generator: FlatteningLookupGenerator,
):
    """
    An unsliced BackboneElement gets one child per direct sub-element the profile defines.
    """
    profile = build_profile(
        "Observation",
        [
            ElementDefinition(
                id="Observation.referenceRange",
                path="Observation.referenceRange",
                type=[ElementDefinitionType(code="BackboneElement")],
            ),
            ElementDefinition(
                id="Observation.referenceRange.low",
                path="Observation.referenceRange.low",
                type=[ElementDefinitionType(code="Quantity")],
            ),
            ElementDefinition(
                id="Observation.referenceRange.high",
                path="Observation.referenceRange.high",
                type=[ElementDefinitionType(code="Quantity")],
            ),
        ],
    )

    result = generator._flatten_backbone_element("Observation.referenceRange", profile)

    assert set(result["Observation.referenceRange"].children) == {
        "Observation.referenceRange.low",
        "Observation.referenceRange.high",
    }
    assert (
        result["Observation.referenceRange"].view_definition.for_each_or_null
        == "referenceRange"
    )


def test_flatten_backbone_element_slice_uses_its_own_discriminator_when_present(
    generator: FlatteningLookupGenerator,
):
    """
    A BackboneElement slice discriminated by a fixed/pattern value on `.code` gets a
    `$this.where(...)` filter built from it, instead of the plain element-name for-each.
    """
    profile = build_profile(
        "Observation",
        [
            ElementDefinition(
                id="Observation.component",
                path="Observation.component",
                type=[ElementDefinitionType(code="BackboneElement")],
                slicing=ElementDefinitionSlicing(
                    discriminator=[
                        ElementDefinitionSlicingDiscriminator(type="value", path="code")
                    ],
                    rules="open",
                ),
            ),
            ElementDefinition(
                id="Observation.component:systolic",
                path="Observation.component",
                sliceName="systolic",
                type=[ElementDefinitionType(code="BackboneElement")],
            ),
            ElementDefinition(
                id="Observation.component:systolic.code",
                path="Observation.component.code",
                type=[ElementDefinitionType(code="CodeableConcept")],
                patternCodeableConcept=CodeableConcept(
                    coding=[Coding(system="http://loinc.org", code="8480-6")]
                ),
            ),
        ],
    )

    result = generator._flatten_backbone_element(
        "Observation.component:systolic", profile
    )

    assert result[
        "Observation.component:systolic"
    ].view_definition.for_each_or_null == (
        "$this.where(code.coding.exists(system = 'http://loinc.org' and code = '8480-6'))"
    )


def test_flatten_backbone_element_slice_is_dropped_when_discriminator_fails(
    generator: FlatteningLookupGenerator,
):
    """
    A slice whose discriminator can't be resolved (here: the parent defines no slicing
    discriminators at all) is dropped entirely, rather than kept under the plain
    element-name for-each -- that unfiltered for-each is shared by every sibling slice, so
    keeping it here would make this slice indistinguishable from them
    """
    profile = build_profile(
        "Observation",
        [
            _COMPONENT_SLICED,
            ElementDefinition(
                id="Observation.component:systolic",
                path="Observation.component",
                sliceName="systolic",
                type=[ElementDefinitionType(code="BackboneElement")],
            ),
            ElementDefinition(
                id="Observation.component:systolic.value",
                path="Observation.component.value",
                type=[ElementDefinitionType(code="string")],
            ),
        ],
    )

    result = generator._flatten_backbone_element(
        "Observation.component:systolic", profile
    )

    assert result == {}


def test_flatten_backbone_element_drops_slices_that_collide_on_the_same_fallback_binding(
    generator: FlatteningLookupGenerator,
):
    """
    Two sibling slices whose `.code` carries no fixed/pattern value, only the identical
    non-required binding, both fall back to that same binding and  nothing actually distinguishes them.
    Both are dropped entirely instead
    """
    binding = ElementDefinitionBinding(
        strength="example",
        valueSet="http://hl7.org/fhir/ValueSet/observation-codes",
    )
    profile = build_profile(
        "Observation",
        [
            ElementDefinition(
                id="Observation.component",
                path="Observation.component",
                type=[ElementDefinitionType(code="BackboneElement")],
                slicing=ElementDefinitionSlicing(
                    discriminator=[
                        ElementDefinitionSlicingDiscriminator(type="value", path="code")
                    ],
                    rules="open",
                ),
            ),
            ElementDefinition(
                id="Observation.component:foo",
                path="Observation.component",
                sliceName="foo",
                type=[ElementDefinitionType(code="BackboneElement")],
            ),
            ElementDefinition(
                id="Observation.component:foo.code",
                path="Observation.component.code",
                type=[ElementDefinitionType(code="CodeableConcept")],
                binding=binding,
            ),
            ElementDefinition(
                id="Observation.component:bar",
                path="Observation.component",
                sliceName="bar",
                type=[ElementDefinitionType(code="BackboneElement")],
            ),
            ElementDefinition(
                id="Observation.component:bar.code",
                path="Observation.component.code",
                type=[ElementDefinitionType(code="CodeableConcept")],
                binding=binding,
            ),
        ],
    )

    result = generator._flatten_backbone_element("Observation.component", profile)

    assert result == {}


def test_flatten_backbone_element_prunes_itself_when_every_child_fails(
    generator: FlatteningLookupGenerator,
):
    """
    If every direct child fails to flatten (here: "string" is an excluded type), the
    BackboneElement itself is dropped rather than left behind with empty children.
    """
    generator.config.excluded_types = ["string"]
    profile = build_profile(
        "Observation",
        [
            ElementDefinition(
                id="Observation.referenceRange",
                path="Observation.referenceRange",
                type=[ElementDefinitionType(code="BackboneElement")],
            ),
            ElementDefinition(
                id="Observation.referenceRange.text",
                path="Observation.referenceRange.text",
                type=[ElementDefinitionType(code="string")],
            ),
        ],
    )

    result = generator._flatten_backbone_element("Observation.referenceRange", profile)

    assert result == {}


def test_flatten_backbone_element_slice_that_fails_to_flatten_is_not_listed_as_a_child(
    generator: FlatteningLookupGenerator,
):
    """
    A slice is only added to `children` once it's actually been flattened - a slice that
    fails (here: "BackboneElement" is an excluded type) leaves no dangling reference, and
    the parent - having no valid children left - is pruned too.
    """
    generator.config.excluded_types = ["BackboneElement"]
    profile = build_profile(
        "Observation",
        [
            _COMPONENT_SLICED,
            ElementDefinition(
                id="Observation.component:systolic",
                path="Observation.component",
                sliceName="systolic",
                type=[ElementDefinitionType(code="BackboneElement")],
            ),
            ElementDefinition(
                id="Observation.component:systolic.value",
                path="Observation.component.value",
                type=[ElementDefinitionType(code="string")],
            ),
        ],
    )

    result = generator._flatten_backbone_element("Observation.component", profile)

    assert result == {}


# --- _flatten_generic_complex_element -----------------------------------------------------

_MARITAL_PERIOD = ElementDefinition(
    id="Patient.maritalPeriod",
    path="Patient.maritalPeriod",
    type=[ElementDefinitionType(code="Period")],
)

_MARITAL_PERIOD_SLICED = ElementDefinition(
    id="Patient.maritalPeriod",
    path="Patient.maritalPeriod",
    type=[ElementDefinitionType(code="Period")],
    slicing=ElementDefinitionSlicing(
        discriminator=[
            ElementDefinitionSlicingDiscriminator(type="exists", path="start")
        ],
        rules="open",
    ),
)


def test_flatten_generic_complex_element_unsliced_flattens_required_children(
    generator: FlatteningLookupGenerator,
):
    """
    An unsliced Period field gets its required children (`.start`/`.end`, via the default
    config) flattened underneath it.
    """
    profile = build_profile("Patient", [_MARITAL_PERIOD])

    result = generator._flatten_generic_complex_element(
        "Patient.maritalPeriod", profile
    )

    assert set(result["Patient.maritalPeriod"].children) == {
        "Patient.maritalPeriod.start",
        "Patient.maritalPeriod.end",
    }
    assert (
        result["Patient.maritalPeriod"].view_definition.for_each_or_null
        == "maritalPeriod"
    )


def test_flatten_generic_complex_element_slicing_only_includes_same_typed_slices(
    generator: FlatteningLookupGenerator,
):
    """
    When the element itself is sliced (and isn't a polymorphic value[x]), only slices
    typed the same as the element are flattened as children - a same-named slice of a
    different type is ignored.
    """
    profile = build_profile(
        "Patient",
        [
            _MARITAL_PERIOD_SLICED,
            ElementDefinition(
                id="Patient.maritalPeriod:early",
                path="Patient.maritalPeriod",
                sliceName="early",
                type=[ElementDefinitionType(code="Period")],
            ),
            ElementDefinition(
                id="Patient.maritalPeriod:decoy",
                path="Patient.maritalPeriod",
                sliceName="decoy",
                type=[ElementDefinitionType(code="Quantity")],
            ),
        ],
    )

    result = generator._flatten_generic_complex_element(
        "Patient.maritalPeriod", profile
    )

    assert result["Patient.maritalPeriod"].children == ["Patient.maritalPeriod:early"]
    assert set(result["Patient.maritalPeriod:early"].children) == {
        "Patient.maritalPeriod:early.start",
        "Patient.maritalPeriod:early.end",
    }


def test_flatten_generic_complex_element_slice_uses_its_own_discriminator(
    generator: FlatteningLookupGenerator,
):
    """
    A slice with a resolvable discriminator gets a `$this.where(...)` for-each instead of
    the plain element-name default.
    """
    profile = build_profile(
        "Patient",
        [
            _MARITAL_PERIOD_SLICED,
            ElementDefinition(
                id="Patient.maritalPeriod:early",
                path="Patient.maritalPeriod",
                sliceName="early",
                type=[ElementDefinitionType(code="Period")],
            ),
        ],
    )

    result = generator._flatten_generic_complex_element(
        "Patient.maritalPeriod:early", profile
    )

    assert result["Patient.maritalPeriod:early"].view_definition.for_each_or_null == (
        "$this.where(start.exists())"
    )


def test_flatten_generic_complex_element_slice_with_unresolvable_discriminator_returns_empty(
    generator: FlatteningLookupGenerator,
):
    """
    Unlike `_flatten_backbone_element` (which falls back to the plain element-name
    for-each), a slice whose discriminator can't be resolved here drops the whole element
    outright - no fallback.
    """
    profile = build_profile(
        "Patient",
        [
            ElementDefinition(
                id="Patient.maritalPeriod",
                path="Patient.maritalPeriod",
                type=[ElementDefinitionType(code="Period")],
                slicing=ElementDefinitionSlicing(rules="open"),
            ),
            ElementDefinition(
                id="Patient.maritalPeriod:early",
                path="Patient.maritalPeriod",
                sliceName="early",
                type=[ElementDefinitionType(code="Period")],
            ),
        ],
    )

    result = generator._flatten_generic_complex_element(
        "Patient.maritalPeriod:early", profile
    )

    assert result == {}


def test_flatten_generic_complex_element_prunes_itself_when_every_child_fails(
    generator: FlatteningLookupGenerator,
):
    """
    If every required child fails to flatten (here: "dateTime" is an excluded type, which
    knocks out both `.start` and `.end`), the element itself is dropped rather than left
    behind with empty children.
    """
    generator.config.excluded_types = ["dateTime"]
    profile = build_profile("Patient", [_MARITAL_PERIOD])

    result = generator._flatten_generic_complex_element(
        "Patient.maritalPeriod", profile
    )

    assert result == {}


# --- _flatten_extension -------------------------------------------------------------------


class _FakePackageManager:
    """Minimal stand-in for `FhirPackageManager`, resolving canonical URLs from a dict."""

    def __init__(self, profiles: dict):
        self._profiles = profiles

    def find_struct_def(self, url):
        return self._profiles.get(url)


_CONDITION_EXTENSION_SLICED = ElementDefinition(
    id="Condition.extension",
    path="Condition.extension",
    type=[ElementDefinitionType(code="Extension")],
    slicing=ElementDefinitionSlicing(rules="open"),
)


def _local_extension_elements(slice_name: str, value_type: str = "string") -> list:
    """A self-contained (no separate StructureDefinition) simple-valued extension slice."""
    base = f"Condition.extension:{slice_name}"
    return [
        ElementDefinition(
            id=base,
            path="Condition.extension",
            sliceName=slice_name,
            type=[ElementDefinitionType(code="Extension")],
        ),
        ElementDefinition(
            id=f"{base}.url",
            path="Condition.extension.url",
            fixedUri=f"http://example.org/{slice_name}",
            type=[ElementDefinitionType(code="uri")],
        ),
        ElementDefinition(
            id=f"{base}.value[x]",
            path="Condition.extension.value",
            type=[ElementDefinitionType(code=value_type)],
        ),
    ]


def test_flatten_extension_base_container_without_slices_is_pruned(
    generator: FlatteningLookupGenerator,
):
    """
    The slicing-defining `.extension` element with no actual slices produces nothing to
    select, so it's pruned rather than left behind empty.
    """
    profile = build_profile("Condition", [_CONDITION_EXTENSION_SLICED])

    result = generator._flatten_extension("Condition.extension", profile)

    assert result == {}


def test_flatten_extension_base_container_flattens_defined_slices(
    generator: FlatteningLookupGenerator,
):
    profile = build_profile(
        "Condition",
        [
            _CONDITION_EXTENSION_SLICED,
            *_local_extension_elements("foo"),
            *_local_extension_elements("bar"),
        ],
    )

    result = generator._flatten_extension("Condition.extension", profile)

    assert set(result["Condition.extension"].children) == {
        "Condition.extension:foo",
        "Condition.extension:bar",
    }


def test_flatten_extension_slice_that_fails_to_flatten_is_not_listed_as_a_child(
    generator: FlatteningLookupGenerator,
):
    """
    A slice is only added to `children` once it's actually been flattened - a slice that
    fails (here: "integer" is an excluded type) leaves no dangling reference behind.
    """
    generator.config.excluded_types = ["integer"]
    profile = build_profile(
        "Condition",
        [
            _CONDITION_EXTENSION_SLICED,
            *_local_extension_elements("foo", value_type="string"),
            *_local_extension_elements("bar", value_type="integer"),
        ],
    )

    result = generator._flatten_extension("Condition.extension", profile)

    assert result["Condition.extension"].children == ["Condition.extension:foo"]
    assert "Condition.extension:bar" not in result


def test_flatten_extension_local_extension_without_separate_profile(
    generator: FlatteningLookupGenerator,
):
    """
    A slice with no `type[x].profile` reference but with its own locally-defined `.url`/
    `.value[x]` children is flattened directly against the same profile, filtered by its
    fixed url.
    """
    profile = build_profile(
        "Condition",
        [_CONDITION_EXTENSION_SLICED, *_local_extension_elements("foo")],
    )

    result = generator._flatten_extension("Condition.extension:foo", profile)

    assert result["Condition.extension:foo"].view_definition.for_each_or_null == (
        "extension.where(url = 'http://example.org/foo')"
    )
    assert result["Condition.extension:foo"].children == [
        "Condition.extension:foo.value[x]"
    ]


def test_flatten_extension_slice_with_unresolvable_profile_is_pruned(
    generator: FlatteningLookupGenerator,
):
    """
    A `type[x].profile` reference the package manager can't resolve logs an error and
    ends up pruned, rather than raising or leaving an empty placeholder behind.
    """
    generator.package_manager = _FakePackageManager({})
    profile = build_profile(
        "Condition",
        [
            _CONDITION_EXTENSION_SLICED,
            ElementDefinition(
                id="Condition.extension:foo",
                path="Condition.extension",
                sliceName="foo",
                type=[
                    ElementDefinitionType(
                        code="Extension", profile=["http://example.org/foo"]
                    )
                ],
            ),
        ],
    )

    result = generator._flatten_extension("Condition.extension:foo", profile)

    assert result == {}


def test_flatten_extension_slice_with_external_profile_simple_value(
    generator: FlatteningLookupGenerator,
):
    """
    A slice referencing an external extension profile whose `Extension.value[x]` is
    allowed (max > 0) flattens that value polymorphically and recontextualizes it under
    the slice's own id.
    """
    ext_profile = build_profile(
        "Extension",
        [
            ElementDefinition(
                id="Extension.value[x]",
                path="Extension.value",
                min=0,
                max="1",
                type=[ElementDefinitionType(code="string")],
            ),
        ],
        url="http://example.org/StructureDefinition/simple-ext",
    )
    generator.package_manager = _FakePackageManager(
        {"http://example.org/StructureDefinition/simple-ext": ext_profile}
    )
    profile = build_profile(
        "Condition",
        [
            _CONDITION_EXTENSION_SLICED,
            ElementDefinition(
                id="Condition.extension:foo",
                path="Condition.extension",
                sliceName="foo",
                type=[
                    ElementDefinitionType(
                        code="Extension",
                        profile=["http://example.org/StructureDefinition/simple-ext"],
                    )
                ],
            ),
        ],
    )

    result = generator._flatten_extension("Condition.extension:foo", profile)

    assert result["Condition.extension:foo"].children == [
        "Condition.extension:foo.value[x]"
    ]
    assert "Condition.extension:foo.value[x]:valueString" in result


def test_flatten_extension_slice_with_external_profile_compound_children(
    generator: FlatteningLookupGenerator,
):
    """
    A slice referencing an external extension profile whose `Extension.value[x]` is
    disallowed (max = 0) instead flattens its nested sub-extensions (via the profile's own
    `Extension.extension` slicing) and recontextualizes the whole subtree under the outer
    slice's id.
    """

    def sub_extension(name: str) -> list:
        base = f"Extension.extension:{name}"
        return [
            ElementDefinition(
                id=base,
                path="Extension.extension",
                sliceName=name,
                type=[ElementDefinitionType(code="Extension")],
            ),
            ElementDefinition(
                id=f"{base}.url",
                path="Extension.extension.url",
                fixedUri=name,
                type=[ElementDefinitionType(code="uri")],
            ),
            ElementDefinition(
                id=f"{base}.value[x]",
                path="Extension.extension.value",
                type=[ElementDefinitionType(code="string")],
            ),
        ]

    ext_profile = build_profile(
        "Extension",
        [
            ElementDefinition(
                id="Extension.extension",
                path="Extension.extension",
                type=[ElementDefinitionType(code="Extension")],
                slicing=ElementDefinitionSlicing(rules="open"),
            ),
            *sub_extension("reasonStart"),
            *sub_extension("reasonEnd"),
            ElementDefinition(id="Extension.value[x]", path="Extension.value", max="0"),
        ],
        url="http://example.org/StructureDefinition/compound-ext",
    )
    generator.package_manager = _FakePackageManager(
        {"http://example.org/StructureDefinition/compound-ext": ext_profile}
    )
    profile = build_profile(
        "Condition",
        [
            _CONDITION_EXTENSION_SLICED,
            ElementDefinition(
                id="Condition.extension:compound",
                path="Condition.extension",
                sliceName="compound",
                type=[
                    ElementDefinitionType(
                        code="Extension",
                        profile=["http://example.org/StructureDefinition/compound-ext"],
                    )
                ],
            ),
        ],
    )

    result = generator._flatten_extension("Condition.extension:compound", profile)

    assert result["Condition.extension:compound"].children == [
        "Condition.extension:compound.extension"
    ]
    assert set(result["Condition.extension:compound.extension"].children) == {
        "Condition.extension:compound.extension:reasonStart",
        "Condition.extension:compound.extension:reasonEnd",
    }


# --- _flatten_primitive -------------------------------------------------------------------


def test_flatten_primitive_plain_element_uses_a_top_level_column(
    generator: FlatteningLookupGenerator,
):
    profile = build_profile(
        "Patient",
        [
            ElementDefinition(
                id="Patient.gender",
                path="Patient.gender",
                max="1",
                type=[ElementDefinitionType(code="code")],
            ),
        ],
    )

    result = generator._flatten_primitive("Patient.gender", profile)

    assert result == {
        "Patient.gender": FlatteningLookupElement(
            view_definition=ViewDefinitionSnippet(
                column=[
                    ViewDefinitionColumn(
                        name="Patient_gender", path="gender", type="code"
                    )
                ]
            ),
        )
    }


def test_flatten_primitive_max_cardinality_star_uses_for_each_and_select(
    generator: FlatteningLookupGenerator,
):
    """
    A repeating primitive (`max = "*"`, read straight off the profile) is wrapped in
    `forEachOrNull` + `select` instead of a plain top-level `column`.
    """
    profile = build_profile(
        "Patient",
        [
            ElementDefinition(
                id="Patient.address",
                path="Patient.address",
                type=[ElementDefinitionType(code="Address")],
            ),
            ElementDefinition(
                id="Patient.address.line",
                path="Patient.address.line",
                max="*",
                type=[ElementDefinitionType(code="string")],
            ),
        ],
    )

    result = generator._flatten_primitive("Patient.address.line", profile)

    assert result["Patient.address.line"].view_definition == ViewDefinitionSnippet(
        for_each_or_null="line",
        select=[
            ViewDefinitionSelect(
                column=[
                    ViewDefinitionColumn(
                        name="Patient_address_line", path="$this", type="string"
                    )
                ]
            )
        ],
    )


def test_flatten_primitive_max_cardinality_multiple_kwarg_for_pseudo_elements(
    generator: FlatteningLookupGenerator,
):
    """
    For a "pseudo" element not defined in the profile, `max_cardinality_multiple` has to
    be passed explicitly (there's no profile element to read `.max` off), and drives the
    same `select`/`forEachOrNull` form as a real repeating element.
    """
    profile = build_profile("Patient", [])

    result = generator._flatten_primitive(
        "Patient.foo", profile, type="string", max_cardinality_multiple=True
    )

    assert result["Patient.foo"].view_definition.for_each_or_null == "foo"
    assert result["Patient.foo"].view_definition.select is not None


def test_flatten_primitive_polymorphic_child_uses_this_as_the_column_path(
    generator: FlatteningLookupGenerator,
):
    """
    A primitive flattened as a polymorphic child (e.g. `value[x]:valueString`) uses
    `$this` as the column path instead of its own last id segment, since it's being
    evaluated against the already-selected value, not a named sub-element of it.
    """
    profile = build_profile(
        "Observation",
        [
            ElementDefinition(
                id="Observation.value[x]",
                path="Observation.value",
                type=[
                    ElementDefinitionType(code="string"),
                    ElementDefinitionType(code="boolean"),
                ],
            ),
            ElementDefinition(
                id="Observation.value[x]:valueString",
                path="Observation.value",
                sliceName="valueString",
                max="1",
                type=[ElementDefinitionType(code="string")],
            ),
        ],
    )

    result = generator._flatten_primitive(
        "Observation.value[x]:valueString", profile, polymorphic_child=True
    )

    assert (
        result["Observation.value[x]:valueString"].view_definition.column[0].path
        == "$this"
    )


def test_flatten_primitive_excluded_type_returns_empty(
    generator: FlatteningLookupGenerator,
):
    generator.config.excluded_types = ["code"]
    profile = build_profile(
        "Patient",
        [
            ElementDefinition(
                id="Patient.gender",
                path="Patient.gender",
                type=[ElementDefinitionType(code="code")],
            ),
        ],
    )

    result = generator._flatten_primitive("Patient.gender", profile)

    assert result == {}


def test_flatten_primitive_supports_pseudo_elements_not_defined_in_the_profile(
    generator: FlatteningLookupGenerator,
):
    """
    An element id that doesn't resolve to anything in the profile can still be flattened,
    as long as an explicit `type` is given - used for elements the flattening logic
    assumes should exist without the profile spelling them out.
    """
    profile = build_profile("Patient", [])

    result = generator._flatten_primitive("Patient.pseudo", profile, type="boolean")

    assert result["Patient.pseudo"].view_definition.column[0].type == "boolean"


# --- _flatten_element (dispatcher) --------------------------------------------------------


def _local_extension_on(base_id: str, base_path: str, slice_name: str) -> list:
    """A self-contained extension slice, attached under `base_id.extension`."""
    ext_id = f"{base_id}.extension:{slice_name}"
    return [
        ElementDefinition(
            id=f"{base_id}.extension",
            path=f"{base_path}.extension",
            type=[ElementDefinitionType(code="Extension")],
            slicing=ElementDefinitionSlicing(rules="open"),
        ),
        ElementDefinition(
            id=ext_id,
            path=f"{base_path}.extension",
            sliceName=slice_name,
            type=[ElementDefinitionType(code="Extension")],
        ),
        ElementDefinition(
            id=f"{ext_id}.url",
            path=f"{base_path}.extension.url",
            fixedUri=f"http://example.org/{slice_name}",
            type=[ElementDefinitionType(code="uri")],
        ),
        ElementDefinition(
            id=f"{ext_id}.value[x]",
            path=f"{base_path}.extension.value",
            type=[ElementDefinitionType(code="string")],
        ),
    ]


def test_flatten_element_explicit_type_overrides_profile_type(
    generator: FlatteningLookupGenerator,
):
    """
    An explicit `type` kwarg wins over whatever the profile itself says the element is -
    used for 'pseudo' elements not defined in the profile.
    """
    profile = build_profile("Patient", [])

    result = generator._flatten_element("Patient.pseudo", profile, type="boolean")

    assert result["Patient.pseudo"].view_definition.column[0].type == "boolean"


def test_flatten_element_excluded_type_returns_empty(
    generator: FlatteningLookupGenerator,
):
    generator.config.excluded_types = ["code"]
    profile = build_profile(
        "Patient",
        [
            ElementDefinition(
                id="Patient.gender",
                path="Patient.gender",
                type=[ElementDefinitionType(code="code")],
            ),
        ],
    )

    result = generator._flatten_element("Patient.gender", profile)

    assert result == {}


def test_flatten_element_root_element_has_no_type_and_returns_empty(
    generator: FlatteningLookupGenerator,
):
    """
    The profile's own root element (id == path == resource type) has no `.type`, so
    `get_element_type` returns `None` for it, and `_flatten_element` treats that the same
    as an excluded type.
    """
    profile = build_profile("Patient", [])

    result = generator._flatten_element("Patient", profile)

    assert result == {}


def test_flatten_element_extension_type_is_a_pure_passthrough_to_flatten_extension(
    generator: FlatteningLookupGenerator,
):
    """
    An Extension-typed element is dispatched straight to `_flatten_extension`, bypassing
    the "attach my own .extension as an extra child" side logic entirely (an extension
    doesn't get a nested extension attached to itself here).
    """
    profile = build_profile(
        "Condition",
        [
            ElementDefinition(
                id="Condition.extension",
                path="Condition.extension",
                type=[ElementDefinitionType(code="Extension")],
                slicing=ElementDefinitionSlicing(rules="open"),
            ),
            ElementDefinition(
                id="Condition.extension:foo",
                path="Condition.extension",
                sliceName="foo",
                type=[ElementDefinitionType(code="Extension")],
            ),
            ElementDefinition(
                id="Condition.extension:foo.url",
                path="Condition.extension.url",
                fixedUri="http://example.org/foo",
                type=[ElementDefinitionType(code="uri")],
            ),
            ElementDefinition(
                id="Condition.extension:foo.value[x]",
                path="Condition.extension.value",
                type=[ElementDefinitionType(code="string")],
            ),
        ],
    )

    via_dispatch = generator._flatten_element("Condition.extension", profile)
    via_direct = generator._flatten_extension("Condition.extension", profile)

    assert via_dispatch == via_direct


def test_flatten_element_attaches_own_extension_as_extra_child(
    generator: FlatteningLookupGenerator,
):
    """
    A complex-typed element (here a BackboneElement) that itself defines an `.extension`
    slice gets that extension flattened and attached as an extra child, alongside its
    normal children.
    """
    profile = build_profile(
        "Observation",
        [
            ElementDefinition(
                id="Observation.referenceRange",
                path="Observation.referenceRange",
                type=[ElementDefinitionType(code="BackboneElement")],
            ),
            ElementDefinition(
                id="Observation.referenceRange.low",
                path="Observation.referenceRange.low",
                type=[ElementDefinitionType(code="Quantity")],
            ),
            *_local_extension_on(
                "Observation.referenceRange", "Observation.referenceRange", "foo"
            ),
        ],
    )

    result = generator._flatten_element("Observation.referenceRange", profile)

    assert set(result["Observation.referenceRange"].children) == {
        "Observation.referenceRange.low",
        "Observation.referenceRange.extension",
    }
    assert "Observation.referenceRange.extension:foo" in result


def test_flatten_element_skips_extension_attachment_for_mixed_primitive_polymorphic_type(
    generator: FlatteningLookupGenerator,
):
    """
    Extensions on primitively-typed elements aren't supported downstream (Pathling
    limitation), so a polymorphic element with at least one primitive among its possible
    types never gets its own `.extension` attached, even if one is defined.
    """
    profile = build_profile(
        "Observation",
        [
            ElementDefinition(
                id="Observation.value[x]",
                path="Observation.value",
                type=[
                    ElementDefinitionType(code="dateTime"),
                    ElementDefinitionType(code="Period"),
                ],
            ),
            *_local_extension_on("Observation.value[x]", "Observation.value", "foo"),
        ],
    )

    result = generator._flatten_element("Observation.value[x]", profile)

    assert not any(".extension" in key for key in result.keys())


# --- aggregated FHIRPath expression reconstruction (integration-style, real profiles) -----
# Unlike everything above, this checks a cross-cutting invariant over a *whole* generated
# lookup (walking `forEachOrNull`/`children` back up to the root should reconstruct a
# sensible full FHIRPath expression) rather than one `_flatten_*` function in isolation, so
# it's kept against real profiles via `profile_lookup` rather than a synthetic one.
# Currently skipped in both cases pending support for extensions on primitively-typed
# elements - ported over unchanged from the old suite, not reworked.


def _construct_child_to_parent_mapping(lookup: FlatteningLookup) -> Mapping[str, str]:
    """
    Helper function to construct a mapping of lookup elements (via their ID) to their parent elements ID
    """
    child_to_parent = dict()
    for elem_id, elem in lookup.elements.items():
        if children := getattr(elem, "children", []):
            for child_id in children:
                child_to_parent[child_id] = elem_id
    return child_to_parent


def _construct_fhirpath_prefix(
    elem_id: str,
    elem: FlatteningLookupElement,
    child_to_parent: Mapping[str, str],
    lookup: FlatteningLookup,
) -> Optional[str]:
    """
    Helper function to construct the aggregated FHIRPath expression prefix from any flattening lookup. The aggregation
    starts at the provided lookup element and ends at its lookup root element. This step only construct the prefix using
    the `forEachOrNull` field values of the lookup elements in the chain
    """
    fhirpath_expr = None
    if parent_id := child_to_parent.get(elem_id):
        fhirpath_expr = _construct_fhirpath_prefix(
            parent_id, lookup.elements[parent_id], child_to_parent, lookup
        )
    if vd := elem.view_definition:
        if foreach_filter := vd.for_each_or_null:
            fhirpath_expr = (
                f"{fhirpath_expr}.{foreach_filter}" if fhirpath_expr else foreach_filter
            )
    # FHIRPath aggregation is expected to replace such redundant expression parts
    return fhirpath_expr.replace(".$this", "") if fhirpath_expr else None


def _construct_fhirpaths(
    elem_id: str,
    elem: FlatteningLookupElement,
    child_to_parent: Mapping[str, str],
    lookup: FlatteningLookup,
) -> list[str]:
    """
    Helper function to construct the aggregated FHIRPath expression from any flattening lookup. The aggregation
    starts at the provided lookup element and ends at its lookup root element. An expression is generated for each view
    definition column and if none is defined then only the aggregated `forEachOrNull` expression is returned
    """
    prefix = _construct_fhirpath_prefix(elem_id, elem, child_to_parent, lookup)
    fhirpath_exprs = list()
    if vd := elem.view_definition:
        if columns := vd.column:
            for c in columns:
                col_path = c.path
                if col_path != "$this":
                    fhirpath_exprs.append(
                        f"{prefix}.{col_path}" if prefix else col_path
                    )
                else:
                    if prefix:
                        fhirpath_exprs.append(prefix)
    if not fhirpath_exprs:
        if prefix:
            fhirpath_exprs.append(prefix)
    return fhirpath_exprs


@pytest.mark.parametrize(
    argnames=["elem_id", "profile_lookup", "expected"],
    argvalues=[
        pytest.param(
            "Patient.identifier:MaskierterVersichertenIdentifer.value.extension:data-absent-reason.value[x]:valueCode",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-person/StructureDefinition/PatientPseudonymisiert",
            [
                "identifier.where(type.coding.system = 'http://fhir.de/sid/gkv/kvid-10').value.extension.where(url = 'http://hl7.org/fhir/StructureDefinition/data-absent-reason').value.ofType(code)"
            ],
            marks=[
                pytest.mark.skip(
                    "ATM extensions on elements that support any primitive FHIR data type are not supported"
                )
            ],
            id="MII_PR_Person_PatientPseudonymisiert.identifier:MaskierterVersichertenIdentifer.value.extension:data-absent-reason.value[x]",
        ),
        pytest.param(
            "Observation.effective[x].extension:QuelleKlinischesBezugsdatum",
            "https://www.medizininformatik-initiative.de/fhir/core/modul-labor/StructureDefinition/ObservationLab",
            [
                "effective.extension.where(url = 'https://www.medizininformatik-initiative.de/fhir/core/modul-labor/StructureDefinition/QuelleKlinischesBezugsdatum')"
            ],
            marks=[
                pytest.mark.skip(
                    "ATM extensions on elements that support any primitive FHIR data type are not supported"
                )
            ],
            id="MII_PR_Labor_Laboruntersuchung.effective[x].extension:QuelleKlinischesBezugsdatum",
        ),
    ],
    indirect=["profile_lookup"],
)
def test_aggregated_fhir_path_expression(
    elem_id: str, profile_lookup: FlatteningLookup, expected
):
    mapping = _construct_child_to_parent_mapping(profile_lookup)
    elem = profile_lookup.elements[elem_id]
    assert _construct_fhirpaths(elem_id, elem, mapping, profile_lookup) == expected
