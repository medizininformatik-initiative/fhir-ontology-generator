# Generate Elasticsearch Input for Ontology

After an ontology has been merged, the necessary elastic search files for the ontology can be generated. When setting up
the FDPG backend component, these files will be imported into its own Elasticsearch instance. The backend uses it to 
query individual ontology components (e.g. search criteria, criterion attributes, codings in a certain terminology 
system or supported by some criterion, etc.) using search strings.

## Generate the Elasticsearch files

The elastic search files generator expects a specific file structure of the merged ontology.

## How it works

**Generating the ontology search files**

It reads in the `ui_tree`s and for each `ui_tree` loads the respective `term-code-info`. Based on this information it 
generates the Elasticsearch files, which combines the information from the two files to generate the information for 
each criterion, including the parent and child relationships.

These files are then saved in the `projects/<project-name>/output/elastic` folder as the ontology input with file name 
prefix `onto_es__ontology*`.

**Generating the value set search files**

Additionally, the program then reads in all the value-sets and converts them into an elastic search input.

These files are then saved in the `projects/<project-name>/output/elastic` folder as the codeable_concept search input 
with file name prefix `onto_es__codeable_concept*`.

## Availability

The program currently also contains a part which allows you to generate the elastic search availability input files from multiple
MeasureReport.json as produced by the fhir data evaluator project see: [link fhir data evaluator](https://github.com/medizininformatik-initiative/fhir-data-evaluator)

To generate the availability toggle `--generate_availability` and add the directory `--availability_input_dir` from 
which to read the `MeasureReport.json` files.
**NOTE:** The filename is irrelevant, but should end on `.json`.

## Example Call

`python3 generate_elasticsearch_files.py --ontology_dir projects/fdpg-ontology`

### Configuration

**Script Options:**

| Argument                   | Description                                                                                                                                                         |
|----------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| --project [project-name]   | Project to generate for e.g. generate using input files from location `projects/<project-name>/input` and write generated files to `projects/<project-name>/output` |
| --generate_profile_details | Flag to generate profile details                                                                                                                                    |
| --generate_mapping_trees   | Flag to generate mapping trees                                                                                                                                      |
| --generate_availability    | Flag to generate availability                                                                                                                                       |
| --download_packages        | Downloads FHIR packages for DSE gen defined in `projects/<project-name>/input/data_selection_extraction/required-packages.json`                                     |
| --copy_snapshots           | Copy and filter allowed profiles for processing during DSE gen                                                                                                      |
| --profiles [profile-url]+  | List of profiles to process identified by their URL to limit the amount of profiles processed to it                                                                 |