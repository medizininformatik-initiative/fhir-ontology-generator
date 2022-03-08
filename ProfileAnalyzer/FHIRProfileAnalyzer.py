import json
import os

from FHIRProfileConfiguration import *
from ProfileAnalyzer.ProfileModel import Profile
from model.UiDataModel import TermCode, TerminologyEntry


def remove_resource_name(name_with_resource_name):
    # order matters here!
    resource_names = ["ProfilePatient", "Profile", "LogicalModel", "Condition", "DiagnosticReport", "Observation",
                      "ServiceRequest", "Extension", "ResearchSubject", "Procedure"]
    for resource_name in resource_names:
        name_with_resource_name = name_with_resource_name.replace(resource_name, "")
    return name_with_resource_name


def generate_profiles_for_fhir_dataset():
    profiles = []
    for data_set in core_data_sets:
        if data_set == GECCO:
            data_set = data_set.replace(" ", "#")
            for snapshot in [f"resources\\core_data_sets\\{data_set}\\package\\{f.name}" for f in
                             os.scandir(f"resources\\core_data_sets\\{data_set}\\package") if
                             not f.is_dir() and "-snapshot" in f.name]:
                with open(snapshot, encoding="UTF-8") as json_file:
                    json_data = json.load(json_file)
                    # Care parentheses matter here!
                    if (kind := json_data.get("kind")) and (kind == "logical"):
                        continue
                    if resource_type := json_data.get("type"):
                        if resource_type == "Bundle":
                            continue
                        elif json_data.get("name") == "UncertaintyOfPresence":
                            continue
                module_element_name = remove_resource_name(json_data.get("name"))
                if module_element_name in IGNORE_LIST:
                    continue
                module_element_code = TermCode("mii.abide", module_element_name, module_element_name)
                module_element_entry = TerminologyEntry([module_element_code], "Category", selectable=False,
                                                        leaf=False)
                profiles.append(Profile.generate_profile(module_element_entry, json_data))
    return profiles


if __name__ == "__main__":
    generated_profiles = generate_profiles_for_fhir_dataset()
    # print(len(generated_profiles))
    # for profile in generated_profiles:
    #     print(profile.termCodes[0].code)
