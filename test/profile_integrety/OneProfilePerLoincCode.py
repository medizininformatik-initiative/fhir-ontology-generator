import os
import json


def extract_loinc_code(profile):
    """Extract the LOINC code from the given observation profile."""
    elements = profile.get('differential', {}).get('element', [])
    for element in elements:
        if element.get('id') == "Observation.code.coding:loinc":
            return element.get('patternCoding', {}).get('code')
    return None


def identify_duplicate_loinc_codes(directory):
    """Identify observation profiles with the same LOINC code in a directory."""
    loinc_code_to_profiles = {}  # To store the mapping from LOINC codes to profiles

    # Iterate through each file in the directory
    for filename in os.listdir(directory):
        if filename.endswith("snapshot.json"):
            with open(os.path.join(directory, filename), 'r') as f:
                profile = json.load(f)
                loinc_code = extract_loinc_code(profile)
                if loinc_code:
                    if loinc_code not in loinc_code_to_profiles:
                        loinc_code_to_profiles[loinc_code] = []
                    loinc_code_to_profiles[loinc_code].append(filename)

    # Filter out the LOINC codes that appear in more than one profile
    duplicate_loinc_codes = {code: filenames for code, filenames in loinc_code_to_profiles.items() if
                             len(filenames) > 1}

    return duplicate_loinc_codes


if __name__ == "__main__":
    duplicates = identify_duplicate_loinc_codes(
        "../../example/mii_core_data_set/resources/fdpg_differential/Laboruntersuchung/package/")

    for code, filenames in duplicates.items():
        print(f"LOINC Code: {code}")
        for filename in filenames:
            print(f"    {filename}")
