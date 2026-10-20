#!/bin/bash

re='^v([0-9]+)\.([0-9]+)\.([0-9]+)(-(.+))?'

parse_release_tag () {
  if [[ "$release_tag" =~ "$re" ]]; then
    local major="${BASH_REMATCH[1]}"
    local minor="${BASH_REMATCH[2]}"
    local patch="${BASH_REMATCH[3]}"

    echo "$major.$minor.$patch"
  else
    echo "Invalid release tag: $release_tag" >&2
    exit 1
  fi
}

IFS="." read -r -a past_version <<< "$1"
IFS="." read -r -a curr_version <<< "$2"
diff_verdict="$3"

declare -i past_major="${past_version[0]}"
declare -i curr_major="${curr_version[0]}"

if [ "$diff_verdict" == "breaking" ] && [ $past_major -ge $curr_major ]; then
  echo "Breaking changes detected in a non-major version bump" >&2
  exit 1
fi