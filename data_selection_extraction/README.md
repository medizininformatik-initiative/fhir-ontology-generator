# data_selection_extraction

Module holding functions and classes related to generating the **Data Selection and Extraction** ontology

## Profile Details

The **Profile Details** generation uses FHIR profiles from which the feature selection data models are created. It
processes the elements defined and constrained within FHIR profiles to determine their representation in the feature
selection data models. These models server as a kind of simplified view on the underlying data model for researchers and
people in general that do not need to know about implementation-specific details of the underlying data model - *FHIR* 
in this case.

### Field Config

To have control over how elements are handled and represented as fields of the *Profile details*, a project can provide
a `field_config.json` file in the input *data selection and extraction directory* 
(`<project>/input/data_selection_extraction/field_config.json`). It defines what elements are included/excluded, 
required, and recommended. Rules can be both defined such that they apply to all elements regardless of the profile or 
profile-specific (such that they apply to the profile itself and all profiles based on it).

> [!IMPORTANT]
> ATM if the config can not make a determination on how to handle an element definition the `filter_element` function is
> used to apply special handling. This behavior should be reworked at some point

#### Field Config Entry

The `FieldConfigEntry` model is the base component of the *field config*. It has the following fields:

| Name        | Type                                                                                  | Cardinality | Note                                                                 |
|-------------|---------------------------------------------------------------------------------------|-------------|----------------------------------------------------------------------|
| **pattern** | [ElementDefinition](https://hl7.org/fhir/R4/elementdefinition.html#ElementDefinition) | 1..1        | Pattern of a FHIR `ElementDefinition`                                  |
| **note**    | String                                                                                | 0..1        | Information about the rule, e.g. why it exists, what it covers, etc. |

The most important field is **pattern** as it defines what element definitions will match the rule/setting. Similar to 
how the `ElementDefinition` FHIR data type uses its `pattern` field, this field represents a pattern of an 
`ElementDefinition` that element definitions in the profiles have to match in order for the setting to apply. As such 
they have to match **all** field values set by the pattern. The following logic applies:

1) If the `FieldConfigEntry` field value is an object, an instance matches if all of its corresponding field values match
2) If the `FieldConfigEntry` field value is a list, an instance matches if the corresponding list in the instance contains at least the elements of the list in the config
3) Otherwise, direct comparison is performed between the value of the config and the instance

For instance the following example matches element definitions that are must-support and support the `Quantity` data 
type:

```json
{
  "pattern": {
    "mustSupport": true,
    "type": [
      {
        "code": "Quantity"
      }
    ]
  },
  "note": "Simple pattern matching on must-support and supported types"
}
```

When matching against the following element definition, a match would be found:

```json
{
  "id": "Observation.value[x]:someSlice",
  "path": "Observation.value[x]",
  "label": "Some Slice",
  "mustSupport": true,
  "type": [
    {
      "code": "CodeableConcept"
    },
    {
      "code": "Quantity"
    }
  ],
  "base": {
    "path": "Observation.value[x]"
  }
}
```

##### Regex Matching

Fields with *String*-typed values do support RegEx-style matching. It can be enabled by prefixing the RegEx string with
the prefix `?regex:` as is shown in the example which matches all element definitions whos `id` element contains the 
string `type`:

```json
{
  "pattern": {
    "id": "?regex:.*type.*"
  }
}
```

Note that the pattern has to **fully** match the input string in order for a match to be found.

The RegEx matching does support special modifiers to make defining filters on the FHIR data model easier. To insert 
them into the pattern you have to use the following expression:

```
(?fhir:<modifiers>)
```

where the `<modifiers>` are a **semicolon** separated list of modifiers that are applied in order from left to right, e.g.

```
(?fhir:modifier1();modifier2();...;modifierN())
```

applies `modifier1` first, then `modifier2`, etc. Note that the modifiers can take input parameters by inserting them
into the parentheses.

They currently supported modifiers are listed in the table below:

| Signature                             | Description                                                                   | Example                                                  |
|---------------------------------------|-------------------------------------------------------------------------------|----------------------------------------------------------|
| `slices(filter: Optional[str])`       | Matches only slices defined on the element                                    | `?regex:Encounter.type(?fhir:slices(".*level.*"))`       |
| `slicesOrSelf(filter: Optional[str])` | Matches slices and the element on which they are defined                      | `?regex:Encounter.type(?fhir:slicesOrSelf(".*level.*"))` |
| `descendants()`                       | Matches all descendant element definitions. This does not include direct slices | TODO                                                     |
| `descendantsOrSelf()`                 | Like `descendants` but also matches the element on which it is is called      | TODO                                                     |