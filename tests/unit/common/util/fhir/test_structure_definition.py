from fhir.resources.R4B.elementdefinition import ElementDefinitionType

from common.util.fhir.structure_definition import get_types_supported_by_element


def test_get_types_supported_by_element():
    element_definition = {
        "id": "Specimen.collection.collected[x]",
        "path": "Specimen.collection.collected[x]",
        "type": [{"code": "dateTime"}, {"code": "Period"}],
    }
    types = get_types_supported_by_element(element_definition)
    assert len(types) == 2
    assert ElementDefinitionType(code="dateTime") in types
    assert ElementDefinitionType(code="Period") in types
