import pytest
from _pytest.fixtures import FixtureRequest

from flattening.core.flattening import FlatteningLookupGenerator
from flattening.model.FlatteningLookupModels import FlatteningLookup

PROJECT_RESOLUTION = "ancestor"


@pytest.fixture
def flattening_lookup_generator(project):
    return FlatteningLookupGenerator(project)


@pytest.fixture
def profile_lookup(
    request: FixtureRequest, package_manager, flattening_lookup_generator
) -> FlatteningLookup:
    """
    Indirect fixture to construct a ``FlatteningLookup`` object for the FHIR ``StructureDefinition`` using its URL
    (``str``-type fixture parameter)

    :return: ``FlatteningLookup`` object
    """
    match request.param:
        case str(v):
            struct_def = package_manager.find_struct_def(v)
            if not struct_def:
                raise FileNotFoundError(
                    f"Structure definition {repr(v)} is not present in package cache"
                )
            return flattening_lookup_generator.generate_flattening_lookup_for_profile(
                struct_def
            )
        case _ as param:
            raise ValueError(
                f"Fixture 'profile_lookup' expects a parameter of type {repr(str)} but got {type(param)}"
            )
