
import pytest

from flattening.core.flattening import FlatteningLookupGenerator


@pytest.fixture
def flattening_lookup_generator(project):
    return FlatteningLookupGenerator(project)

