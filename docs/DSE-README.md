# Generating a Data Selection Ontology

The data selection ontology allows researchers to select health record items (HRI) to extract.

For the purpose of this ontology, each health record item is represented by a FHIR profile (e.g. 
https://www.medizininformatik-initiative.de/fhir/core/modul-labor/StructureDefinition/ObservationLab) which are based on 
standard FHIR resources (e.g. Condition, Patient, Observation).

Each health record item to extract has multiple attributes an HRI is composed of.
For example a laboratory value (see profile above) has attributes like "value" and "effectiveDateTime", as defined by a 
FHIR path or - in case of a profile - an element ID.

For a data selection a researcher is then able to define their own HRI (specific combination of attributes of an HRI) to 
extract.

Additionally, the ontology defines how the researcher can filter the respective HRI. This is done based on the fields 
and in the current implementation corresponds to FHIR Search parameters.

the data selection ontology is always composed of two elements:
- **Profile Tree:** A tree of the available HRIs to extract (one for each profile)
- **Profile Details:** Contains Information about the specific HRI including the available attributes and what filters 
  are allowed to be applied to it

## Requirements

- Python 3.8 or higher
- Firely Terminal available at https://simplifier.net/downloads/firely-terminal v3.1.0 or higher
- Access to a terminology server with all value sets used in the FHIR profiles

## How it works - Overview

The fhir ontology generator allows you to generate all the files above at the same time or independently of each other. 
For details see script options section below.

All files are generated based on the profiles (packages as specified on simplifier) and it allows you to exclude 
directories of packages in order not to accidentally generated base profiles which you would not want to offer for data 
selection.

## A step-by-step guide to a new ontology

### Step 1 - Download and Evaluate packages

First one should familiarize themselves with the FHIR packages one is interested in and then download the complete 
packages. This can be done manually or via the generator by specifying the required_packages in the 
`required-packages.json`.

### Step 2 - Add Translations (Temporary)

It is currently possible to add your own translations for fields to the project, by adding a copy of the las generations 
`profile_details_all.json` to the project and naming it `profile_details_all_translations.json`. For now ignore this 
function, but be aware that a translation mechanism will be developed in future iterations.


### Step 3 - Download all the required packages for your ontology

To generate a new ontology one requires specific packages, which the ontology depends on.
These have to be added to the `required_packages.json` file. 

The packages you need can be found by opening the package tab of the new module you wish to generate your ontology for 
(e.g. <https://simplifier.net/MedizininformatikInitiative-Modul-Intensivmedizin/~packages>).

You can then download all required packages by running the generate_ontology.py with the `--download_packages` option.

**NOTE:** There is currently a problem with too many retries when downloading many packages from simplifier. The current 
solution is to retry the download at a later stage.

### Step 4 - Generate snapshots used for the ontology generation

You can now generate your data selection ontology by running the program with the flags `--generate_profile_details` and 
`--download_value_sets`.

Note that the program always generates the profile_tree.json regardless of configuration.

Note that the value_sets are necessary to make the researcher be able to filter HRIs for example by a code of a 
laboratory value.

Therefore, one should execute the program at least once with `--download_value_sets` when happy with the general 
ontology created.

## How it works - Detailed (Check out the step-by-step guide before)

The program goes through all packages and their snapshots and for each one checks if it is a StructureDefinition, is not 
an Extension, is active and is of type resource to ensure only profiles for actual HRIs are processed.

It then assigns each to a module based on the profile url and builds a hierarchy within each profile as an HRI based on 
inter-profile references.  After this it converts the output into a `profile_tree.json` file.

The program then generates the details for each profile based on the respective snapshot of the profile as follows:

**Filter**: 

According to the `mapping_type_code` it searchers for value sets in the respective path in form of a coding and only if a 
value set is found a code filter is created.

A time restriction filter is always added.

No other filter a currently supported

**Attributes**: 

Attributes are added to each HRI by going through all `elements` specified in the snapshot and are added as fields, if
1. Are must support fields
2. Are _not_ in fields_to_exclude = [".meta", ".id", ".subject", ".extension"]
3. Are _not_ the children of a multipart field as designatet by "[x]"
4. Are _not_ of primitive type = ["instant", "time", "date", "dateTime", "decimal", "boolean", "integer", "string", 
   "uri", "base64Binary", "code", "id", "oid", "unsignedInt", "positiveInt", "markdown", "url", "canonical", "uuid"]

### Configuration

**Environment variables:**

| Var | Description | Example |
|--------|-------------|---------|
|ONTOLOGY_SERVER_ADDRESS | Address of the Ontology server fhir api (with "/") | my_onto_server.com/fhir/
|SERVER_CERTIFICATE | Path to the certificate of the Ontology server fhir api| C:\Users\Certs\certificate.pem
|PRIVATE_KEY | Path to the private key for the Ontology server | C:\Users\Certs\private_key.pem

**Script Options:**

|Option| Description                                                                                                       |
|---|-------------------------------------------------------------------------------------------------------------------|
|--project| Project to generate for e.g. generate using input files from location `projects/<project-name>/input` and write generated files to `projects/<project-name>/output`|
|--download_packages| Toggle download packages -> required to generated snapshots - Execute only once as you add new packages           |
|--generate_profile_details| Toggle generate profile details -> generates the details for the profile tree                                     |
|--download_value_sets| Download the value sets to make the code filters possible -> Execute only towards end of your ontology generation |
