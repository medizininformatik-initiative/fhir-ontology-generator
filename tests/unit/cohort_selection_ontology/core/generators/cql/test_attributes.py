from datetime import datetime

import pytest
from fhir.resources.R4B.coding import Coding
from fhir.resources.R4B.elementdefinition import (
    ElementDefinitionType,
    ElementDefinition,
)
from fhir.resources.R4B.period import Period
from fhir.resources.R4B.quantity import Quantity
from fhir.resources.R4B.reference import Reference
from fhir.resources.R4B.structuredefinition import StructureDefinitionSnapshot

from cohort_selection_ontology.core.generators.cql.attributes import (
    get_components_from_invocation_expression,
    get_components_from_equality_expression,
    ContextGroupDict,
    ReferenceGroupDict,
    AttributeComponentDict,
    get_components_from_and_expression,
    ComponentDict,
    get_components_from_function,
    get_components_from_function_parameters,
    get_components_from_term_expression,
    _get_component_tree,
    _enrich_reference_typed_tree,
    ElementChain,
    _enrich_coding_typed_tree,
    _enrich_quantity_tree,
    _enrich_literal_quantity_tree,
    _enrich_period_tree,
    _enrich_reference_typed_attribute,
    _enrich_coding_typed_attribute,
)
from cohort_selection_ontology.model.mapping import SimpleCardinality
from cohort_selection_ontology.model.mapping.cql import (
    AttributeComponent,
    ContextGroup,
    ReferenceGroup,
)
from common.util.fhir.enums import FhirComplexDataType
from common.util.fhirpath import parse_expr, fhirpathParser
from common.util.project import Project
from common.util.structure_definition.functions import get_element_chain
from common.util.wrapper import dotdict


def get_leaf(
    d: ContextGroupDict | ReferenceGroupDict | AttributeComponentDict,
) -> AttributeComponentDict:
    """
    Retrieves the (assumed to be the only) leaf of a degenerated attribute tree

    :param d: Attribute tree to search
    :return: AttributeComponent dict representing the leaf
    """
    leaf = d
    while leaf._type != AttributeComponent.__name__:
        leaf = leaf.components[0]
    return leaf


def flatten(
    d: ContextGroupDict,
) -> list[ComponentDict]:
    cs = []
    if d.components[0]._type == ContextGroup.__name__:
        cs.extend(flatten(d.components[0]))
    else:
        cs.append(d.components[0])
    cs.append(d.components[1])
    return cs


def test_get_component_from_invocation_expression():
    expr_str = "Resource.element1.element2"
    invoc_expr = parse_expr(expr_str).expression()
    c = get_components_from_invocation_expression(invoc_expr, None)
    assert (
        c._type == AttributeComponent.__name__
    ), "A pure element navigation should return an AttributeComponent dict"
    assert c.path == expr_str, (
        "A pure element navigation should in the components path being equal to the expression"
        "itself"
    )

    invoc_expr = parse_expr(
        "Resource.element1.where(a=1 and b=2).element2"
    ).expression()
    c = get_components_from_invocation_expression(invoc_expr, None)
    assert c.path == "Resource.element1"
    assert next(
        filter(
            lambda x: x.path == "element2" and x._type == AttributeComponent.__name__,
            c.components,
        ),
        None,
    ), (
        "There should be an AttributeComponent dict representing the pure element navigation after the function "
        "invocation"
    )

    invoc_expr = parse_expr("Resource.element1").expression()
    component = dotdict(
        {
            "_type": AttributeComponent.__name__,
            "types": ["Coding"],
            "path": "element2",
            "cardinality": SimpleCardinality.SINGLE,
            "values": [Coding()],
        }
    )
    c = get_components_from_invocation_expression(invoc_expr, component)
    assert c._type == component._type, (
        "if the child component is not 'None' the generated component should "
        "match its type"
    )
    assert c.path == "Resource.element1.element2", (
        "If the child component is not 'None' its path should be "
        "appended to the path of the generated component"
    )


def test_get_components_from_equality_expression():
    expr_str = "Resource.element1 = 'a'"
    eq_expr = parse_expr(expr_str).expression()
    c = get_components_from_equality_expression(eq_expr)
    leaf = get_leaf(c)
    assert leaf.get("values")[0] == eq_expr.getChild(2), (
        "The generated components value should be the right operand of the "
        "equality expression"
    )


