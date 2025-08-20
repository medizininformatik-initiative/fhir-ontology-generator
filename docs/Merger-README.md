# Merging an ontology

Once the data selection and the cohort selection ontologies have been generated, they need to be merged.

The merger implemented here allows you to merge multiple ontologies into one ontology.

## Merge ontologies

The ontology merger takes the files from multiple ontologies and merges them into one.

The ontology merges expects each (module) ontology folder (e.g. folders with path like 
`<project-root>/projects/<project-name>/output/cohort_selection_ontology/modules/<module>`) to have the following 
structure:

- `mapping/cql/mapping_cql.json`
- `mapping/fhir/mapping_fhir.json`
- `value-sets/*.json`
- `criteria-sets/*.json`
- `./term-code-info/*.json`
- `./ui-trees/*.json`
- `./ui-profiles/*.json`
- `./R__Load_latest_ui_profile.sql`

and the data selection ontology folder to have the following structure:

- `value-sets/*value-set-names.json`
- `R__load_latest_dse_profiles.sql` 
- `profile_details_all.json`        
- `profile_tree.json`

## How it works

The ontology merger copies all files from the respective dirs into on directory and for some files opens them all and 
adds them together to one large file. It further combines the R__Load_latest_ui_profile.sql files found in the different 
folders to one large database sql file.

## Example Call

`python3 ontology_merging/scripts/merge_ontologies.py --merge_mappings --merge_uitrees --merge_sqldump --merge_dse --project fdpg-ontology`

### Configuration

**Script Options:**

| Option                   | Description                                                                              |
|--------------------------|------------------------------------------------------------------------------------------|
| --merge_mappings         | Toggle to merge mappings                                                                 |
| --merge_uitrees          | Toggle to merge UI trees                                                                 |
| --merge_sqldump          | Toggle to merge SQL files R__load_latest_dse_profiles.sql  from the different ontologies |
| --merge_dse              | Toggle to merge DSE                                                                      |
| --project <project-name> | Project to merge mappings for                                                            |
