import pytest

from flattening.core.flattening import FlatteningLookupGenerator


PROJECT_RESOLUTION = "ancestor"


@pytest.fixture
def flattening_lookup_generator(project):
    return FlatteningLookupGenerator(project)