def test_get_components_from_and_expression():
    expr_str = "element1.value = 123 and element2.value = 'abc'"
    and_expr = parse_expr(expr_str).expression()
    c = get_components_from_and_expression(and_expr)
    assert (
        c._type == ContextGroup.__name__
    ), "The function should always return a dict representation of a ContextGroup"
    assert len(c.components) == 2, (
        "An and expression with n (2) clauses should result in the generated component "
        "containing n (2) child components"
    )

    for idx in range(3, 50):
        expr_str += f" and component{idx}.value = 123"
        and_expr = parse_expr(expr_str).expression()
        c = get_components_from_and_expression(and_expr)
        assert (
            c._type == ContextGroup.__name__
        ), "The function should always return a dict representation of a ContextGroup"
        assert len(flatten(c)) == idx, (
            f"An and expression with n ({idx}) clauses should result in the generated component "
            f"containing n ({idx}) child components"
        )


def test_get_components_from_function_parameters():
    expr_str = "where()"
    func_expr: fhirpathParser.FunctionContext = (
        parse_expr(expr_str).expression().term().invocation().function()
    )
    param_list_expr = func_expr.paramList()
    params = get_components_from_function_parameters(param_list_expr)
    assert (
        len(params) == 0
    ), "If the function invocation contains no parameters then an empty list should be returned"

    expr_str = "where(a = 1 and b = '2')"
    func_expr: fhirpathParser.FunctionContext = (
        parse_expr(expr_str).expression().term().invocation().function()
    )
    param_list_expr = func_expr.paramList()
    params = get_components_from_function_parameters(param_list_expr)
    assert params == [get_components_from_and_expression(param_list_expr.getChild(0))]

    expr_str = "where(a = 1)"
    func_expr: fhirpathParser.FunctionContext = (
        parse_expr(expr_str).expression().term().invocation().function()
    )
    param_list_expr = func_expr.paramList()
    params = get_components_from_function_parameters(param_list_expr)
    assert params == [
        get_components_from_equality_expression(param_list_expr.getChild(0))
    ]

    expr_str = "where(a.b.exists())"
    func_expr: fhirpathParser.FunctionContext = (
        parse_expr(expr_str).expression().term().invocation().function()
    )
    param_list_expr = func_expr.paramList()
    params = get_components_from_function_parameters(param_list_expr)
    assert params == [
        get_components_from_invocation_expression(param_list_expr.getChild(0))
    ]


