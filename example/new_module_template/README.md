# Base example template project for ontology generation

The FHIR ontology generator generates all the required ontology files and database entries needed as part of the fdpg+ project for feasibility queries.

The aim of the ontology is to provide information needed to search for, display, select and specify criteria for a feasibility query.
It further puts them in a hierachical relationship (tree) to allow for resolving multiple select

The ontology is always composed of four elements:
- **UI Trees:** UI trees contain the information needed to display the criteria in a hierachical structure
- **UI Profiles:** UI profiles describe how each criterion can be filtered or specified further (e.g. what values and attributes are allowed)
- **Mappings:** Query language specific mappings, which define how criteria and their attribute and value filters should be mapped to the respective query language
- **Mapping Tree:** Generated based on the ui trees the mapping tree is used to resolve children elements of a parent, so that all the leaves of a tree are queried if a non-leaf element is selected


## Requirements

Python 3.8 or higher \
Firely Terminal available at https://simplifier.net/downloads/firely-terminal v3.1.0 or higher  \
Access to a terminology server with all value sets used in the FHIR profiles

## How it works - Overview

The fhir ontology generator allows you to generate all the files above at the same time or independently of each other. For details see script options section below.

All files are generated based on a combination of the fhir profiles (packages as specified on simplifier), querying meta data (config files) and a terminology server to resolve value set bindings. These bindings specify how to create criteria (criteria identifying attribute binding) as well as filter options (binding for codeable concept value sets).

## A step by step guide to a new ontology

### Step 1 - Download and Evaluate snaphots

