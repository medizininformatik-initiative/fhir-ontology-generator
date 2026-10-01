from __future__ import annotations

import os
import uuid
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING, TypeVar
from urllib.parse import urljoin

from fhir.resources.R4B.bundle import Bundle
from fhir.resources.R4B.codesystem import CodeSystem
from fhir.resources.R4B.coding import Coding
from fhir.resources.R4B.conceptmap import ConceptMap
from fhir.resources.R4B.parameters import ParametersParameter, Parameters
from fhir.resources.R4B.valueset import ValueSet, ValueSetExpansionContains
from pydantic import BaseModel, HttpUrl
from requests import Response
from requests.sessions import Session

from dataportal_generator.common.cache import disk_cache_method
from dataportal_generator.common.log.functions import get_logger
from dataportal_generator.common.model.terminology import TermCode, TreeMap, TermEntryNode

if TYPE_CHECKING:
    # Import only for type checking to avoid a circular import with ``model.project``
    from dataportal_generator.common.model.project import Project

_logger = get_logger(__file__)

T = TypeVar("T", bound=BaseModel)

TERM_SRC_PUBLIC_KEY_ENV_VAR = "TERMINOLOGY_SRC_PUBLIC_KEY"
TERM_SRC_PRIVATE_KEY_ENV_VAR = "TERMINOLOGY_SRC_PRIVATE_KEY"


def _check_and_parse_response(resp: Response, res_type_cls: type[T]) -> T:
    resp.raise_for_status()
    return res_type_cls.model_validate_json(resp.content)


def _remove_non_direct_ancestors(parents: list[str], input_map: dict):
    """
    Removes all ancestors of a node that are not direct ancestors.
    :param parents: List of parents of a concept
    :param input_map: Closure map of the value set
    """
    if len(parents) < 2:
        return
    parents_copy = parents.copy()
    for parent in parents_copy:
        if parent in input_map:
            parent_parents = input_map[parent]
            for elem in parents_copy:
                if elem in parent_parents and elem in parents:
                    parents.remove(elem)


def _sum_concept_in_vs_expansion_contains(contains: list[ValueSetExpansionContains]) -> int:
    return sum(1 + (_sum_concept_in_vs_expansion_contains(c.contains) if c.contains else 0) for c in contains)


