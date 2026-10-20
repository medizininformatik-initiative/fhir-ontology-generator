#!/bin/bash

report_dir="$1"

declare -i transparent=0
declare -i informational=0
declare -i breaking=0

while IFS= read -r -d '' file_path
do
  counts=$( jq '.counts' "$file_path" )
  if [ "$counts" != "null" ]; then
    transparent+=$( echo "$counts" | jq '.transparent' )
    informational+=$( echo "$counts" | jq '.informational' )
    breaking+=$( echo "$counts" | jq '.breaking' )
  fi
done <   <( find "$report_dir" -name '*.json' -type f -print0 )

if [ "$breaking" -gt 0 ]; then
  echo "verdict=breaking"
elif [ "$informational" -gt 0 ]; then
  echo "verdict=informational"
elif [ "$transparent" -gt 0 ]; then
  echo "verdict=transparent"
fi