def test_get_components_from_function():
    expr_str = "Resource.element1.element2"
    func_expr: fhirpathParser.FunctionContext = parse_expr(expr_str).expression()
    with pytest.raises(ValueError) as exc_info:
        get_components_from_function(func_expr)
    assert "Expected function invocation" in str(
        exc_info.value
    ), "The function should fail if the expression contains no function invocation as its right operand"

    expr_str = "Resource.element1.where()"
    func_expr: fhirpathParser.FunctionContext = parse_expr(expr_str).expression()
    with pytest.raises(ValueError) as exc_info:
        get_components_from_function(func_expr, None)
    assert "Function 'where' should not terminate an expression" in str(
        exc_info.value
    ), (
        "If the where function invocation is the terminal operation, e.g. there is no succeeding subexpression, then the "
        "function should fail since it neither returns a boolean value used in logical formula nor should it be used to "
        "directly select the target element of the attribute since this imply checks on the target elements attributes +"
        "(which should only need to be done in the CQL query and not the navigation to it)"
    )

    expr_str = "Resource.element1.where(a = 1 and b = 2)"
    func_expr: fhirpathParser.FunctionContext = parse_expr(expr_str).expression()
    component = {"_type": ContextGroup.__name__, "path": "element2", "components": []}
    c = get_components_from_function(func_expr, component)
    assert c._type == ContextGroup.__name__, (
        "The generated component dict for a where function invocation should "
        "represent a ContextGroup"
    )
    assert component in c.components, (
        "The component dict representing the succeeding expression should be an entry in "
        "the 'component' attribute"
    )
    assert len(flatten(c)) == 3, (
        "The number of grouped components for a where function invocation should be one larger than the number of "
        "clauses in the parameter (due to the additional component representing the trailing expression)"
    )

    expr_str = "element1.exists()"
    func_expr: fhirpathParser.FunctionContext = parse_expr(expr_str).expression()
    component = {"_type": ContextGroup.__name__, "path": "element2", "components": []}
    with pytest.raises(ValueError) as exc_info:
        get_components_from_function(func_expr, component)
    assert (
        "Function 'exists' returns a boolean value and thus should terminate the expression"
        in str(exc_info.value)
    ), "If the exists function invocation is not a terminal operation than the function should fail"

    expr_str = "Resource.element1.exists(a = 1 and b = 2)"
    func_expr: fhirpathParser.FunctionContext = parse_expr(expr_str).expression()
    c = get_components_from_function(func_expr)
    assert c._type == ContextGroup.__name__, (
        "The generated component dict for an exists function invocation should "
        "represent a ContextGroup"
    )
    assert len(flatten(c)) == 2, (
        "The number of grouped components for an exists function invocation should be equal to the number of clauses "
        "in the parameter"
    )

    expr_str = "element1.ofType()"
    func_expr: fhirpathParser.FunctionContext = parse_expr(expr_str).expression()
    component = {"_type": ContextGroup.__name__, "path": "element2", "components": []}
    with pytest.raises(ValueError) as exc_info:
        get_components_from_function(func_expr, component)
    assert (
        "Function invocation 'ofType' with trailing expression is currently not supported"
        in str(exc_info.value)
    ), "If the ofType function invocation is not a terminal operation than the function should fail"

    expr_str = "Resource.element1.value.ofType(Quantity)"
    func_expr: fhirpathParser.FunctionContext = parse_expr(expr_str).expression()
    c = get_components_from_function(func_expr)
    assert c._type == AttributeComponent.__name__, (
        "The generated component dict for an ofType function invocation should "
        "represent an AttributeComponent"
    )
    assert (
        c.type == "Quantity"
    ), "The type for an ofType function invocation should be specified via its parameter"

    expr_str = "Resource.reference.resolve()"
    func_expr: fhirpathParser.FunctionContext = parse_expr(expr_str).expression()
    c = get_components_from_function(func_expr)
    assert c._type == AttributeComponent.__name__, (
        "The generated component dict for a resolve function invocation without a trailing expression should "
        "represent an AttributeComponent"
    )
    assert (
        c.type == "Reference"
    ), "The type for a resolve function invocation without a trailing expression should be the data type 'Reference'"

    expr_str = "Resource.reference.resolve()"
    func_expr: fhirpathParser.FunctionContext = parse_expr(expr_str).expression()
    component = {"_type": ContextGroup.__name__, "path": "element2", "components": []}
    c = get_components_from_function(func_expr, component)
    # assert c._type == ReferenceGroup.__name__, (
    #    "The generated component dict for a resolve function invocation with a trailing expression should "
    #    "represent a ReferenceGroup"
    # )
    # assert c.components == [component], (
    #    "The generated component dict for a resolve function invocation with a trailing "
    #    "expression should contain the component representing the trailing expression"
    # )
    assert c._type == AttributeComponent.__name__, (
        "The generated component dict for a resolve function invocation with a trailing expression should "
        "represent an AttributeComponent (for now)"
    )
    assert (
        c.type == "Reference"
    ), "The type for a resolve function invocation with a trailing expression should be the data type 'Reference'"
    assert c["values"] == [component]


def test_get_components_from_term_expression():
    expr_str = "element1"
    term_expr = parse_expr(expr_str).expression()
    c = get_components_from_term_expression(term_expr, None)
    assert c._type == AttributeComponent.__name__, (
        "The generated component dict for a term expression without a "
        "trailing expression should represent an AttributeComponent"
    )
    assert c.path == "element1", (
        "The path of the generated component dict for a term expression without a trailing "
        "expression should the element name itself"
    )

    expr_str = "element1"
    term_expr = parse_expr(expr_str).expression()
    component = dotdict(
        {"_type": ContextGroup.__name__, "path": "element2", "components": []}
    )
    c = get_components_from_term_expression(term_expr, component)
    assert c._type == component._type, (
        "The returned component dict for a term expression with a trailing expression "
        "should be the component dict representing the trailing expression"
    )
    assert c.path == "element1.element2", (
        "The path of the returned component dict for a term expression with a "
        "trailing expression should the concatenation of the element itself and the "
        "path of the component representing the trailing expression"
    )


