# Generate Elastic Search Input for Ontology

After an ontology has been merged, the necessary elastic search files for the ontology can be generated.

## Generate the Elastic Search files

The elastic search files generator expects a specific file structure of the merged ontology.




## How it works

**Generating the ontology search files**
It reads in the ui_trees and for each ui_tree loads the respective term-code-info.
Based on this information it gnerates the elastic search files, which combines the information from the two files to generate the information
for each criterion, including the parents and children relationships.

These files are then saved in the `elastic` folder as the ontology input with filenames onot_es__ontology*.

**Generating the value set search files**

Additionally the program then reads in all the value-sets and converts them into a elastic search input.

These files are then saved in the `elastic` folder as the codeable_concept search input with filenames onot_es__codeable_concept*.


## Availability

The program currently also contains a part which allows you to generate the elastic search availability input files from multiple
MeasureReport.json as produced by the fhir data evaluator project see: [link fhir data evaluator](https://github.com/medizininformatik-initiative/fhir-data-evaluator)

To generate the availability toggle `--generate_availability` and add the directory `--availability_input_dir` from which to read the MeasureReport.json files.
note the filename is irrelevant, but should end on .json

## Example Call

`python3 generate_elasticsearch_files.py --ontology_dir projects/fdpg-ontology`


### Configuration

**Script Options:**

| Argument                     | Description                      |
|------------------------------|----------------------------------|
| --ontology_dir               | Directory of the merged ontology |
| --generate_availability       | Flag to generate availability   |
| --availability_input_dir     | Directory for availability input |

