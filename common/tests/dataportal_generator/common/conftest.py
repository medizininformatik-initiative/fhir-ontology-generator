from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def resources(request: pytest.FixtureRequest) -> Path:
    """
    Return the path to the resource directory in the module where the requesting test function is located

    :param request: Fixture request
    :return: Path to the resource directory
    :raises FileNotFoundError: if there is no directory ``resources`` in the module
    """
    resources_dir_path = Path(request.module.__file__).parent / "resources"
    if resources_dir_path.exists() and resources_dir_path.is_dir():
        return resources_dir_path
    else:
        raise FileNotFoundError(f"No resources directory @ {repr(resources_dir_path)}")
