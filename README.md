# CODEX - Gecco to UI and Mapper

## Requirements

Python 3.8 or higher \
Firely Terminal available at https://simplifier.net/downloads/firely-terminal \
Access to a terminology server with all value sets defined in the gecco dataset

## Configuration

| Var | Description | Example |
|--------|-------------|---------|
|ONTOLOGY_SERVER_ADDRESS | Address of the Ontology server fhir api| my_onto_server.com/fhir

## Results
Running the script results in:
* downloading the GECCO data set
* the creation of csv files in the csv folder with all terminologies used in the ui
* the creation Anamnses Risikofaktoren.json Andere.json Demographie.json Laborwerte.json Therapie.json in /result
* the creation of terminology tree structure to expand term codes and the termc ode mapping for the query builder in mapping
