# FHIR Searchontology Generator

## Requirements

Python 3.8 or higher \
Firely Terminal available at https://simplifier.net/downloads/firely-terminal v3.1.0 or higher  \
Access to a terminology server with all value sets used in the FHIR profiles

## Configuration

| Var | Description | Example |
|--------|-------------|---------|
|ONTOLOGY_SERVER_ADDRESS | Address of the Ontology server fhir api| my_onto_server.com/fhir

## About

This project generates a search ontology based on FHIR Profiles for the
project https://github.com/medizininformatik-initiative/feasibility-deploy. Within a FHIR Profile all elements are
identified that can be used as criteria. Each criterion consists of a defining TermCode and can be further specified
using valueFilters, attributeFilters and timeRestrictions. TermCodes are equivalent to FHIR CodeableConcepts and
originate from a Terminology. I.e. the criterion "body height" is defined by the TermCode "8302-2" from the
Terminology "LOINC". In case of the body height the criterion is a quantity and can be further specified by a
valueFilter. The valueFilter defines the unit of the quantity, for our example "cm". If the filter is not directly
related to the TermCode, it is an attributeFilter. I.E. the status of the body height observation is not directly
related to the concept defined by the TermCode. Therefore, it is an attributeFilter. The timeRestriction can be regarded
as attributeFilter which is always related to the clinical time of the criterion.

With the defined metadata of a criterion, we can identify FHIR elements within a FHIR Profile that provide the possible
values for the termCode, valueFilter, attributeFilter and timeRestriction.

I.e in the FHIR Profile Observation we can find the following elements that are of interest for the criterion:

```json
[
  {
    "id": "Observation.code.coding:loinc",
    "path": "Observation.code.coding",
    "sliceName": "loinc",
    "min": 1,
    "max": "*",
    "patternCoding": {
      "system": "http://loinc.org",
      "code": "8302-2"
    }
  },
  {
    "id": "Observation.value[x]",
    "path": "Observation.value[x]",
    "slicing": {
      "discriminator": [
        {
          "type": "type",
          "path": "$this"
        }
      ],
      "ordered": false,
      "rules": "open"
    },
    "type": [
      {
        "code": "Quantity"
      }
    ],
    "mustSupport": true
  },
  {
    "id": "Observation.valueQuantity.code",
    "path": "Observation.valueQuantity.code",
    "min": 1,
    "mustSupport": true,
    "binding": {
      "strength": "required",
      "valueSet": "http://hl7.org/fhir/ValueSet/ucum-bodylength|4.0.0"
    }
  }
]
```

To specify a criterion we need to identify all elements and their path that relate to the criteria. In the example above
we can see that the criterion "body height" is defined by the element "Observation.code.coding:loinc" and the value is
defined by the element Observation.value[x] and the element Observation.valueQuantity.code. As all quantity values might
have a unit it is sufficient to identify the element Observation.value[x], the unit is automatically resolved.

```json
{
  "name": "ObservationValueQuantity",
  "resource_type": "Observation",
  "context": {
    "system": "fdpg.mii.gecco",
    "code": "QuantityObservation",
    "display": "QuantityObservation"
  },
  "term_code_defining_id": "Observation.code.coding:loinc",
  "value_defining_id": "Observation.value[x]:valueQuantity",
  "time_restriction_defining_id": "Observation.effective[x]"
}
```

Above you can see the full QueryingMetaData for the criterion "body height". As a matter of fact, the same
QueryingMetaData can be used for all FHIR Profiles that define a quantity observation with a termCode at"
"Observation.code.coding:loinc" and a value at "Observation.value[x]:valueQuantity"

After successfully resolving all QueryingMetaData for all criteria, we can generate a search ontology. The search
ontology consists of a mono hierarchy of all criteria, based on their relation to each other in their ontology. We refer
to this hierarchy as ui-tree. The ui-tree only contains the termCodes of the criteria, the information on how to further
specify the criteria is stored normalized in ui-profiles. I.e. the ui-profile for the criterion "body height" looks like
this:

```json
{
  "name": "BodyHeight",
  "timeRestrictionAllowed": true,
  "valueDefinitions": {
    "allowedUnits": [
      {
        "code": "cm",
        "display": "centimeter",
        "system": "http://unitsofmeasure.org"
      },
      {
        "code": "[in_i]",
        "display": "inch (international)",
        "system": "http://unitsofmeasure.org"
      }
    ],
    "precision": 1,
    "type": "quantity"
  }
}
```

Which allows the user to select a criterion "body height" and further specify the value using comparators and the here
defined units.

Beside the ui-tree and ui-profiles we also generate a fhir search mapping and a cql mapping. Based on the termCode the
fhir search parameter and the fhir path are identified for the termCode, the valueFilter and each attributeFilter.

CQL Mapping generated for Body Height Profile and the provided QueryingMetaData:

```json
{
  "name": "QuantityObservation",
  "resource_type": "Observation",
  "termCodeFhirPath": "code.coding",
  "termValueFhirPath": "value",
  "timeRestrictionPath": "effective"
}
```

FHIR Search Mapping generated for Body Height Profile and the provided QueryingMetaData:

```json
{
  "name": "QuantityObservation",
  "resource_type": "Observation",
  "termCodeSearchParameter": "code",
  "timeRestrictionParameter": "date",
  "valueSearchParameter": "value-quantity",
  "valueType": "quantity"
}
```