class TerminologySource:
    _DEFAULT_HEADERS = {
        "Content-Type": "application/fhir+json",
        "Accept": "application/fhir+json"
    }

    def __init__(self, project: Project):
        self.__project = project
        term_src_conf = self.__project.config.terminology_source
        if ssl_conf := term_src_conf.ssl:
            cert = (ssl_conf.public, ssl_conf.private)
        elif (public := os.environ.get(TERM_SRC_PUBLIC_KEY_ENV_VAR)) and (private := os.environ.get(TERM_SRC_PRIVATE_KEY_ENV_VAR)):
            cert = (public, private)
        else:
            cert = None
        self.__base_url = str(term_src_conf.base_url)
        if not self.__base_url.endswith("/"):
            self.__base_url = self.__base_url + "/"
        self.__session = Session()
        self.__session.cert = cert
        self.__session.headers.update(self._DEFAULT_HEADERS)

    def __del__(self):
        if hasattr(self, "_TerminologySource__session"):
            self.__session.close()

    def init_closure(self, closure_name: str | None = None) -> ConceptMap:
        """
        Initializes a closure on the terminology server

        :param closure_name: Name of the closure to initialize. If ``None`` a random UUID will be used
        :return: ``ConceptMap`` instance representing the closure
        """
        name = closure_name if closure_name else str(uuid.uuid4())
        parameters = Parameters(
            parameter=[ParametersParameter(name="name", valueString=name)]
        )
        resp = self.__session.post(urljoin(self.__base_url, "$closure"), data=parameters.model_dump_json())
        return _check_and_parse_response(resp, ConceptMap)

    def closure(self, concepts: Iterable[Coding], closure_name: str | None = None,
                init_closure: bool = True) -> ConceptMap:
        """
        Returns the closure map of a set of term codes.

        :param concepts: Set of concepts with potential hierarchical relations among them
        :param closure_name: Identifier of the closure table to invoke closure operation on
        :param init_closure: If ``True`` a new closure with the provided name will be created
        :return: Closure map of the concepts
        """
        # The name is generated here since the server is not guaranteed to return it in the response
        closure_name = closure_name if closure_name else str(uuid.uuid4())
        if init_closure:
            self.init_closure(closure_name)
        parameters = Parameters(
            parameter=[ParametersParameter(name="name", valueString=closure_name)]
        )
        for c in concepts:
            parameters.parameter.append(
                ParametersParameter(name="concept", valueCoding=c)
            )
        resp = self.__session.post(urljoin(self.__base_url, "$closure"), data=parameters.model_dump_json())
        return _check_and_parse_response(resp, ConceptMap)

    @disk_cache_method(lambda self: Path(f"{self.__project.path}/.cache/terminology/closure"))
    def closure_map(self, system: str, version: str | None, concepts: Iterable[tuple[str, str]]) -> TreeMap:
        """
        Builds a closure table from the provided concepts and returns a tree map of it.

        :param system: Code system URL
        :param version: Code system version
        :param concepts: Iterable of tuples containing code and display values
        :return: ``TreeMap`` object representing the closure table
        """
        term_codes = [TermCode(system=system, code=t[0], display=t[1], version=version) for t in concepts]
        treemap: TreeMap = TreeMap(
            entries={term_code.code: TermEntryNode(term_code=term_code) for term_code in term_codes},
            system=system,
            version=version,
        )
        _logger.debug("Building closure table")
        if groups := self.closure(term_codes, init_closure=True).group:
            if len(groups) > 1:
                raise NotImplementedError(
                    "Multiple groups in closure map are currently not supported."
                )
            _logger.debug("Building tree map")
            for group in groups:
                mapping = group.element
                subsumption_map = defaultdict(list)
                for item in mapping:
                    for target in item.target:
                        if target.code is not None:
                            subsumption_map[item.code].append(target.code)
                        else:
                            _logger.warning(
                                f"Coding [system={group.source}, code={item.code}] "
                                f"has no target coding for system '{group.target}' and will not be "
                                f"added [equivalence={target.equivalence}, "
                                f"comment='{target.comment}']"
                            )
                for parents in subsumption_map.values():
                    _remove_non_direct_ancestors(parents, subsumption_map)
                for (
                        node,
                        parents,
                ) in subsumption_map.items():
                    treemap.entries[node].parents += parents
                    for parent in parents:
                        treemap.entries[parent].children.append(node)
        return treemap

    def value_set(self, url: str | None = None, version: str | None = None, canonical: str | None = None) -> ValueSet | None:
        """
        Searches for matching value sets in the terminology data source

        :param url: URL of the value set. Required unless ``canonical`` is provided
        :param version: (Optional) version of the value set. If ``None`` the latest version is returned
        :param canonical: (Optional) canonical URL of the value set
        :return: The matching ``ValueSet`` resource or ``None`` if not found.
        """
        if canonical:
            split = canonical.split("|", maxsplit=1)
            url = split[0]
            version = split[1] if len(split) > 1 else None
        else:
            assert url is not None, "Either 'url' or 'canonical' must be provided"
        params = {"url": url}
        if version:
            params["version"] = version
        # Relative path since an absolute one would discard any path component of the base URL
        resp = self.__session.get(urljoin(self.__base_url, "ValueSet"), params=params)
        bundle = _check_and_parse_response(resp, Bundle)
        if not bundle.entry:
            return None
        return max((entry.resource for entry in bundle.entry), key=lambda vs: vs.version or "")

    def _expand_value_set_with_offset(self, url: str, version: str | None = None, offset: int = 0) -> ValueSet:
        params = {"url": url}
        if version:
            params["valueSetVersion"] = version
        params["offset"] = offset
        resp = self.__session.get(urljoin(self.__base_url, "ValueSet/$expand"), params=params)
        return _check_and_parse_response(resp, ValueSet)

    def expand_value_set(self, url: str, version: str | None = None) -> ValueSet:
        """
        Expands a value set using the ``$expand`` operation of the terminology data source

        :param url: URL of the value set
        :param version: (Optional) version of the value set. If ``None`` the server determines the version to expand
        :return: ``ValueSet`` resource containing the expansion
        """
        vs = self._expand_value_set_with_offset(url, version, 0)
        expansion = vs.expansion
        total = expansion.total
        offset = _sum_concept_in_vs_expansion_contains(expansion.contains)
        while total > offset:
            vs_part = self._expand_value_set_with_offset(url, version, offset)
            expansion_part = vs_part.expansion
            expansion.contains.extend(expansion_part.contains)
            offset += _sum_concept_in_vs_expansion_contains(expansion_part.contains)
        return vs

    def code_system(self, url: str, version: str | None = None) -> CodeSystem | None:
        """
        Searches for a matching code system in the terminology data source. Only the summary is requested since the
        concepts of (potentially large) code systems are not needed

        :param url: URL of the code system
        :param version: (Optional) version of the code system. If ``None`` the latest version is returned
        :return: The matching ``CodeSystem`` resource (summary) or ``None`` if not found
        """
        params = {"url": url, "_summary": "true"}
        if version:
            params["version"] = version
        resp = self.__session.get(urljoin(self.__base_url, "CodeSystem"), params=params)
        bundle = _check_and_parse_response(resp, Bundle)
        if not bundle.entry:
            return None
        return max((entry.resource for entry in bundle.entry), key=lambda cs: cs.version or "")
