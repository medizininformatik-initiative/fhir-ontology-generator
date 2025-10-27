import unittest

from fhir.resources.R4B.coding import Coding
from fhir.resources.R4B.reference import Reference

from cohort_selection_ontology.model.mapping import SimpleCardinality
from cohort_selection_ontology.model.mapping.cql import (
    AttributeComponent,
    ContextGroup,
)


class ContextGroupTest(unittest.TestCase):
    @classmethod
    def test_model_construct(cls):
        valid_ac = AttributeComponent(
            type="Coding",
            path="code.coding",
            cardinality=SimpleCardinality.MANY,
            values=[Coding()],
        )
        valid_cg = ContextGroup(
            path="extension",
            components=[
                AttributeComponent(
                    type="Reference",
                    path="value",
                    cardinality=SimpleCardinality.SINGLE,
                    values=[Reference()],
                )
            ],
        )

        values = {
            "path": "Resource",
            "components": [
                ContextGroup.model_construct(path=None, components=[valid_ac]),
                ContextGroup(path="", components=[valid_ac]),
                ContextGroup(path="$this", components=[valid_ac]),
                valid_cg,
            ],
        }
        cg = ContextGroup.model_construct(**values)
        assert cg.components == [valid_ac, valid_ac, valid_ac, valid_cg], (
            "Nested ContextGroup components should be removed if their "
            "path does not does navigate to a different element than that of its parent"
        )
