import abc
import enum
from enum import StrEnum
from xml.etree.ElementTree import XML
from importlib.resources import files


def __load_elm_fhir_modelinfo() -> list[str]:
    import cohort_selection_ontology.resources.cql

    elm = (
        files(cohort_selection_ontology.resources.cql)
        .joinpath("elm-modelinfo.xml")
        .read_text(encoding="utf-8")
    )
    ns = {"elm": "urn:hl7-org:elm-modelinfo:r1"}
    return [
        type_info.attrib["name"]
        for type_info in XML(elm).findall("elm:typeInfo", ns)
        if type_info.attrib["baseType"] == "FHIR.DomainResource"
    ]


RetrievableType = enum.Enum(
    value="RetrievableType",
    type=str,
    names=((x, x) for x in __load_elm_fhir_modelinfo()),
)
