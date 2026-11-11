# Concept Tree Generation

Module: `dataportal_generator.cohort_selection.core.generators.concept_tree`
Models: `dataportal_generator.cohort_selection.model.concept_tree`

For every criterion definition in a project, this module finds the concepts (codes) that can be selected for:

- the criterion's **identifier** (e.g. which diagnosis code identifying representing some clinical condition, a `Condition` resource instance in FHIR),
- the criterion's **value**, if it is of type `concept` (e.g. the coded result of an `Observation`),
- each of the criterion's **attributes** (e.g. `Observation.interpretation`). ATM they only support concept values,
  meaning an attribute is always eligable for concept tree generation.

It stores those concepts as **concept tree groups** (one JSON file per group) and keeps track of the associations
between criterion elememt and their concept tree groups by updating a **criterion mapping**. The mapping is written to
a file at the end of the generation process. The following steps are dependent on this step:

- `core/generators/ui_profile.py` uses the mapping to fill in the referenced value sets / tree groups of UI profiles.
- `core/generators/mapping_link.py` iterates over the identifier trees to link every contextualized term code to its
  query-language mapping entry.
    
## Entry point

```python
from dataportal_generator.cohort_selection.core.generators.concept_tree import generate_concept_trees
from dataportal_generator.common.model.project import Project

project = Project(path="example/example-project")
project.package_manager.restore(inflate=True, lenient=True)  # Ensure all packages are available and inflated
mapping = generate_concept_trees(project, remove_unused=True)
```

`generate_concept_trees(project, remove_unused=True) -> CriterionTreeMapping`

1. Loads all criterion definitions from `<project>/input/cohort_selection/modules/<module>/criteria/**/*.y(a)ml`
   (`util.io.load_criterion_definitions`). Modules and files are processed in sorted order.
2. Runs a `CriterionConceptTreeGenerator` for each criterion.
3. Writes the combined mapping to `<project>/output/cohort_selection/concept_trees/criterion_mapping.json`.
4. If `remove_unused` is set, deletes every tree group file no criterion references any more.

Failure of the process leads to a `ConceptTreeGenerationError` being raised.

**Requirements:**

- The project's package manager must be able to find the criterion's `definitionSource.structureDefinition` and any
  data-type profiles and value sets it references.
