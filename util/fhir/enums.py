from enum import unique, Enum, EnumMeta

from typing_extensions import Self


class FhirPrimitiveDataTypeMeta(EnumMeta):
    def __contains__(cls, item: str | Self) -> bool:
        try:
            cls(item)
        except ValueError:
            return False
        return True


@unique
class FhirPrimitiveDataType(Enum, metaclass=FhirPrimitiveDataTypeMeta):
    INSTANT = 'instant'
    TIME = 'time'
    DATE = 'date'
    DATE_TIME = 'dateTime'
    BASE_64_BINARY = 'base64Binary'
    DECIMAL = 'decimal'
    BOOLEAN = 'boolean'
    URI = 'uri'
    URL = 'url'
    CANONICAL = 'canonical'
    CODE = 'code'
    STRING = 'string'
    INTEGER = 'integer'
    MARKDOWN = 'markdown'
    ID = 'id'
    OID = 'oid'
    UUID = 'uuid'
    UNSIGNED_INT = 'unsignedInt'
    POSITIVE_INT = 'positiveInt'


class FhirComplexDataTypeEnumMeta(EnumMeta):
    def __contains__(cls, item: str | Self) -> bool:
        try:
            cls(item)
        except ValueError:
            return False
        return True


@unique
class FhirComplexDataType(Enum, metaclass=FhirComplexDataTypeEnumMeta):
    ELEMENT = "Element"
    RATIO = "Ratio"
    PERIOD = "Period"
    RANGE = "Range"
    ATTACHMENT = "Attachment"
    IDENTIFIER = "Identifier"
    ANNOTATION = "Annotation"
    HUMAN_NAME = "HumanName"
    CODEABLE_CONCEPT = "CodeableConcept"
    CONTACT_POINT = "ContactPoint"
    CODING = "Coding"
    MONEY = "Money"
    ADDRESS = "Address"
    BACKBONE_ELEMENT = "BackboneElement"
    TIMING = "Timing"
    DOSAGE = "Dosage"
    ELEMENT_DEFINITION = "ElementDefinition"
    QUANTITY = "Quantity"
    AGE = "Age"
    DISTANCE = "Distance"
    DURATION = "Duration"
    COUNT = "Count"
    MONEY_QUANTITY = "MoneyQuantity"
    SIMPLE_QUANTITY = "SimpleQuantity"
    SAMPLED_DATA = "SampledData"
    SIGNATURE = "Signature"
    CONTRIBUTOR = "Contributor"
    DATA_REQUIREMENT = "DateRequirement"
    RELATED_ARTIFACT = "RelatedArtifact"
    USAGE_CONTEXT = "UsageContext"
    PARAMETER_DEFINITION = "ParameterDefinition"
    EXPRESSION = "Expression"
    TRIGGER_DEFINITION = "TriggerDefinition"
    REFERENCE = "Reference"
    META = "Meta"
    XHTML = "xhtml"
    NARRATIVE = "Narrative"
    EXTENSION = "Extension"


FhirDataType = FhirPrimitiveDataType | FhirComplexDataType


class FhirSearchTypeMeta(EnumMeta):
    def __contains__(cls, item: str | Self) -> bool:
        try:
            cls(item)
        except ValueError:
            return False
        return True


@unique
class FhirSearchType(str, Enum, metaclass=FhirSearchTypeMeta):
    NUMBER = "number"
    DATE = "date"
    STRING = "string"
    TOKEN = "token"
    REFERENCE = "reference"
    COMPOSITE = "composite"
    QUANTITY = "quantity"
    URI = "uri"
