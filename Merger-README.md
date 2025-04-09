# Merging an ontology

Once the data selection and the cohort selection ontologies have been generated, they need to be merged.

The merger implemented here allows you to merge multiple ontologies into one ontology.

## Merge ontologies

The ontology merger takes the files from multiple ontologies and merges them into one.

The ontology merges expects each ontology folder to have the following structure:

./mapping/cql/mapping_cql.json
./mapping/fhir/mapping_fhir.json
./value-sets/*.json
./criteria-sets/*.json
./term-code-info/*.json
./ui-trees/*.json
./ui-profiles/*.json
./R__Load_latest_ui_profile.sql

and the dse folder to have the following structure:
value-sets/*value-set-names.json
R__load_latest_dse_profiles.sql 
profile_details_all.json        
profile_tree.json

## How it works

The ontology merger copies all files from the respective dirs into on directory and for some files opens them all and adds them together to one large file.
It further combines the R__Load_latest_ui_profile.sql files found in the different folders to one large database sql file.

## Example Call

`python3 OntologyMergeUtil.py --merge_mappings --merge_uitrees --merge_sqldump --merge_dse  --ontodirs absolute-path-to-repo/projects/mii_core_data_set/generated-ontology --dseontodir absolute-path-to-repo/dse/generated --outputdir absolute-path-to-repo/example/your-folder-here`

### Configuration

**Script Options:**

| Option      | Description                                                                                                                                |
|-------------|--------------------------------------------------------------------------------------------------------------------------------------------|
| --merge_mappings | Toggle to merge mappings                                                                                                              |
| --merge_uitrees | Toggle to merge UI trees                                                                                                               |
| --merge_sqldump | Toggle to merge SQL files R__load_latest_dse_profiles.sql  from the different ontologies                                               |
| --merge_dse | Toggle to merge DSE                                                                                                                        |
| --ontodirs  | List of directory paths (space separated) to ontologies to be merged (Required), point to generated-ontology folder of repsective ontology |
| --dseontodir | Directory path for DSE ontologies (Required), point to generated folder of dse                                                            |
| --outputdir | Output directory for merged ontology (Required)                                                                                            |
| --log-level | Set the logging level (Options: DEBUG, INFO, WARNING, ERROR, CRITICAL; default is DEBUG)                                                   |