- The project's terminology source (`project.terminology_src`) has to be configured. The FHIR terminology source has to
  support the [`$closure`](https://hl7.org/fhir/R4/conceptmap-operation-closure.html) operation if code systems with 
  hierarchies are used.

## Inputs: what gets a concept tree

Given a criterion definition like:

```yaml
name: "LaboratoryMeasurement"
module: "Example"
definitionSource:
  structureDefinition: "https://www.medizininformatik-initiative.de/fhir/core/modul-labor/StructureDefinition/ObservationLab"
identifier:
  type: "binding"
  definition: "Observation.code"
value:                       # only `type: concept` produces concept trees
  type: "concept"
  definition: "Observation.value"
attributes:
  - name: "interpretation"
    definition: "Observation.interpretation"
```

| Criterion element                        | Mapping key        | How concepts are determined                                                         |
|------------------------------------------|--------------------|-------------------------------------------------------------------------------------|
| `identifier` with `type: fixed`          | `$identifier`      | The listed codings are used directly (see [Fixed codings](#fixed-codings))          |
| `identifier` with `type: binding`        | `$identifier`      | The FHIRPath expression is resolved against the profile (see [Element resolution](#element-resolution)) |
| `value` with `type: concept`             | `$value`           | Element resolution                                                                  |
| `value` with any other type              | *(not generated)*  | —                                                                                   |
| each entry in `attributes`               | `<attribute name>` | Element resolution                                                                  |

Each of these must produce at least one tree group, otherwise generation fails for the criterion.

## Element resolution

For expression-based elements (`_generate_for_implicit_definition`):

1. **Resolve the expression.** The expression is resolved against the criterion's structure definition with
   `FHIRPathResolver.resolve_leaf`. Expressions may use the project's FHIRPath extensions, such as
   `.slice(%profile, 'gene-studied')` or `.resolve()` to follow references into other profiles.
2. **Check the type.** The target `ElementDefinition` must have exactly one type, and it must be `code`, `Coding` or
   `CodeableConcept`.
3. **Collect restrictions.** The element definition is searched for things that limit its allowed values. Two kinds of
   restriction exist:
   - a **binding** to a value set, with strength `required`, `extensible` or `preferred` (`example` bindings are
     ignored), and
   - a **coding** fixed by `fixed[x]` or `pattern[x]`.
4. **Turn restrictions into tree groups.**
   - Each binding gives one value-set tree group, identified by the binding's value set canonical. It is only generated
     if no file for that identifier exists yet.
   - All complete codings (system **and** code present) are collected into one fixed-coding tree group, identified by
     `<module>.<criterion name>.<attribute key>`. Missing code system versions are filled in first.
5. Returns the identifiers of all these groups, in the order found.

If no restriction is found, generation fails with `ConceptTreeGenerationError`.

### How restrictions are collected per data type

**`CodeableConcept`** (`_codeable_concept_restriction`)

- If the element is **sliced**, the restrictions of every slice are combined and nothing else is looked at.
- `fixedCodeableConcept`: all of its codings are returned and nothing else is looked at. Every coding must have a
  system and code, otherwise a `ValueError` is raised.
- `patternCodeableConcept`: its complete codings are added.
- The element's own binding is added (if strong enough).
- The `coding` child is analysed as a `Coding` (below). Its codings are added. Of all the bindings found, only those
  with the strongest binding strength are kept.

**`Coding`** (`_coding_restriction`)

- `fixedCoding`: returned as the only restriction. System and code are both required.
- `patternCoding` provides a starting system and/or code.
- If there is still no system, it is taken from `fixedUri`/`patternUri` on the `system` child.
- The element's binding is used. If the bound value set is built from exactly one code system, that system is used.
- If there is still no code, the `code` child is analysed as a `code` (below).
- If system or code are still missing and the `Coding` type has a profile (a data-type profile), that profile's root
  element is analysed the same way and its results are merged in. Codings that contradict each other cause a
  `ValueError`.
- If the element is sliced, the restrictions of every slice are added as well.

**`code`** (`_code_restriction`)

- `fixedCode` / `patternCode` gives the code. The system is only known if the element's binding uses a value set built
  from exactly one code system.
- Without a fixed or pattern value, the binding (if strong enough) is returned.

The code systems a value set is built from are found by reading `compose.include` (following included value sets
recursively), or `expansion.contains` if there is no `compose`. The value set is first looked up in the project's
packages, then in the terminology source.

## Building the trees

A **concept tree** is the set of concepts from one code system version, including how they relate to each other. A
**concept tree group** holds one tree per code system version.

### Value-set groups

`_generate_concept_tree_group_for_vs_canonical`:

1. Expands the value set using the terminology source.
2. Reads the `used-codesystem` expansion parameters to work out a default version for each code system. Concepts
   without their own version get that default. Having no `used-codesystem` parameter at all is an error.
3. Groups the expanded concepts by `(system, version)`.
4. For each group, fetches the `CodeSystem` from the terminology source:
   - If the code system **defines a `hierarchyMeaning`**, a `$closure` is run over the group's concepts. The
     resulting closure table lists every ancestor of each concept. Ancestors that are also ancestors of another
     ancestor are removed, which leaves only the **immediate parents**. Each concept then lists its `parents`, and each
     parent lists its `children`.
     If the closure returns nothing, a warning is logged and a flat list is used instead.
   - Otherwise the concepts are written as a **flat list** with no parent or child links.
5. Stores the group with `valueSet` set to `<expanded VS url>|<expanded VS version>`, i.e. the exact version
   that was used.

### Fixed codings

`_generate_concept_tree_group_for_coding_list` groups the codings by `(system, version)` and writes one flat tree per
group. `valueSet` is not set. If a coding has no version, it gets the code system's default version, which is the
version returned by `terminology_src.code_system(url)` (cached for the whole process). The codes are **not** checked
against that version.

Fixed-coding groups are written again on every run. Value-set groups are not.

## Output

```
<project>/output/cohort_selection/concept_trees/
├── criterion_mapping.json
└── trees/
    ├── <uuid5(identifier)>.json
    └── ...
```

### Tree group files

The file name is `uuid5(NAMESPACE_DNS, identifier)` (`ConceptTreeGroup.uuid_of`). This lets the generator and
`util.io.load_concept_tree_group` find a group's file from its identifier alone.

```json
{
  "identifier": "http://example.org/fhir/ValueSet/my-vs",
  "valueSet": "http://example.org/fhir/ValueSet/my-vs|1.0.0",
  "trees": {
    "http://snomed.info/sct|http://snomed.info/sct/900000000000207008/version/20240201": {
      "system": "http://snomed.info/sct",
      "version": "http://snomed.info/sct/900000000000207008/version/20240201",
      "entries": [
        { "code": "A", "children": ["B", "C"] },
        { "code": "B", "parents": ["A"] },
        { "code": "C", "parents": ["A"] }
      ]
    }
  }
}
```

- `identifier`: the value set canonical as written in the binding (value-set groups), or
  `<module>.<criterion>.<key>` (fixed-coding groups).
- `valueSet`: the exact value set version that was expanded, or not present for fixed-coding groups.
- `trees`: keyed by `system|version` (just `system` if there is no version).
- `parents` / `children`: left out when empty. Both are always empty for flat lists.

### Criterion mapping

Maps module → criterion name → criterion element → list of tree group identifiers (`CriterionTreeMapping`):

```json
{
  "Example": {
    "LaboratoryMeasurement": {
      "$identifier": ["http://example.org/fhir/ValueSet/lab-codes"],
      "interpretation": ["http://hl7.org/fhir/ValueSet/observation-interpretation"]
    },
    "PatientAge": {
      "$identifier": ["Example.PatientAge.$identifier"]
    }
  }
}
```

An element can point to more than one group, for example when it is sliced and each slice binds a different value
set. Use `util.io.load_criterion_mapping` and `util.io.load_concept_tree_group` to read these files back.

## Reuse and cleanup

- **Reuse:** before generating a value-set group, the generator checks whether a file for that value set canonical
  already exists. This check only looks at the file name. If the binding canonical has no version, a group from an
  older run is reused even if the value set or code system has changed since. To force regeneration, delete the
  matching file or the whole `trees/` directory.
- **Sharing:** value-set groups are shared by every criterion element that binds the same canonical. Fixed-coding
  groups belong to one criterion element only.
- **Cleanup:** with `remove_unused=True`, any `trees/*.json` file whose name is not the UUID of an identifier in the
  new mapping is deleted after the run.

## Errors

| Situation                                                                              | Error                                    |
|----------------------------------------------------------------------------------------|------------------------------------------|
| Criterion's structure definition not found                                             | `ConceptTreeGenerationError`             |
| Expression cannot be resolved against the profile                                      | `ConceptTreeGenerationError`             |
| Target element has more than one type, or a type other than `code`/`Coding`/`CodeableConcept` | `ConceptTreeGenerationError`      |
| No binding or fixed/pattern value found for the target element                         | `ConceptTreeGenerationError`             |
| Incomplete `fixedCoding` / `fixedCodeableConcept`, or codings that contradict each other | `ValueError`                           |
| Value set, code system or data-type profile not found                                  | `ResourceNotFoundError`                  |
| Value set expansion has no `used-codesystem` parameter                                 | `ValueError`                             |

`generate_concept_trees` re-raises all of these as `ConceptTreeGenerationError`; the original error is kept as the
cause.
