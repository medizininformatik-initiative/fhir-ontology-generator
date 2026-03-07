# Flattening Lookup Table Generation

## Usage
```bash
python scripts/generate_lookup.py -p fdpg-ontology
```

## Currently supported:
1. Primitives:
   - ``boolean``, ``string``, ``code``, ``decimal``, ``integer``, ``integer64``, ``unsignedInt``, ``positiveInt``, ``uri``, ``canonical``, ``url``, ``markdown``, ``xhtml``, ``date``, ``dateTime``, ``instant``, ``time`` 
2. Complex:
   - ``Coding``, ``CodeableConcept``, `Period`, `Ratio`, `Range`, `Quantity`, ``References``, ``BackboneElements``
3. Extensions: yes
   - Supports extensions defined in separate profile
   - Supports extensions with extensions
4. Polymorphic elements: yes, but only the types mentioned above
5. Excluded by design: ``id``, `modifierExtension`

## How to work with a lookup file
The lookup file contains instructions on how each element has to be flattened 
and can be used to generate viewDefinition files for a selection of elements of a Profile.

When generating a ViewDefinition from a lookup file, the following rules need to be adhered to:
1. The element of interest must be inserted into the ``parent.viewDefinition.select`` array of its parent
   - any siblings of the element of interest do not need to be inserted
   - if the ``parent`` attribute is not set, the element needs to be inserted into 
   the select array on the first level in the viewDefinition
2. If the element of interest has a ``.children`` array defined, all ids contained in said array must be
   flattened as well

