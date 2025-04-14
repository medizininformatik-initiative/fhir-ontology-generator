# Ontology Merge Script
This script merges the generated files of two ontologies

The selection of the components to be merged can be done via script parameters, if the entire ontologies should be joined use all 3:
```
--merge_uitrees 
```
```
--merge_mappings 
```
```
--merge_sqldump
```
| Var              | Description                                                 | Example                                       | Default   |
|------------------|-------------------------------------------------------------|-----------------------------------------------|-----------|
| ONTOPATH_JOINED  | Output Path                                                 | projects/joinTest/                             | -         |
| ONTOPATH_LEFT    | Path of the base ontology the extension will be joined into | projects/bildgebung_prelim/generated-ontology/ | -         |
| ONTOPATH_RIGHT   | Path of the extension ontology                              | projects/dktk_oncology/generated-ontology/     | -         |
| UITREE_DIR_LEFT  | UI-tree folder for the base ontology                        | trees/                                        | ui-trees/ |
| UITREE_DIR_RIGHT | UI-tree folder for the extension ontology                   | trees/                                        | ui-trees/ |
| SQL_SCRIPT_DIR   | Path to the different SQL Dumps                             | /tmp/sqldumps/                                |           |
