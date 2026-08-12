"""
Helpers for building minimal, synthetic profiles for flattening unit tests.
"""

import fhir.resources.R4B.structuredefinition
from fhir.resources.R4B.elementdefinition import ElementDefinition

from common.model.fhir.nav_structure_definition import (
    NavStructureDefinition,
)


def build_profile(
    resource_type: str,
    elements: list[ElementDefinition],
    url: str = None,
) -> NavStructureDefinition:
    """
    Builds a minimal navigable profile snapshot: a synthetic root element for
    ``resource_type`` plus whatever ``elements`` the test needs.

    :param resource_type: FHIR resource type of the profile (e.g. "Observation")
    :param elements: element definitions to include, in addition to the root element
    :param url: canonical URL of the profile, defaults to a synthetic example.org URL
    :return: navigable profile snapshot usable wherever a ``StructureDefinitionSnapshot`` is expected
    """
    root = ElementDefinition(id=resource_type, path=resource_type)
    return NavStructureDefinition(
        url=url or f"http://example.org/fhir/StructureDefinition/{resource_type}",
        name=resource_type,
        status="active",
        kind="resource",
        abstract=False,
        type=resource_type,
        snapshot=fhir.resources.R4B.structuredefinition.StructureDefinitionSnapshot(
            element=[root, *elements]
        ),
    )
