from pathlib import Path
from typing import List, Optional, Any, Mapping, Iterable

from fhir.resources.conceptmap import ConceptMap
from fhir.resources.parameters import Parameters
from fhir.resources.coding import Coding
from fhir.resources.parameters import ParametersParameter
from requests.auth import AuthBase
from typing_extensions import override, deprecated

from cohort_selection_ontology.model.tree_map import TermEntryNode, TreeMap, ContextualizedTermCodeInfo
from sortedcontainers import SortedSet
from itertools import groupby

from cohort_selection_ontology.model.ui_data import TermCode
from common.exceptions import UnsupportedError
from common.util.http.terminology.client import FhirTerminologyClient
from common.util.log.functions import get_logger
from common.util.project import Project


def remove_non_direct_ancestors(parents: List[str], input_map: dict):
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


class CohortSelectionTerminologyClient(FhirTerminologyClient):
    __logger = get_logger("CohortSelectionTerminologyClient")
    POSSIBLE_CODE_SYSTEMS:frozenset[str] = frozenset(["http://loinc.org", "http://snomed.info/sct"])

    __project: Project

    def __init__(
        self,
        project: Project,
        base_url: Optional[str] = None,
        auth: Optional[type[AuthBase]] = None,
        cert: Optional[tuple[str, str]] = None,
        timeout: float = 60,
    ):
        if base_url is None:
            if "ONTOLOGY_SERVER_ADDRESS" in project.env:
                base_url = project.env["ONTOLOGY_SERVER_ADDRESS"]
            else:
                raise ValueError(
                    "Server base URL has to be provided either explicitly through the `base_url` parameter"
                    "or implicitly via environment variable `ONTOLOGY_SERVER_ADDRESS`"
                )
        if cert is None:
            if "SERVER_CERTIFICATE" in project.env and "PRIVATE_KEY" in project.env:
                cert = (
                    Path(project.env["SERVER_CERTIFICATE"]),
                    Path(project.env["PRIVATE_KEY"]),
                )
        super().__init__(base_url, auth, cert, timeout, project.config.http)

    @override
    def expand_value_set(
        self, url: str, version: Optional[str] = None
    ) -> SortedSet[TermCode]:
        """
        Expands a value set and returns a set of term codes contained in the value set.
        :param url: Canonical url of the value set
        :param version: Version of the value set
        :return: Sorted set of the term codes contained in the value set
        """
        term_codes = SortedSet()
        value_set_data = super().expand_value_set(url, version)
        if "expansion" in value_set_data:
            global_version = None
            for parameter in value_set_data["expansion"]["parameter"]:
                if parameter["name"] == "version":
                    global_version = parameter["valueUri"].split("|")[-1]
            if "contains" not in value_set_data["expansion"]:
                self.__logger.debug(
                    f"Value set '{url}' is either not expanded or has an empty expansion"
                )
                return term_codes
            for contains in value_set_data["expansion"]["contains"]:
                system = contains["system"]
                code = contains["code"]
                display = contains["display"]
                if display.isupper():
                    display = display.title()
                if "version" in contains:
                    version = contains["version"]
                else:
                    version = global_version
                term_code = TermCode(system=system, code=code, display=display, version=version)
                term_codes.add(term_code)
        else:
            self.__logger.warning(
                f"Failed to expand value set '{url}' => Returning empty expansion"
            )
            return SortedSet()
        return term_codes

    def create_vs_tree_map(self, canonical_url: str) -> TreeMap:
        """
        Creates a tree of the value set hierarchy utilizing the closure operation.
        :param canonical_url: Canonical URL of the value set
        :return: TreeMap of the value set hierarchy
        """
        self.__logger.debug(f"Generating tree map for value set '{canonical_url}'")
        closure_name = self.create_concept_map()
        vs = self.expand_value_set(canonical_url)
        treemap: TreeMap = TreeMap({}, None, None, None)
        treemap.entries = {term_code.code: TermEntryNode(term_code=term_code) for term_code in vs}
        treemap.system = vs[0].system
        treemap.version = vs[0].version
        try:
            closure_map_data = self.get_closure_map(vs, closure_name)
            if groups := closure_map_data.group:
                if len(groups) > 1:
                    raise UnsupportedError(
                        "Multiple groups in closure map are currently not supported"
                    )
                for group in groups:
                    treemap.system = group.source
                    treemap.version = group.sourceVersion
                    subsumption_map = group.element
                    subsumption_map = {
                        item.code: [target.code for target in item.target]
                        for item in subsumption_map
                    }
                    for code, parents in subsumption_map.items():
                        remove_non_direct_ancestors(parents, subsumption_map)
                    for (
                        node,
                        parents,
                    ) in subsumption_map.items():
                        treemap.entries[node].parents += parents
                        for parent in parents:
                            treemap.entries[parent].children.append(node)
        except Exception as e:
            self.__logger.error(
                f"Failed to generate tree map from value set '{canonical_url}' => Returning empty "
                f"tree map",
                exc_info=e,
                stack_info=True,
            )

        return treemap

    def create_concept_map(self, name: Optional[str] = None):
        """
        Creates an empty concept map for closure operation on the ontology server.
        :param name: (Optional) identifier of the concept map for closure invocation. Defaults to a randomly generated
                     UUID
        :return: Identifier of the created closure
        """
        name = name if name else str(uuid.uuid4())
        parameters = Parameters(
            parameter=[ParametersParameter(name="name", valueString=name)]
        )
        self.closure(parameters)
        return name

    def get_closure_map(
        self, term_codes: Iterable[TermCode], closure_name: str
    ) -> ConceptMap:
        """
        Returns the closure map of a set of term codes.
        :param term_codes: Set of term codes with potential hierarchical relations among them
        :param closure_name: Identifier of the closure table to invoke closure operation on
        :return: Closure map of the term codes
        """
        # FIXME: Workaround for gecco. ValueSets with multiple versions are not supported in closure.
        #  Maybe split by version? Or change Profile to reference ValueSet with single version?
        # Check if concepts from multiple versions of the same code system are present and fail if so since value sets with
        # multiple versions are not supported for now
        for system, versions in map(
            lambda entry: (entry[0], set(map(lambda t: t.version, entry[1]))),
            groupby(term_codes, lambda t: t.system),
        ):
            if len(versions) > 1:
                raise UnsupportedError(
                    f"Concepts from multiple code system versions are currently not supported "
                    f"[url={system}, versions={versions}]"
                )

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
        return self.closure(parameters)

    @deprecated("No longer in use. Consider removing")
    def value_set_json_to_term_code_set(self, response):
        """
        Converts a json response from the ontology server to a set of term codes.
        :param response: json response from the ontology server
        :return: Sorted set of term codes
        """
        term_codes = SortedSet()
        if response.status_code == 200:
            value_set_data = response.json()
            if (
                "expansion" in value_set_data
                and "contains" in value_set_data["expansion"]
            ):
                for contains in value_set_data["expansion"]["contains"]:
                    system = contains["system"]
                    code = contains["code"]
                    display = contains["display"]
                    version = None
                    if "version" in contains:
                        version = contains["version"]
                    term_code = TermCode(system=system, code=code, display=display, version=version)
                    term_codes.add(term_code)
        return term_codes

    def get_term_map(self, value_set_canonical_url: str):
        """
        Get the term entries roots from the terminology server based on the given value set canonical url.
        :param value_set_canonical_url: Canonical url of the valueSet
        :return: Sorted term entry roots of the value set hierarchy
        """
        value_set_canonical_url = value_set_canonical_url.replace("|", "&version=")

        result = self.create_vs_tree_map(value_set_canonical_url)
        if len(result.entries) < 1:
            raise Exception("ERROR", value_set_canonical_url)
        return result

    def get_term_info(
        self, value_set_canonical_url: str
    ) -> List[ContextualizedTermCodeInfo]:
        """
        Get the term info for a given value set canonical url
        :param value_set_canonical_url: The canonical url of the valueSet
        :return: The term info of the value set
        """
        value_set_canonical_url = value_set_canonical_url.replace("|", "&version=")
        term_codes = self.expand_value_set(value_set_canonical_url)
        return [ContextualizedTermCodeInfo(term_code=term_code) for term_code in term_codes]

    def get_termcodes_for_value_set(
        self, value_set_canonical_url: str
    ) -> List[TermCode]:
        """
        Get the term codes from the terminology server based on the given value set canonical url.
        :param value_set_canonical_url: Canonical url of the value set
        :return: Sorted list of term codes of the value set prioritized by the coding system:
        ICD10 > SNOMED CT
        """
        self.__logger.debug(
            f"Retrieving term codes for value set '{value_set_canonical_url}'"
        )
        return list(self.expand_value_set(value_set_canonical_url))

    @staticmethod
    def get_term_code_from_contains(contains):
        """
        Extracts the term code from the contains element of the value set expansion
        :param contains: `contains` element of the value set expansion
        :return: Term code
        """
        system = contains["system"]
        code = contains["code"]
        display = contains["display"]
        term_code = TermCode(system=system, code=code, display=display)
        if system == "http://snomed.info/sct":
            if "designation" in contains:
                for designation in contains["designation"]:
                    if "language" in designation and designation["language"] == "de-DE":
                        term_code.display = designation["value"]
        return term_code

    @staticmethod
    def get_answer_list_code(parameters: Parameters) -> Optional[str]:
        """
        Get the LOINC answer list code from the terminology server based on the lookup response information.
        :param parameters: lookup Parameters instance for the LOINC code
        :return: the answer list code of the LOINC code or `None` if no answer list is available
        """
        if parameters := parameters.parameter:
            for parameter in parameters:
                if parts := parameter.part:
                    next_is_answer_list = False
                    for part in parts:
                        if next_is_answer_list and (valueCode := part.value):
                            return valueCode
                        if (valueCode := part.value) and (valueCode == "answer-list"):
                            next_is_answer_list = True
        return None

    def get_answer_list_vs(self, loinc_code: TermCode) -> Optional[str]:
        """
        Get the answer list value set url from the terminology server based on the LOINC code.
        :param loinc_code: LOINC code to get the answer list for
        :return: URL of the answer list value set or None if no answer list is available
        """
        parameters = self.code_system_lookup(
            "http://loinc.org", loinc_code.code, properties=["answer-list"]
        )
        if answer_list_code := self.get_answer_list_code(parameters):
            return "http://loinc.org/vs/" + answer_list_code
        return None

    # TODO: Refactor should only need the 2nd function
    def pattern_coding_to_termcode(self, element):
        """
        Converts a patternCoding to a term code
        :param element: Element node from the snapshot with a patternCoding
        :return: Term code
        """
        code = element["patternCoding"]["code"]
        system = element["patternCoding"]["system"]
        display = self.get_term_code_display(system, code)
        if display.isupper():
            display = display.title()
        term_code = TermCode(system=system, code=code, display=display)
        return term_code

    def pattern_codeable_concept_to_termcode(self, element):
        """
        Converts a patternCodeableConcept to a term code
        :param element: Element node from the snapshot that is a patternCoding
        :return: Term code
        """
        code = element["code"]
        system = element["system"]
        display = self.get_term_code_display(system, code)
        if display.isupper():
            display = display.title()
        term_code = TermCode(system=system, code=code, display=display)
        return term_code

    @staticmethod
    def get_value_sets_by_path(element_path: str, profile_data: dict) -> List[str]:
        """
        Get the value sets from the profile data based on the given path element.
        :param element_path: Value of path element of the profile
        :param profile_data: Snapshot of the profile
        :return: List of value set URLs or empty list if no value set is available
        """
        value_set = []
        for element in profile_data["snapshot"]["element"]:
            if (
                "id" in element
                and element["path"] == element_path
                and "binding" in element
            ):
                vs_url = element["binding"]["valueSet"]
                if vs_url in ["http://hl7.org/fhir/ValueSet/observation-codes"]:
                    continue
                value_set.append(vs_url)
        return value_set

    def get_term_codes_by_id_from_term_server(
        self, element_id: str, profile_data: dict
    ) -> List[TermCode]:
        # TODO: not used in project. Obsolete?
        """
        Get the term codes from the profile data based on the given id element.
        :param element_id: Value of the id element of the profile
        :param profile_data: Snapshot of the profile
        :return: List of term codes or empty list if no term codes are available
        """
        value_set = ""
        for element in profile_data["snapshot"]["element"]:
            if (
                "id" in element
                and element["id"] == element_id
                and "patternCoding" in element
            ):
                if "code" in element["patternCoding"]:
                    term_code = self.pattern_coding_to_termcode(element)
                    return [term_code]
            if "id" in element and element["id"] == element_id and "binding" in element:
                value_set = element["binding"]["valueSet"]
        if value_set:
            return self.get_termcodes_for_value_set(value_set)
        return []

    def try_get_fixed_code(
        self, element_path: str, profile_data: dict
    ) -> Optional[TermCode]:
        """
        Get the fixed code from the profile data based on the given path element if available.
        :param element_path: Value of the path element of the profile
        :param profile_data: Snapshot of the profile
        :return: Term code or None if no fixed code is available
        """
        system = ""
        code = ""
        for element in profile_data["snapshot"]["element"]:
            if "path" in element and element["path"] == element_path + ".system":
                if "fixedUri" in element:
                    system = element["fixedUri"]
            if "path" in element and element["path"] == element_path + ".code":
                if "fixedCode" in element:
                    code = element["fixedCode"]
            if system and code:
                display = self.get_term_code_display(system, code)
                term_code = TermCode(system=system, code=code, display=display)
                return term_code
        return None

    def get_term_codes_by_path(
        self, element_path: str, profile_data: dict
    ) -> List[TermCode]:
        """
        Get the term codes from the profile data based on the given path element.
        :param element_path: Value of the path element of the profile
        :param profile_data: Snapshot of the profile
        :return:
        """
        # TODO: handle multiple term_codes in patternCoding also consider allowing to resolve multiple value sets here
        value_set = ""

        # This is another case of inconsistent profiling:
        if result := self.try_get_fixed_code(element_path, profile_data):
            return [result]
        for element in profile_data["snapshot"]["element"]:
            if "path" in element and element["path"] == element_path:
                if "patternCoding" in element:
                    if "code" in element["patternCoding"]:
                        term_code = self.pattern_coding_to_termcode(element)
                        return [term_code]
                elif "patternCodeableConcept" in element:
                    for coding in element["patternCodeableConcept"]["coding"]:
                        if "code" in coding:
                            term_code = self.pattern_codeable_concept_to_termcode(
                                coding
                            )
                            return [term_code]
            if (
                "path" in element
                and element["path"] == element_path
                and "binding" in element
            ):
                value_set = element["binding"]["valueSet"]
        if value_set:
            result = self.get_termcodes_for_value_set(value_set)
            return result
        return []

    # TODO duplicated code in valueSetToRoots
    def get_term_code_display(self, system: str, code: str) -> str:
        """
        Get the display of a term code from the terminology server.
        :param system: Code system URL value of the term code
        :param code: Code value of the term code
        :return: Display value of the term code or "" if no display is available
        """
        parameters = self.code_system_lookup(system, code)
        for parameter in parameters.parameter:
            if name := parameter.name:
                if name == "display":
                    return str(parameter.valueString) if parameter.valueString else ""
        return ""

    def get_system_from_code(self, code: str):
        """
        Get the system of a term code from the terminology server based on the code.
        :param code: Code we want to get the system for
        :return: List of PossibleSystems that contain the code or an empty list if no system contains the code
        """
        result = []
        for system in self.POSSIBLE_CODE_SYSTEMS:
            if self.get_term_code_display(system, code):
                result.append(system)
        return result

    @deprecated("Use `CohortSelectionTerminologyClient::search_value_set` instead")
    def get_value_set_definition(self, canonical_url: str) -> dict:
        """
        Get the value set definition from the terminology server based on the canonical address.
        :param canonical_url: Canonical URL of the value set
        :return: Value set definition or None if no value set definition is available
        """
        value_sets = self.search_value_set(canonical_url)
        for vs in value_sets:
            if vs.id is not None:
                return self.get_value_set(vs.id).model_dump()
        self.__logger.warning(
            f"Failed to retrieve value set '{canonical_url}' => Returning empty definition"
        )
        return {}

    # TODO: Replace usages
    @deprecated("Use `CohortSelectionTerminologyClient::expand_value_set` instead")
    def get_value_set_expansion(self, url: str) -> Optional[Mapping[str, Any]]:
        """
        Retrieves the value set expansion from the terminology server
        :param url: Canonical URL of the value set
        :return: JSON data of the value set expansion
        """
        return super().expand_value_set(url)

    # TODO: Check if we can use that for any resource type
    @deprecated("Use `CohortSelectionTerminologyClient::get_value_set` instead")
    def get_value_set_definition_by_id(
        self, value_set_id: str
    ) -> Optional[Mapping[str, Any]]:
        """
        Get the value set definition from the terminology server based on the id.
        :param value_set_id: ID of the value set
        :return: Value set definition or None if no value set definition is available
        """
        return self.get_value_set(value_set_id)