import uuid
from collections import defaultdict
from collections.abc import Iterable
from typing import TypeVar
from urllib.parse import urljoin
from fhir.resources.R4B.coding import Coding
from fhir.resources.R4B.conceptmap import ConceptMap
from fhir.resources.R4B.parameters import ParametersParameter, Parameters
from pydantic import BaseModel
from requests import Response
from requests.sessions import Session

from dataportal_generator.common.log.functions import get_logger
from dataportal_generator.common.model.terminology import TermCode, TreeMap, TermEntryNode

_logger = get_logger(__file__)

T = TypeVar("T", bound=BaseModel)


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


class TerminologySource:
    _DEFAULT_HEADERS = {
        "Content-Type": "application/fhir+json",
        "Accept": "application/fhir+json"
    }

    def __init__(self, base_url: str, **kwargs):
        self.__base_url = base_url
        if not "headers" in kwargs:
            kwargs["headers"] = self._DEFAULT_HEADERS
        self.__session = Session(**kwargs)

    def __del__(self):
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
        resp = self.__session.post(urljoin(self.__base_url, "$closure"), body=parameters.model_dump_json())
        return _check_and_parse_response(resp, ConceptMap)

    def closure(self, term_codes: Iterable[TermCode], closure_name: str | None = None,
                init_closure: bool = True) -> ConceptMap:
        """
        Returns the closure map of a set of term codes.

        :param term_codes: Set of term codes with potential hierarchical relations among them
        :param closure_name: Identifier of the closure table to invoke closure operation on
        :param init_closure: If ``True`` a new closure with the provided name will be created
        :return: Closure map of the term codes
        """
        if init_closure:
            c = self.init_closure(closure_name)
            if not closure_name:
                closure_name = c.name
        parameters = Parameters(
            parameter=[ParametersParameter(name="name", valueString=closure_name)]
        )
        for term_code in term_codes:
            value_coding = Coding(
                system=term_code.system,
                code=term_code.code,
                display=str(term_code.display),
            )
            if term_code.version:
                value_coding.version = term_code.version
            parameters.parameter.append(
                ParametersParameter(name="concept", valueCoding=value_coding)
            )
        resp = self.__session.post(urljoin(self.__base_url, "$closure"), body=parameters.model_dump_json())
        return _check_and_parse_response(resp, ConceptMap)

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
            {term_code.code: TermEntryNode(term_code=term_code) for term_code in term_codes},
            None,
            system,
            version
        )
        _logger.debug("Building closure table")
        if groups := self.closure(term_codes, init_closure=True):
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
