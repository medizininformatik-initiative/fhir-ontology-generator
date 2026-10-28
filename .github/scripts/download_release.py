import subprocess
import sys

from common.util.project import Project

if __name__ == "__main__":
    project = Project(name=sys.argv[1])
    repository = sys.argv[2]

    if restore_ver := project.config.terminology.use_release:
        print(f"Downloading restore version {restore_ver!r}")
        subprocess.check_output(
            ["gh", "release", "download", restore_ver,
             "--repo", repository,
             "--dir", str(project.input.mkdirs("restore").absolute())],
        )