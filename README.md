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



## How it works
The Logical Model of GECCO within the data set matches in its representation the hierarchy display below the  GECCO core entry: https://simplifier.net/guide/germancoronaconsensusdataset-implementationguide/home
Within the Logical Model the categories can be identified as well as their sub entries. Both are parsed into a tree structure with its TermCode .
Using the names of the sub entries the matching profiles are identified. In the process of parsing the corresponding profiles the resource type, its coding and optional value definitions are created. In cases where the value of a concept is itself a concept a valueset defines the possible values. Using a terminology server the valuesets are expanded and translated to the valuedefinitons.
In the process an information loss takes place. All Fhir resources are reduced to a defining TermCode to identify the concept and an optional value definition defining the one possible value within the resource. In consequence additional information can be necessary in the process of translating the criterion to a fhir search or cql request. 
The mapping Model therefor provides in addition to search parameters for each resource type, fixed criteria that concertize the request.
To allow the selection of a parent criterion to refer to all criterions below a tree structure of all TermCodes is provided to find all children of a node.
Wherever possible, the display texts are in German if a German display is either defined in the gecco dataset or provided by the terminology server. For each category, CSV files with German and English display texts are provided so that medical experts can add the German terms if they are missing.