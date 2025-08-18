#!/bin/bash

usage() {
  echo "Usage: generate-coding-availability-measure.sh [options]"
  echo "  -h. --help              Display this help message"
  echo "  -p, --project <name>    Specify project to generate for (required)"
}

help() {
  echo "Generates a Measure resource for analyzing coding variance"
  usage
}

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
AVAILABILITY_DIR=$( dirname "$SCRIPT_DIR" )
PROJECT=""

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    -h | --help)
      help
      exit 1
      ;;
    -p | --project)
      PROJECT="$2"
      shift 2
      ;;
    *)
      echo "ERROR: Unknown option '$1'"
      echo ""
      usage
      exit 0
      ;;
  esac
done

if [[ -z "$PROJECT" ]]; then
  echo "ERROR: Missing project name"
  exit 1
fi

sushi "$AVAILABILITY_DIR/measure_shorthand"

TARGET_DIR="$( pwd )/projects/$PROJECT/output/availability"
mkdir -p "$TARGET_DIR"
TARGET_FILE="$TARGET_DIR/Measure-CdsCodingAvailability.fhir.json"
echo "Copying measure file to $TARGET_FILE"
cp "$AVAILABILITY_DIR/measure_shorthand/fsh-generated/resources/Measure-CdsCodingAvailabilityMeasure.json" "$TARGET_FILE"
cp "$AVAILABILITY_DIR/resources/stratum-to-context.json" "$TARGET_DIR/stratum-to-context.json"