_Recommended_: _Include elements `subject.reference` (only if part of [patient compartment](https://hl7.org/fhir/R4/compartmentdefinition-patient.html)) 
and `id` by default to later be able to identify patients in your data._

Tools that implement generation of viewDefintions from lookup files:
- [Aether](https://medizininformatik-initiative.github.io/aether/)

## Lookup file format:
Json-encoded array of lookups of each profile.
A lookup for a profile should look like this:
- ``url``: url of the profile which this lookup corresponds to. 
  Used to match lookups, instance data and feature selection
- ``resourceType``: the resource type of the Profile. (``Medication``, ``Observation``, etc.)
- ``elements``: a dictionary holding the flattening instructions indexed by the element ids contained in the Profile
  - Each lookup element should contain at minimum the ``.viewDefinition`` attribute:
    - ``.parent``: id of parent element. Used for the insertion as described [here](#how-to-work-with-a-lookup-file)
      - if missing => parent is implicitly pointing to root should be included in root select array
    - ``.viewDefinition`` viewDefinition snippet to use for this lookup element.
      - For possible content, see how the different types are handled [here](#implementation-details)
    - ``.children``: array of children ids. Also used for insertion as described [here](#how-to-work-with-a-lookup-file)
      - if missing, no supported children could be found 

## Implementation details:
As the lookup file contains flattening instructions for all supported elements, 
each possible element type needs a way to be flattened. For this it does make 
sense to think about where within or beneath each type the actual values are stored, 
when looking at the instance data.
### 1. Primitive types
Since primitive types in most cases are the elements which actually contain the values,
these can be flattened directly. Thus, the viewDefinition snippet contains the actual column and path.

For example: For this pritive-typed element ``Condition.recordedDate`` the following 
lookup elements would be generated:
```json
  "Condition.recordedDate": {
    "viewDefinition": {
      "column": [
        {
          "name": "Condition_recordedDate",
          "path": "recordedDate",
          "type": "dateTime"
        }
      ]
    }
  },
``` 
_Note: No ``.parent`` is defined because the parent is the root of the resource. 
No `.children` array is defined because primitive elements do not have children._

A viewDefinition containing only this element would look like this
```json
{
  "resourceType": "https://sql-on-fhir.org/ig/StructureDefinition/ViewDefinition",
  "name": "Diagnosen",
  "status": "draft",
  "resource": "Condition",
  "select": [
    {
      "column": [
        {
          "name": "id",
          "path": "id"                        <<<< // added by default 
        },
        {
          "name": "patient",
          "path": "subject.reference"         <<<< // added by default 
        }
      ]
    },
    {
      "column": [
        {
          "name": "Condition_recordedDate",
          "path": "recordedDate",             <<<< // selected through crtdl 
          "type": "dateTime"                   
        }
      ]
    }
  ]
}
```
Below is a table with example output:

| id                      | patient                       | Condition_recordedDate    |
|-------------------------|-------------------------------|---------------------------|
| mii-condition-example-1 | Patient/mii-patient-example-1 | 2024-01-15T10:30:00+01:00 |
| mii-condition-example-2 | Patient/mii-patient-example-2 | 2022-01-10T17:29:00+03:00 |

### 2. Generic complex

Complex elements are structures, which do not hold any information themselves, but rather rely on 
their primitive child elements which hold the actual values. Thus, complex elements can't be flattened directly.
This element's children are enumerated in the ``.children`` attribute. 

- _Generic_ complex elements which can all be flattened the same. Examples: ``Ratio``, ``Period``, ``Quantity``, etc.
- _Non-Generic_ complex element types need to be flattened in a for each specifically defined way. 
    This applies to the following types: ``Coding``, `CodeableConcept`, `Extension`, `Reference`, `Polymorphic`

The viewDefinition also changed, now containing ``forEachOrNull`` and `select`:
1. ``forEachOrNull`` this needs to be used for every element to deal with cardinality implicitly
2. ``select``: corresponds to the select in the viewDefinition into which the children viewDefinition snippets are later
    inserted

Some complex types do need specific child elements without which flattening is meaningless. For example, 
the type ``Period`` in the example below needs ``.start``, ``.end``. These elements are included in the output lookup,
even if they are not explicitly defined in the profile.

Example flattening a generic complex type: 
- For an element of type ``Period`` which is composed of two ``datetime`` (``.start``, ``.end``) elements,
the lookup is: 

````json
{
  "Condition.onset[x]:onsetPeriod.start": {
    "parent": "Condition.onset[x]:onsetPeriod",
    "viewDefinition": {
      "column": [
        {
          "name": "Condition_onset_X_Onsetperiod_start",
          "path": "start",
          "type": "dateTime"
        }
      ]
    }
  },

  "Condition.onset[x]:onsetPeriod.end": {
    "parent": "Condition.onset[x]:onsetPeriod",
    "viewDefinition": {
      "column": [
        {
          "name": "Condition_onset_X_Onsetperiod_end",
          "path": "end",
          "type": "dateTime"
        }
      ]
    }
  },
  "Condition.onset[x]:onsetPeriod": {
    "parent": "Condition.onset[x]",
    "viewDefinition": {
      "forEachOrNull": "onset.ofType(Period)",
      "select": []
    },
    "children": [
      "Condition.onset[x]:onsetPeriod.start",
      "Condition.onset[x]:onsetPeriod.end"
    ]
  }
}
````

_Note 1: in the example above the actual ``Period`` element 
is one of the types of the polymorphic element: ``Condition.onset[x]``. 
Handling of polymorphic elements will be described later._

_Note 2: in the example lookup the actual ``Period`` element has its children enumerated 
in the ``.children`` attribute_


This lookup and with only ``Condition.onset[x]:onsetPeriod`` selected, should result in this viewDefinition:
````json
{
  "resourceType": "https://sql-on-fhir.org/ig/StructureDefinition/ViewDefinition",
  "name": "Diagnosen",
  "status": "draft",
  "resource": "Condition",
  "select": [
    {
      "column": [
        {
          "name": "id",
          "path": "id"                        <<<< // added by default 
        },
        {
          "name": "patient",        
          "path": "subject.reference"         <<<< // added by default 
        }
      ]
    },
    {
      "select": [
        {
          "column": [
            {
              "name": "Condition_onset_X_Onsetperiod_start",
              "path": "start",
              "type": "dateTime"
            }
          ]
        },
        {
          "column": [
            {
              "name": "Condition_onset_X_Onsetperiod_end",
              "path": "end",
              "type": "dateTime"
            }
          ]
        }
      ],
      "forEachOrNull": "onset.ofType(Period)"              <<<< // specific to polymorphic elements (explained later)
    }
  ]
}
````
Producing the following example output:

| id                       | patient                       | Condition_onset_X_Onsetperiod_start  | Condition_onset_X_Onsetperiod_end  |
|--------------------------|-------------------------------|--------------------------------------|------------------------------------|
| mii-condition-example-4  | Patient/mii-patient-example-4 | 2020-01-01T00:00:00+01:00            | 2024-01-01T00:00:00+01:00          |


### 3. Complex - Codings and CodeableConcepts
``CodeableConcepts`` contain an element of type ``Coding`` which is often sliced. 
For each slice and when no slice is defined these columns are created: (`el_code`,`el_system`). See example below.

Example flattening for CodeableConcepts and Codings:
- Each CodeableConcept has a corresponding ``.coding`` element, even if not explicitly defined
- Each Coding(defined or not) will be split up by slices if any present.

Example lookup for ``Condition.code`` CodeableConcept
```json

{
  "Condition.code": {                               <<<< // lookup for CodeableConcept
    "viewDefinition": {
      "forEachOrNull": "code",
      "select": []
    },
    "children": [                                   <<<< // refering to slices
      "Condition.code.coding:icd10-gm",           
      "Condition.code.coding:alpha-id",
      "Condition.code.coding:sct",
      "Condition.code.coding:orphanet"
    ]
  },
  "Condition.code.coding:icd10-gm.system": {
    "parent": "Condition.code.coding:icd10-gm",
    "viewDefinition": {
      "column": [
        {
          "name": "Condition_code_codingIcd10gm_system",
          "path": "system",
          "type": "uri"
        }
      ]
    }
  },
  "Condition.code.coding:icd10-gm.code": {
    "parent": "Condition.code.coding:icd10-gm",
    "viewDefinition": {
      "column": [
        {
          "name": "Condition_code_codingIcd10gm_code",
          "path": "code",
          "type": "code"
        }
      ]
    }
  },
  "Condition.code.coding:icd10-gm": {                                                              <<<< // lookup for the Coding
    "parent": "Condition.code",
    "viewDefinition": {
      "forEachOrNull": "coding.where(system = 'http://fhir.de/CodeSystem/bfarm/icd-10-gm')",       <<<< // select slice
      "select": []
    },
    "children": [                                                      <<<< // for each slice create system and code columns
      "Condition.code.coding:icd10-gm.system",
      "Condition.code.coding:icd10-gm.code"
    ]
  },
  "Condition.code.coding:alpha-id.system": {
    "parent": "Condition.code.coding:alpha-id",
    "viewDefinition": {
      "column": [
        {
          "name": "Condition_code_codingAlphaid_system",
          "path": "system",
          "type": "uri"
        }
      ]
    }
  },
  "Condition.code.coding:alpha-id.code": {
    "parent": "Condition.code.coding:alpha-id",
    "viewDefinition": {
      "column": [
        {
          "name": "Condition_code_codingAlphaid_code",
          "path": "code",
          "type": "code"
        }
      ]
    }
  },
  "Condition.code.coding:alpha-id": {
    "parent": "Condition.code",
    "viewDefinition": {
      "forEachOrNull": "coding.where(system = 'http://fhir.de/CodeSystem/bfarm/alpha-id')",
      "select": []
    },
    "children": [
      "Condition.code.coding:alpha-id.system",
      "Condition.code.coding:alpha-id.code"
    ]
  },
  
```

_Note 1: ``Extensions`` are not considered in this example, but will be discussed [later](#5-extensions)._

_Note 2: Only ``icd10-gm`` and ``alpha-id`` are considered in this example for simplicity_

Resulting viewDefinition:
````json
{
  "resourceType": "https://sql-on-fhir.org/ig/StructureDefinition/ViewDefinition",
  "name": "Diagnosen",
  "status": "draft",
  "resource": "Condition",
  "select": [
    {
      "column": [
        {
          "name": "id",
          "path": "id"                        <<<< // added by default 
        },
        {
          "name": "patient",        
          "path": "subject.reference"         <<<< // added by default 
        }
      ]
    },
    {
      "select": [
        {
          "select": [
            {
              "column": [
                {
                  "name": "Condition_code_codingIcd10gm_system",
                  "path": "system",
                  "type": "uri"
                }
              ]
            },
            {
              "column": [
                {
                  "name": "Condition_code_codingIcd10gm_code",
                  "path": "code",
                  "type": "code"
                }
              ]
            }
          ],
          "forEachOrNull": "coding.where(system = 'http://fhir.de/CodeSystem/bfarm/icd-10-gm')"
        },
        {
          "select": [
            {
              "column": [
                {
                  "name": "Condition_code_codingAlphaid_system",
                  "path": "system",
                  "type": "uri"
                }
              ]
            },
            {
              "column": [
                {
                  "name": "Condition_code_codingAlphaid_code",
                  "path": "code",
                  "type": "code"
                }
              ]
            }
          ],
          "forEachOrNull": "coding.where(system = 'http://fhir.de/CodeSystem/bfarm/alpha-id')"
        }        
      ],
      "forEachOrNull": "code"
    }
  ]
}
````

Producing the following example output:

| id        | patient          | Condition_code_codingIcd10gm_system       | Condition_code_codingIcd10gm_code | Condition_code_codingAlphaid_system      | Condition_code_codingAlphaid_code |
|-----------|------------------|-------------------------------------------|-----------------------------------|------------------------------------------|-----------------------------------|
| cond-ex1  | Patient/pat-ex1  | http://fhir.de/CodeSystem/bfarm/icd-10-gm | I50.01                            |                                          |                                   |
| cond-ex1  | Patient/pat-ex1  | http://fhir.de/CodeSystem/bfarm/icd-10-gm | I50-zweite-diag-code-icd10        |                                          |                                   |
| cond-ex2  | Patient/pat-ex2  | http://fhir.de/CodeSystem/bfarm/icd-10-gm | E11.90                            |                                          |                                   |
| cond-ex3  | Patient/pat-ex3  | http://fhir.de/CodeSystem/bfarm/icd-10-gm | J45.90                            |                                          |                                   |
| cond-ex4  | Patient/pat-ex4  | http://fhir.de/CodeSystem/bfarm/icd-10-gm | C34.10                            |                                          |                                   |
| cond-ex5  | Patient/pat-ex5  | http://fhir.de/CodeSystem/bfarm/icd-10-gm | F32.9                             |                                          |                                   |
| cond-ex6  | Patient/pat-ex6  |                                           |                                   | http://fhir.de/CodeSystem/bfarm/alpha-id | I109999                           |
| cond-ex7  | Patient/pat-ex7  |                                           |                                   | http://fhir.de/CodeSystem/bfarm/alpha-id | A123456                           |
| cond-ex8  | Patient/pat-ex8  | http://fhir.de/CodeSystem/bfarm/icd-10-gm | M54.5                             | http://fhir.de/CodeSystem/bfarm/alpha-id | B654321                           |
| cond-ex9  | Patient/pat-ex9  |                                           |                                   | http://fhir.de/CodeSystem/bfarm/alpha-id | C777888                           |
| cond-ex10 | Patient/pat-ex10 | http://fhir.de/CodeSystem/bfarm/icd-10-gm | K21.9                             | http://fhir.de/CodeSystem/bfarm/alpha-id | D112233                           |
| cond-ex11 | Patient/pat-ex11 | http://fhir.de/CodeSystem/bfarm/icd-10-gm | I10                               | http://fhir.de/CodeSystem/bfarm/alpha-id | A111111                           |
| cond-ex11 | Patient/pat-ex11 | http://fhir.de/CodeSystem/bfarm/icd-10-gm | E78.5                             | http://fhir.de/CodeSystem/bfarm/alpha-id | A111111                           |
| cond-ex11 | Patient/pat-ex11 | http://fhir.de/CodeSystem/bfarm/icd-10-gm | I10                               | http://fhir.de/CodeSystem/bfarm/alpha-id | B222222                           |
| cond-ex11 | Patient/pat-ex11 | http://fhir.de/CodeSystem/bfarm/icd-10-gm | E78.5                             | http://fhir.de/CodeSystem/bfarm/alpha-id | B222222                           |
Couple notes:
- Note that ``Condition`` with id ``cond-ex1`` appears two times. This is because of the usage of ``forEachOrNull``, 
    which creates a row for each entry it finds for a given column. 
    Thus, for the two codes found for ``Condition_code_codingIcd10gm_code`` two rows will be produced, even if this 
    might be an unrealistic example.
- Note that for ``Conditions`` with ids 8 and 10 the columns for both codesystem are populated. This means that the
    testdata contained codes across multiple slices. In case of ``Condition.code`` these codes should have the same 
    meaning.
- Note that for the ``Condition`` with id `cond-ex11` four columns were created and that the codes repeat.
    This is because of the ``forEachOrNull`, which creates all possible combinations with the values nested below itself


### 4. Polymorphic
Polymorphic elements are elements which can have one of many different types, defined by the structure definition of 
the profile of the given element. 
When flattening, each possible type defined by the element needs to be considered and flattened accordingly. 

The polymorphic element itself contains no information itself. Similar to the complex types its information is hold
by its possible types. 


````json
{
  "Condition.onset[x]": {                      <<<< // polymorphic element
    "viewDefinition": {
      "select": []
    },
    "children": [                              <<<< // 2 possible types found in structure definition
      "Condition.onset[x]:onsetDateTime",            
      "Condition.onset[x]:onsetPeriod"
    ]
  },
  "Condition.onset[x]:onsetDateTime": {                    <<<< // datetime: possible type, primitive
    "parent": "Condition.onset[x]",
    "viewDefinition": {
      "forEachOrNull": "onset.ofType(dateTime)",           <<<< // distinguished by the .ofType() function
      "select": [
        {
          "column": [
            {
              "name": "Condition_onset_X_Onsetdatetime",
              "path": "$this",
              "type": "dateTime"
            }
          ]
        }
      ]
    }
  },
  "Condition.onset[x]:onsetPeriod": {                      <<<< // Period: possible type, generic complex
    "parent": "Condition.onset[x]",
    "viewDefinition": {
      "forEachOrNull": "onset.ofType(Period)",             <<<< // distinguished by the .ofType() function
      "select": []
    },
    "children": [
      "Condition.onset[x]:onsetPeriod.start",
      "Condition.onset[x]:onsetPeriod.end"
    ]
  },
  "Condition.onset[x]:onsetPeriod.start": {
    "parent": "Condition.onset[x]:onsetPeriod",
    "viewDefinition": {
      "column": [
        {
          "name": "Condition_onset_X_Onsetperiod_start",
          "path": "start",
          "type": "dateTime"
        }
      ]
    }
  },
  "Condition.onset[x]:onsetPeriod.end": {
    "parent": "Condition.onset[x]:onsetPeriod",
    "viewDefinition": {
      "column": [
        {
          "name": "Condition_onset_X_Onsetperiod_end",
          "path": "end",
          "type": "dateTime"
        }
      ]
    }
  }
}
````

A generated viewDefinition could look like this:
````json
{
  "resourceType": "https://sql-on-fhir.org/ig/StructureDefinition/ViewDefinition",
  "name": "Diagnosen",
  "status": "draft",
  "resource": "Condition",
  "select": [
    {
      "column": [
        {
          "name": "id",
          "path": "id"                        <<<< // added by default 
        },
        {
          "name": "patient",        
          "path": "subject.reference"         <<<< // added by default 
        }
      ]
    },
    {
      "select": [
        {
          "column": [
            {
              "name": "Condition_onset_X_Onsetdatetime",
              "path": "$this",
              "type": "dateTime"
            }
          ]
        }
      ],
      "forEachOrNull": "onset.ofType(dateTime)"                 <<<< // distinguished by the .ofType() function
    },
    {
      "select": [
        {
          "column": [
            {
              "name": "Condition_onset_X_Onsetperiod_start",
              "path": "start",
              "type": "dateTime"
            }
          ]
        },
        {
          "column": [
            {
              "name": "Condition_onset_X_Onsetperiod_end",
              "path": "end",
              "type": "dateTime"
            }
          ]
        }
      ],
      "forEachOrNull": "onset.ofType(Period)"                   <<<< // distinguished by the .ofType() function
    }
  ]
}
````
_Note: Each type is distinguished by the ``.ofType()`` function. Example: ``onset.ofType(Period)``_

Possible output table with example data:

| id         | patient            | Condition_onset_X_Onsetdatetime | Condition_onset_X_Onsetperiod_start | Condition_onset_X_Onsetperiod_end |
|------------|--------------------|---------------------------------|-------------------------------------|-----------------------------------|
| cond-ex1   | Patient/pat-ex1    |                                 |                                     |                                   |
| cond-ex2   | Patient/pat-ex2    |                                 | 2023-05-01T00:00:00+01:00           | 2023-12-31T00:00:00+01:00         |
| cond-ex3   | Patient/pat-ex3    |                                 | 2022-03-15T00:00:00+01:00           |                                   |
| cond-ex4   | Patient/pat-ex4    |                                 | 2020-01-01T00:00:00+01:00           | 2024-01-01T00:00:00+01:00         |
| cond-ex5   | Patient/pat-ex5    |                                 |                                     |                                   |
| cond-ex6   | Patient/pat-ex6    |                                 |                                     |                                   |
| cond-ex7   | Patient/pat-ex7    |                                 | 2021-06-01T00:00:00+01:00           |                                   |
| cond-ex8   | Patient/pat-ex8    |                                 | 2023-01-10T00:00:00+01:00           | 2023-02-20T00:00:00+01:00         |
| cond-ex9   | Patient/pat-ex9    |                                 |                                     |                                   |
| cond-ex10  | Patient/pat-ex10   |                                 | 2022-11-05T00:00:00+01:00           |                                   |
| cond-ex11  | Patient/pat-ex11   |                                 |                                     |                                   |
| cond-ex12  | Patient/pat-ex12   | 2023-09-10T08:30:00+01:00       |                                     |                                   |
| cond-ex13  | Patient/pat-ex13   | 2024-01-05T14:20:00+01:00       |                                     |                                   |
| cond-ex14  | Patient/pat-ex14   | 2023-03-15T07:45:00+01:00       |                                     |                                   |
| cond-ex15  | Patient/pat-ex15   | 2024-02-10T18:00:00+01:00       |                                     |                                   |

_Note 1: Extensions are ignored because they will be discussed [later](#5-extensions)_

_Note 2: ``Condition.onset[x]:onsetAge`` is missing, even though is listed as supported types in the structure definition
This is because, as of now, the type ``Age`` is not supported in the lookup generator_

### 5. Extensions
Extensions can be defined on any element. Because of that we can not possibly predict all extensions 
used and thus, will only flatten the ones which are part of a slicing. This means that all extensions which are not part
of a slice, will be ignored. 

Assume an extension as part of a slicing. We consider these 2 cases:
1. If this extension **does not** contain an extension itself, it's polymorphic element``Extension.value[x]`` is used
2. If this extension **does** contain an extension, 
   the polymorphic element must be of cardinality ``"max"=0`` and will be ignored, 
   and the child extension is flattened recursively instead.

Example of lookup with simple extension `Procedure.extension:Dokumentationsdatum` in profile [Prozedur](https://simplifier.net/mii-basismodul-prozedur-2024/mii_pr_prozedur_procedure):
````json
{
  "Procedure.extension": {                                                   <<<< //extension itself
    "viewDefinition": {
      "select": []
    },
    "children": [
      "Procedure.extension:Dokumentationsdatum",                             <<<< // for this example only Dokumentationsdatum
      "Procedure.extension:durchfuehrungsabsicht"
    ]
  },
  "Procedure.extension:Dokumentationsdatum": {                              <<<< // extension slice
    "parent": "Procedure.extension",
    "viewDefinition": {
      "forEachOrNull": "extension.where(url = 'http://fhir.de/StructureDefinition/ProzedurDokumentationsdatum')",  <<<< // selecting extension slice
      "select": []
    },
    "children": ["Procedure.extension:Dokumentationsdatum.value[x]"]
  },
  "Procedure.extension:Dokumentationsdatum.value[x]": {                      <<<< // flattening for polymorphic element Extension.value[x]
    "parent": "Procedure.extension",
    "viewDefinition": {
      "select": []
    },
    "children": [
      "Procedure.extension:Dokumentationsdatum.value[x]:valueDateTime"
    ]
  },
  "Procedure.extension:Dokumentationsdatum.value[x]:valueDateTime": {        <<<< // flattening for type datetime
    "parent": "Procedure.extension",
    "viewDefinition": {
      "forEachOrNull": "value.ofType(dateTime)",
      "select": [
        {
          "column": [
            {
              "name": "Procedure_extensionDokumentationsdatum_value_X_Valuedatetime",
              "path": "$this",
              "type": "dateTime"
            }
          ]
        }
      ]
    }
  }
}
````


Generated viewDefinition:
```json
{
  "resourceType": "https://sql-on-fhir.org/ig/StructureDefinition/ViewDefinition",
  "name": "Prozeduren",
  "status": "draft",
  "resource": "Procedure",
  "select": [
    {
      "column": [
        {
          "name": "id",
          "path": "id"
        },
        {
          "name": "patient",
          "path": "subject.reference"
        }
      ]
    },
    {
      "select": [
        {
          "select": [
            {
              "column": [
                {
                  "name": "Procedure_extensionDokumentationsdatum_value_X_Valuedatetime",
                  "path": "$this",
                  "type": "dateTime"
                }
              ]
            }
          ],
          "forEachOrNull": "value.ofType(dateTime)"                                        <<<< // flattening for type datetime
        }
      ],
      "forEachOrNull": "extension.where(url = 'http://fhir.de/StructureDefinition/ProzedurDokumentationsdatum')"        <<<< // selecting extension slice
    }
  ]
}
```

CSV output table:

| id      | patient           | Procedure_extensionDokumentationsdatum_value_X_Valuedatetime |
|---------|-------------------|--------------------------------------------------------------|
| pro-ex1 | Patient/pat-ex1   |                                                              |
| pro-ex2 | Patient/pat-ex2   | 2024-02-10T12:00:00+01:00                                    |
| pro-ex3 | Patient/pat-ex3   | 2024-03-05T10:00:00+01:00                                    |
| pro-ex4 | Patient/pat-ex4   | 2024-04-02T08:00:00+01:00                                    |
 













