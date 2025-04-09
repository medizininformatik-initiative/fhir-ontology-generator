#!/bin/bash

export ONTOLOGY_SERVER_ADDRESS=${ONTOLOGY_SERVER_ADDRESS:-http://my-onto-server-address/fhir/}
export PRIVATE_KEY=${PRIVATE_KEY:-path-to-key-file}
export SERVER_CERTIFICATE=${SERVER_CERTIFICATE:-path-to-cert-file}
export POSTGRES_VERSION=${POSTGRES_VERSION:-16}

BASE_DIR="$( cd -- "$(dirname "$0")" >/dev/null 2>&1 || exit 1 ; pwd -P )"

export PYTHONPATH="$BASE_DIR"

steps_to_run=()
delete_folders=false


while [[ "$#" -gt 0 ]]; do
    case $1 in
        --step) steps_to_run+=("$2"); shift ;;
        --all) steps_to_run=(1 2 3 4 5 6); delete_folders=true ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
    shift
done

should_run_step() {
    local step=$1
    for i in "${steps_to_run[@]}"; do
        if [[ "$i" == "$step" ]]; then
            return 0
        fi
    done
    return 1
}

if $delete_folders; then
    OUT_FOLDER_DIR="$BASE_DIR/projects/fdpg-ontology"
    folders=("$OUT_FOLDER_DIR/criteria-sets" "$OUT_FOLDER_DIR/elastic" "$OUT_FOLDER_DIR/mapping" "$OUT_FOLDER_DIR/sql_scripts" "$OUT_FOLDER_DIR/term-code-info" "$OUT_FOLDER_DIR/ui-trees" "$OUT_FOLDER_DIR/value-sets")
    for folder in "${folders[@]}"; do
        [ -d "$folder" ] && rm -r "$folder" && echo "Deleted $folder" || echo "$folder does not exist"
    done
fi


# Step 1: Generating cohort selection ontology
if should_run_step 1; then
    printf "\n#################\nStep 1: Generating cohort selection ontology\n#################\n"
    cd "$BASE_DIR/projects/mii_core_data_set" || exit 1
    python3 generate_ontology.py --generate_ui_trees --generate_ui_profiles --generate_mapping
fi

# Step 2: Generating DSE ontology
if should_run_step 2; then
    printf "\n#################\nStep 2: Generating DSE ontology\n#################\n"
    cd "$BASE_DIR/dse" || exit 1
    python3 generate_dse_files.py --generate_profile_details --download_value_sets --generate_mapping_trees --loglevel INFO
fi

# Step 3: Merging Ontologies into fdpg-ontology
if should_run_step 3; then
    printf "\n#################\nStep 3: Merging Ontologies into fdpg-ontology\n#################\n"
    cd "$BASE_DIR/util/ontology" || exit 1
    python3 OntologyMergeUtil.py --merge_mappings --merge_uitrees --merge_sqldump --merge_dse \
     --dseontodir "$BASE_DIR/dse/generated" \
     --outputdir "$BASE_DIR/projects/fdpg-ontology" \
     --ontodirs "$BASE_DIR/projects/mii_core_data_set/CDS_Module/Diagnose/generated-ontology" \
     "$BASE_DIR/projects/mii_core_data_set/CDS_Module/Bioprobe/generated-ontology" \
     "$BASE_DIR/projects/mii_core_data_set/CDS_Module/Person/generated-ontology" \
     "$BASE_DIR/projects/mii_core_data_set/CDS_Module/Fall/generated-ontology" \
     "$BASE_DIR/projects/mii_core_data_set/CDS_Module/Labor/generated-ontology" \
     "$BASE_DIR/projects/mii_core_data_set/CDS_Module/Medikation/generated-ontology" \
     "$BASE_DIR/projects/mii_core_data_set/CDS_Module/Prozedur/generated-ontology" \
     "$BASE_DIR/projects/mii_core_data_set/CDS_Module/Einwilligung/generated-ontology"
fi

# Step 4: Generating and merging in combined consent
if should_run_step 4; then
    printf "\n#################\nStep 4: Generating and merging in combined consent\n#################\n"
    cd "$BASE_DIR" || exit 1
    python3 combined-consent-generation.py --merge_mappings \
     --consentinputdir "$BASE_DIR/projects/mii-consent-generation" \
     --mergedontodir "$BASE_DIR/projects/fdpg-ontology"
fi

# Step 5: Generating Elastic Search files
if should_run_step 5; then
    printf "\n#################\nStep 5: Generating Elastic Search files\n#################\n"
    cd "$BASE_DIR" || exit 1
    python3 generate_elasticsearch_files.py \
     --ontology_dir "$BASE_DIR/projects/fdpg-ontology" \
     --update_translation_supplements
fi

# Step 6: Parcel ontology files
if should_run_step 6; then
    printf "\n#################\nStep 6: Parcel ontology files\n#################\n"
    cd "$BASE_DIR" || exit 1
    python3 parcel_final_ontology.py \
    --ontology_dir "$BASE_DIR/projects/fdpg-ontology"
fi
