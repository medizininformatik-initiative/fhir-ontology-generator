# Parceling an ontology

Once the ontology has been merged and the elastic search input files generated, the ontology can be parceled.

## Parcel merged ontology

Takes the merged ontology folder and parcels the files for distribution and use in the different components.

## Example Call

`python3 parcel_final_ontology.py --project fdpg-ontology`

### Configuration

**Script Options:**

| Option                   | Description                 |
|--------------------------|-----------------------------|
| --project <project-name> | Project to parcel files for |
