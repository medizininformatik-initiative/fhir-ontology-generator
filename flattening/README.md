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

_Recommended_: _Include elements `id` and `subject.reference` (only if part of patient compartment) 
by default to later be able to identify patients in your data._

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
lookup would be generated:
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

- _Generic_ complex elements which can all be flattened the same.
- _Non-Generic_ complex element types need to be flattened in a for each specifically defined way. 
    This applies to the following types: ``Coding``, `CodeableConcept`, `Extension`, `Reference`, `BackboneElement`, `Polymorphic`

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
- Each CodeableConcept will contain its corresponding ``.coding`` element, even if not explicitly defined
- Each Coding(defined or not) will be split up by slices if any present.
















foreach or null wird immer verwendet
a
a
a
a
a
a
a
a
a
a
a
a
a
a

a
a
a

a

a

a

a

a

a

a

a

a

a

a

a
