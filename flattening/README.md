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
these can be flattened directly.