def test_get_component_tree():
    expr_str = "Resource.element1.element2"
    expr = parse_expr(expr_str)
    try:
        _get_component_tree(expr)
    except Exception as exc:
        pytest.fail(
            "Entire expression tree should be parsed without raising an exception", exc
        )

    expr_str = "Resource.element1 = 'abc'"
    component = {"_type": ContextGroup.__name__, "path": "element2", "components": []}
    eq_expr = parse_expr(expr_str).expression()
    with pytest.raises(ValueError) as exc_info:
        _get_component_tree(eq_expr, component)
    assert "Trailing expressions are not supported for boolean expressions" in str(
        exc_info.value
    )


def test__enrich_reference_typed_tree(attribute_test_project: Project):
    edd = ElementDefinition(
        path="Procedure.element2",
        type=[
            ElementDefinitionType(code="Coding"),
            ElementDefinitionType(
                code="Reference",
                targetProfile=[
                    "http://organization.org/fhir/StructureDefinition/procedure1"
                ],
            ),
        ],
    )
    rgd = dotdict(
        _type=ReferenceGroup.__name__,
        type=None,
        path="Condition.element1",
        components=[
            dotdict(
                _type=AttributeComponent.__name__,
                type=None,
                path="element2",
                cardinality=SimpleCardinality.SINGLE,
                values=[],
            )
        ],
    )
    rg = _enrich_reference_typed_tree(rgd, edd, attribute_test_project, "module")
    assert rg.type == "Procedure", "Expected type in this example is 'Procedure'"
    assert (
        rg.path == "Condition.element1"
    ), "The path should be the path to the element of type 'Reference'"
    assert (
        len(rg.components) == 1
    ), "The expected number of contained components in this example is 1"

    ac: AttributeComponent = rg.components[0]
    assert (
        ac.type == "Coding"
    ), "The supported type of the contained component should match the type supported by the referenced target"
    assert ac.path == "Procedure.element2", (
        "The path of the contained component should match the path of the "
        "referenced target element"
    )


def test__enrich_coding_typed_tree(chain: ElementChain):
    # Procedure.element2.where(system = 'abc' and code='123')
    tree = dotdict(
        _type=ContextGroup.__name__,
        path="Procedure.element2",
        components=[
            dotdict(
                _type=AttributeComponent.__name__,
                type=None,
                path="system",
                cardinality=None,
                values=[parse_expr("'abc'").expression()],
            ),
            dotdict(
                _type=AttributeComponent.__name__,
                type=None,
                path="code",
                cardinality=None,
                values=[parse_expr("'123'").expression()],
            ),
        ],
    )
    ac: AttributeComponent = _enrich_coding_typed_tree(tree, chain)
    assert (
        ac.type == FhirComplexDataType.CODING
    ), "The resulting AttributeComponent should support the FHIR data type 'Coding'"
    assert ac.path == "Procedure.element2"
    assert ac.cardinality == SimpleCardinality.MANY
    assert ac.values == [Coding(system="abc", code="123")]


