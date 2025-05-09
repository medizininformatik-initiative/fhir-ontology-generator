import os
from pathlib import Path
from typing import List

from common.util.fhir.structure_definition import is_structure_definition


def generate_snapshots(package_dir: str, prerequisite_packages: List[str] = None, reinstall: bool = False):
    """
    Generates the snapshots for all the profiles in the package_dir folder and its sub folders
    :param prerequisite_packages: list of prerequisite packages
    :param package_dir: directory of the package
    :param reinstall: if true the required packages will be reinstalled
    :raises FileNotFoundError: if the package directory could not be found
    :raises NotADirectoryError: if the package directory is not a directory
    """
    def install_prerequisites():

        if os.path.exists("package.json"):
            os.remove("package.json")

        os.system("fhir install hl7.fhir.r4.core")

        for package in prerequisite_packages:
            if os.path.exists("package.json"):
                os.remove("package.json")
            os.system(f"fhir install {package} --here")

    def generate_snapshot(file: str | Path):
        os.system(f"fhir push {file}")
        os.system(f"fhir snapshot")
        os.system(f"fhir save {file[:-5]}-snapshot.json")

    prerequisite_packages = prerequisite_packages if prerequisite_packages else []
    if not os.path.exists(package_dir):
        raise FileNotFoundError(f"Package directory does not exist: {package_dir}")
    if not os.path.isdir(package_dir):
        raise NotADirectoryError("package_dir must be a directory")
    saved_path = os.getcwd()
    if reinstall or not (os.path.exists("fhirpkg.lock.json") and os.path.exists("package.json")):
        install_prerequisites()
    # module folders
    for folder in [f.path for f in os.scandir(package_dir) if f.is_dir()]:
        if folder.endswith("dependencies"):
            continue
        os.chdir(f"{folder}")
        # generates snapshots for all differential in the package if they do not exist
        for file in [f for f in os.listdir('.') if
                     os.path.isfile(f) and is_structure_definition(f) and "-snapshot" not in f
                     and f[:-5] + "-snapshot.json" not in os.listdir('.')]:
            generate_snapshot(file)
        if not os.path.exists("extension"):
            os.chdir(saved_path)
            continue
        os.chdir(f"extension")
        for file in [f for f in os.listdir('.') if
                     os.path.isfile(f) and is_structure_definition(f) and "-snapshot" not in f
                     and f[:-5] + "-snapshot.json" not in os.listdir('.')]:
            generate_snapshot(file)
        os.chdir(saved_path)