First one needs to download analyze the profiles of a new module on simplifier (e.g. <https://simplifier.net/mii-basismodul-diagnose-2024/mii_pr_diagnose_condition>) and download the "snapshot" using the Download button in the top right corner.

It helps to look at the snapshot json as well as the simplifier profile view. Further request the mii_new_module file from the respective MII FHIR module team and check that at least the "criterion identifier" as well as the "time restriction" is specified.

**Note!:** This downloaded snapshot is not to be saved in the ontology repo folders and is instead to be saved elsewhere and only used for pre ontology generation analysis purposes.

### Step 2 - Create differentials from snapshots

Create a differential for all snapshots (example see ICUBeatmung in this repository). Note that your differential has to refer to the snapshot with its own field "baseDefinition" linking to the "url" field of the snapshot. 

In your differential you can then change the "name", which is used as the name of the Category in the UI the generated criteria are under and you can also further specify other changes you would like to make (example change the possible units or other value set bindings).


### Step 3 - Download all the required packages for your ontology

To generate a new ontology one requires specific packages, which the ontology depends on.
These have to be added to the `resources/required_packages.json` file. 

The packages you need can be found be opening the package tab of the new module you wish to generate your ontology for (e.g. <https://simplifier.net/MedizininformatikInitiative-Modul-Intensivmedizin/~packages>)

You can then download all required packages by running the generate_ontology.py with the `--download_packages` option.

**NOTE:** There is currently a problem with too many retries when downloading many packages from simplifier. The current solution is to retry the download at a later stage.

### Step 4 - Generate snapthots used for the ontology generation

You can now generate the snapshots used for the ontology generation. These snapshots are created by the ontology generator by combining your differential with the snapshot the differential is based on according to the "baseDefinition" (see Step 2). To generate these snapshots run the generate_ontology.py with the `--generate_snapshot` option. This wil use the required packages downloaded in step 3.


### Step 5 - Create Metadata Config files

Now you have to specify how the ontology is to be generated based on the snapshot. To do this you have to create config files (one per snapshot / profile) you wish to generate an ontology for.

One example of this can be found in `resources/QueryingMetaData/Beatmung`.

In the querying metadata you have to specify at least the `term_code_defining_id` field as criteria require at least an identification in order to query them.

Further the generator needs to be told which metadata is for which snapshot. This has to be specified in the `resources/profile_to_query_meta_data_resolver_mapping.json`. Here the `name`attribute of the snapshot json has to be matched to the file name of the QueryingMetaData without the `.json` suffix.

### Step 6 - Generate the ontology

You can now generate the ontology by running the script with the `--generate_ui_trees --generate_ui_profiles --generate_mapping` options.
Note that you can run any of these individually and independently of each other. It is generally recommended to run each stage separately and checking
the output before proceeding further to reduce complexity and to avoid long generation cyclces when developing a new ontology.


## How it works - Detailed (Check out the step by step guide before)

The program goes through all snapshots and for each
- Find the metadata config by name of snapshot "SD_MII_ICU_Beatmung" and resolver mapping to Filename of MedaData
- For each criteria category (grouping of multiple differentials) (see same folder in differential) for each snapshot:
    - resolve the `term_code_defining_id` to a fhir path and evaluate the element in the snapshot json:
        - if pattern or fixed create criterion directly, if bound to value set use terminology server to resolve the value set
    - Resolve the `value_defining_id` to a fhir path and depending on type (also resolved to parents if no type given for element):
        - if codeable concept or coding -> if pattern or fixed create selection directly, if bound to value set use terminology server to resolve the value set
        - if quantiy -> generate quantity, unit currently has to be part of differential
    - Resolve each entry of the `attribute_defining_id_type_map` analogous to the `value_defining_id`
        - Here additionally a attribut type `reference" can be specified. If reference is specified the id will be resolved according the brackets of the id
            - Example: `((Specimen.extension:festgestellteDiagnose).value[x]).code.coding:icd10-gm` - everything in brackets specifies where to find the reference. in this case an extension, which means the value is looked for in the respective extension json. This value is then of type reference and the slice coding:icd10-gm tells the generator in which value set the referenced criteria are allowed to be in.

- **SearchParameters:** Search parameters are resolved by FHIR path and custom search parameters have to be explicitedly added to the search_parameter folder as single json files


## Configuration

**Environment variables:**

| Var | Description | Example |
|--------|-------------|---------|
|ONTOLOGY_SERVER_ADDRESS | Address of the Ontology server fhir api (with "/") | my_onto_server.com/fhir/
|SERVER_CERTIFICATE | Path to the certificate of the Ontology server fhir api| C:\Users\Certs\certificate.pem
|PRIVATE_KEY | Path to the private key for the Ontology server | C:\Users\Certs\private_key.pem

**Script Options:**

|Option|Description|
|---|---|
|--download_packages| Toggle download packages -> required to generated snapshots - Execute only once as you add new packages|
|--generate_snapshot| Toggle generate snapshots -> required before ontology can be generated|
|--generate_ui_trees| Toggle generate ui trees and mapping tree|
|--generate_ui_profiles| Toggle generate ui profiles|
|--generate_mapping| Toggle generate mappings (default CQL and FHIR)|

## Querying Metadata Config files

|field|Description|Example|
|---|---|---|
|name| Name of the querying metadata - note currently the filename is used to match snapshot to metadata|ObservationValueQuantity|
|resource_type| The FHIR resource type of the criteria generated|Obervation|
|context| Identifies the context of the criteria generated for this metadata - used to distinguish between same codesystems used for different criteria sets|"context": {"system": "fdpg.mii.gecco","code": "QuantityObservation", "display": "QuantityObservation"}|
|term_code_defining_id|element id of the attribute in the profile snapshot used to identify the critieria / generate the criteria set for the profile|Observation.code.coding:loinc|
|value_defining_id| element id of the attribute which defines the main value for a criterion if one exists - can otherwise be omitted|Observation.value[x]:valueQuantity|
|time_restriction_defining_id|element id of the attribute which defines the time restriction for the criteria set to be generated|Observation.effective[x]|
|attribute_defining_id_type_map| a object of entries with a element id which defines an attribute code and an additional information what type of attribute it is (i.e. reference), specifically for a reference the type has to be explicitedly given, otherwise can be omitted and is then inferred |"attribute_defining_id_type_map": {"((Specimen.extension:festgestellteDiagnose).value[x]).code.coding:icd10-gm": "reference","Specimen.collection.bodySite.coding:icd-o-3": ""}|
