from MapperDataModel import generate_map
from UiDataModel import TerminologyEntry
from geccoToUI import create_terminology_definition_for, get_categories, IGNORE_CATEGORIES, MAIN_CATEGORIES, \
    GECCO_DATA_SET
from termEntryToExcel import to_excel
from queryTermCodeMapper import to_term_code_node
import os, errno
from os import path
import shutil

GECCO_VERSION = "de.gecco 1.0.3"
MII_LAB_VERSION = "de.medizininformatikinitiative.kerndatensatz.laborbefund 1.0.2"


def mkdir_if_not_exists(directory):
    if not path.isdir(f"./{directory}"):
        try:
            os.system(f"mkdir {directory}")
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise


def download_gecco_profile():
    def add_observationlab_from_mii_to_gecco():
        os.system(f"fhir install {MII_LAB_VERSION} --here")
        shutil.copy("de.medizininformatikinitiative.kerndatensatz.laborbefund#1.0.2/package/Profile-ObservationLab.json"
                    , "de.gecco#1.0.3/package/Profile-ObservationLab.json")

    mkdir_if_not_exists("geccoDataSet")
    mkdir_if_not_exists("mapping")
    mkdir_if_not_exists("csv")
    mkdir_if_not_exists("result")
    saved_path = os.getcwd()
    os.chdir("geccoDataSet")
    os.system(f"fhir install {GECCO_VERSION} --here")
    add_observationlab_from_mii_to_gecco()
    os.chdir(saved_path)


if __name__ == '__main__':
    download_gecco_profile()
    others = TerminologyEntry(None, "CategoryEntry", selectable=False)
    others.display = "Andere"
    category_entries = create_terminology_definition_for(get_categories())
    map_entries = generate_map(category_entries)
    map_entries_file = open("mapping/" + "TermCodeMapping.json", 'w')
    map_entries_file.write(map_entries.to_json())
    term_code_tree = to_term_code_node(category_entries)
    term_code_file = open("mapping/" + "TermCodeTree.json", 'w')
    term_code_file.write(term_code_tree.to_json())
    to_excel(category_entries)
    for category in category_entries:
        if category in IGNORE_CATEGORIES:
            continue
        if category.display in MAIN_CATEGORIES:
            f = open("result/" + category.display.replace("/ ", "") + ".json", 'w')
            f.write(category.to_json())
        else:
            others.children.append(category)
    f = open("result/" + others.display + ".json", 'w')
    f.write(others.to_json())