def test__enrich_quantity_typed_tree(chain: ElementChain):
    # Procedure.element2.where(value = 123.45 and unit = 'A^2/B^3' and system = 'http://unitsofmeasure.org' and code='a2/b3')
    tree = dotdict(
        _type=ContextGroup.__name__,
        path="Procedure.element3",
        components=[
            dotdict(
                _type=AttributeComponent.__name__,
                type=None,
                path="value",
                cardinality=None,
                values=[parse_expr("'123.45'").expression()],
            ),
            dotdict(
                _type=AttributeComponent.__name__,
                type=None,
                path="unit",
                cardinality=None,
                values=[parse_expr("'mm[Hg]'").expression()],
            ),
            dotdict(
                _type=AttributeComponent.__name__,
                type=None,
                path="system",
                cardinality=None,
                values=[parse_expr("'http://unitsofmeasure.org'").expression()],
            ),
            dotdict(
                _type=AttributeComponent.__name__,
                types=[],
                path="code",
                cardinality=None,
                values=[parse_expr("'mm[Hg]'").expression()],
            ),
        ],
    )
    ac: AttributeComponent = _enrich_quantity_tree(tree, chain)
    assert (
        ac.type == FhirComplexDataType.QUANTITY
    ), "The resulting AttributeComponent should support the FHIR data type 'Quantity'"
    assert ac.path == "Procedure.element3"
    assert ac.cardinality == SimpleCardinality.MANY
    assert ac.values == [
        Quantity(
            value="123.45",
            unit="mm[Hg]",
            system="http://unitsofmeasure.org",
            code="mm[Hg]",
        )
    ]


def test__enrich_literal_quantity_tree(chain: ElementChain):
    # Procedure.element2 = 123.45 'mm[Hg]'
    tree = dotdict(
        _type=AttributeComponent.__name__,
        type=None,
        path="Procedure.element3",
        cardinality=None,
        values=[parse_expr("123.45 'mm[Hg]'").expression().term()],
    )
    ac: AttributeComponent = _enrich_literal_quantity_tree(tree, chain)
    assert (
        ac.type == FhirComplexDataType.QUANTITY
    ), "The resulting AttributeComponent should support the FHIR data type 'Quantity'"
    assert ac.path == "Procedure.element3"
    assert ac.cardinality == SimpleCardinality.MANY
    assert ac.values == [
        Quantity(
            value="123.45",
            system="http://unitsofmeasure.org",
            code="mm[Hg]",
        )
    ]


def test__enrich_period_tree(chain: ElementChain):
    # Procedure.element4.where(start = @1970-01-01 and end = @2025-12-31)
    tree = dotdict(
        _type=ContextGroup.__name__,
        path="Procedure.element4",
        components=[
            dotdict(
                _type=AttributeComponent.__name__,
                type=None,
                path="start",
                cardinality=None,
                values=[parse_expr("'@1970-01-01'").expression()],
            ),
            dotdict(
                _type=AttributeComponent.__name__,
                type=None,
                path="end",
                cardinality=None,
                values=[parse_expr("'@2025-12-31'").expression()],
            ),
        ],
    )
    ac: AttributeComponent = _enrich_period_tree(tree, chain)
    assert (
        ac.type == FhirComplexDataType.PERIOD
    ), "The resulting AttributeComponent should support the FHIR data type 'Period'"
    assert ac.path == "Procedure.element4"
    assert ac.cardinality == SimpleCardinality.MANY
    assert ac.values == [
        Period(
            start=datetime.fromisoformat("1970-01-01"),
            end=datetime.fromisoformat("2025-12-31"),
        )
    ]


def test__enrich_reference_typed_attribute(
    root_snapshot: StructureDefinitionSnapshot, attribute_test_project: Project
):
    tree = dotdict(
        _type=AttributeComponent.__name__,
        type=None,
        path="Condition.extension:slice1.value[x]",
        cardinality=None,
        values=[],
    )
    chain = get_element_chain(
        "Condition.extension:slice1.value[x]",
        root_snapshot,
        "module",
        attribute_test_project,
    )
    modules_dir_path = attribute_test_project.input.cso / "modules"
    ac: AttributeComponent = _enrich_reference_typed_attribute(
        tree, chain, modules_dir_path
    )
    assert (
        ac.type == FhirComplexDataType.REFERENCE
    ), "The resulting AttributeComponent should support the FHIR data type 'Reference'"
    assert ac.path == "Condition.extension:slice1.value[x]"
    assert ac.cardinality == SimpleCardinality.MANY
    assert ac.values == [Reference(type="Procedure")]


def test__enrich_coding_typed_attribute(chain: ElementChain):
    ac: AttributeComponent = _enrich_coding_typed_attribute(chain)
    assert (
        ac.type == FhirComplexDataType.CODING
    ), "The resulting AttributeComponent should support the FHIR data type 'Coding'"
    assert ac.path == "Procedure.element2"
    assert ac.cardinality == SimpleCardinality.MANY
