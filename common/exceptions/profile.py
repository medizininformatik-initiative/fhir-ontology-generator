from typing import Optional

from fhir.resources.R4B.structuredefinition import StructureDefinition

from common.exceptions import NotFoundError
from unit.common.util.fhir.conftest import profile


class MissingProfileError(NotFoundError):
    pass

class MissingElementError(NotFoundError):
    pass

class NoSuchElemDefError(NotFoundError):
    def __init__(self, profile: str | StructureDefinition, id: Optional[str] = None, path: Optional[str] = None, *args):
        if not id and not path:
            raise ValueError("One of parameter `id` or `path` has to be provided")
        profile_url = profile if isinstance(profile, str) else profile.url
        super().__init__(f"No element definition with {'ID' if id else 'path'} '{id if id else path}' in profile '{profile_url}'", *args)