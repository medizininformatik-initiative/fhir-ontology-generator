#!/bin/bash

export ONTOLOGY_SERVER_ADDRESS=${ONTOLOGY_SERVER_ADDRESS:-http://my-onto-server-address/fhir/}
export PRIVATE_KEY=${PRIVATE_KEY:-path-to-key-file}
export SERVER_CERTIFICATE=${SERVER_CERTIFICATE:-path-to-cert-file}
export POSTGRES_VERSION=${POSTGRES_VERSION:-16}

BASE_DIR="$( cd -- "$(dirname "$0")" >/dev/null 2>&1 || exit 1 ; pwd -P )"

export PYTHONPATH="$BASE_DIR"

PROJECT="fdpg-ontology"
steps_to_run=()
delete_folders=false


while [[ "$#" -gt 0 ]]; do
    case $1 in
        -p|--project) PROJECT=("$2"); shift ;;
        --step) steps_to_run+=("$2"); shift ;;
        --all) steps_to_run=(1 2 3 4 5 6); delete_folders=true ;;
        -h|--help)
          echo "Executes all steps necessary to generate the ontologies for a given project"
          echo "Arguments:"
          echo "  -h | --help              Display this help message"
          echo "  -p | --project [name]    Name of the project to generate the ontologies for. Default: 'fdpg-ontology'"
          echo "  -s | --step [1..6]       Index of a step to run. Can be provided multiple times"
          echo "  -a | --all               Run all steps"
          exit 0
          ;;
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

echo "Generating ontologies for project '${PROJECT}'"

if $delete_folders; then
    OUT_FOLDER_DIR="$BASE_DIR/projects/${PROJECT}/output"
    echo "Cleaning up output directory @${OUT_FOLDER_DIR} "
    rm -rf "$OUT_FOLDER_DIR"
    #folders=("$OUT_FOLDER_DIR/criteria-sets" "$OUT_FOLDER_DIR/elastic" "$OUT_FOLDER_DIR/mapping" "$OUT_FOLDER_DIR/sql_scripts" "$OUT_FOLDER_DIR/term-code-info" "$OUT_FOLDER_DIR/ui-trees" "$OUT_FOLDER_DIR/value-sets")
    #for folder in "${folders[@]}"; do
    #    [ -d "$folder" ] && rm -r "$folder" && echo "Deleted $folder" || echo "$folder does not exist"
    #done
fi

# Step 1: Generating cohort selection ontology
if should_run_step 1; then
    printf "\n#################\nStep 1: Generating cohort selection ontology\n#################\n"
    cd "$BASE_DIR/cohort_selection_ontology" || exit 1
    python3 scripts/generate_ontology.py --project "${PROJECT}" --generate_ui_trees --generate_ui_profiles --generate_mapping
fi

# Step 2: Generating DSE ontology
if should_run_step 2; then
    printf "\n#################\nStep 2: Generating DSE ontology\n#################\n"
    cd "$BASE_DIR/data_selection_extraction" || exit 1
    python3 scripts/generate_dse_files.py --project "${PROJECT}" --generate_profile_details --download_value_sets --generate_mapping_trees
fi

# Step 3: Merging ontologies for project
if should_run_step 3; then
    printf "\n#################\nStep 3: Merging Ontologies for project '${PROJECT}'\n#################\n"
    cd "$BASE_DIR/ontology_merging" || exit 1
    python3 scripts/merge_ontologies.py --merge_mappings --merge_uitrees --merge_sqldump --merge_dse \
     --project "${PROJECT}"
fi

# TODO: Refactor into execution of project-specific scripts found as BASH script in project dir
# Step 4: Generating and merging in combined consent
if should_run_step 4; then
    printf "\n#################\nStep 4: Generating and merging in combined consent\n#################\n"
    cd "$BASE_DIR/projects/${PROJECT}" || exit 1
    python3 combined_consent_generation.py --merge_mappings \
     --project "fdpg-ontology"
fi

# Step 5: Generating Elasticsearch files
if should_run_step 5; then
    printf "\n#################\nStep 5: Generating Elasticsearch files\n#################\n"
    cd "$BASE_DIR/elasticsearch" || exit 1
    python3 scripts/generate_elasticsearch_files.py \
     --project "${PROJECT}" \
     --update_translation_supplements
fi

# Step 6: Parcel ontology files
if should_run_step 6; then
    printf "\n#################\nStep 6: Parcel ontology files\n#################\n"
    cd "$BASE_DIR/parceling" || exit 1
    python3 scripts/parcel_final_ontology.py \
    --project "${PROJECT}"
fi
