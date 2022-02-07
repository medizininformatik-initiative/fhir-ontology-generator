from FHIRProfileAnalyzer import generate_profiles_for_fhir_dataset
from OpenEHRTemplateAnalyzer import generate_openehr_profiles


def align_by_code(template, profile):
    for key, value in template.annotations.items():
        for term_code in profile.termCodes:
            if key == term_code.code:
                return template.name
            elif value.lower() in term_code.display.lower():
                return template.name
    return None


def align_by_value_set(template, profile):
    for value_set in template.valueSets:
        for fhir_value_set in profile.valueSet:
            if value_set == fhir_value_set:
                return template.name
    return None


def align_fhir_profile_with_template(profile, templates):
    for template in templates:
        if result := align_by_code(template, profile):
            return profile.name, result
        elif result := align_by_value_set(template, profile):
            return profile.name, result
    return profile.name, None


if __name__ == "__main__":
    fhir_profiles = generate_profiles_for_fhir_dataset()
    open_ehr_templates = generate_openehr_profiles()

    # matched = [fhir_profile for fhir_profile in fhir_profiles
    #            if align_fhir_profile_with_template(fhir_profile, open_ehr_templates)]
    # unmatched = [fhir_profile for fhir_profile in fhir_profiles
    #              if not align_fhir_profile_with_template(fhir_profile, open_ehr_templates)]
    # print(unmatched)

    mapping = {k: v for k, v
               in (align_fhir_profile_with_template(fhir_profile, open_ehr_templates)
                   for fhir_profile in fhir_profiles)}
    print(mapping)