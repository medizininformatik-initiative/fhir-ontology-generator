import json
import math
import os
import re
import cohort_selection_ontology.resources.fhir as fhir_resource_files
from abc import ABC, abstractmethod
from importlib.resources import files
from pathlib import Path
from typing import List, OrderedDict, Dict, Tuple
from collections import OrderedDict as orderedDict

from common.exceptions import NotFoundError
from common.util.log.functions import get_class_logger


# TODO: Refactor class hierarchy: The ABC only really needs to implement the most basic functionalities, the rest could
#       be implemented by derived classes. Though this is likely unnecessary since the standard implementation covers
#       covers most use cases
class SearchParameterResolver(ABC):
    """
    Abstract class for resolving the search parameters.
    """
    __logger = get_class_logger("SearchParameterResolver")

    def __init__(self):
        self.search_parameters: List[dict] = self._load_all_search_parameters()

    def find_composite_search_parameter(self, search_parameters: OrderedDict[str, dict]) -> dict:
        """
        Finds the composite search parameter for the given search parameters.
        :param search_parameters: search parameters
        :return: the composite search parameter
        :raises ValueError: if the composite search parameter could not be found
        """
        if len(search_parameters) != 2:
            raise ValueError("Only two search parameters are allowed for composite search")
        search_parameter_url_1, search_parameter_url_2 = [param.get("url") for param in search_parameters.values()]
        path_1, path_2 = search_parameters.keys()
        joined_path = f"{path_1}.where({path_2})"
        for composite_search_parameter in [search_parameter for search_parameter in self.search_parameters if
                                           search_parameter.get("type") == "composite"]:
            components = composite_search_parameter.get("component")
            if components[0].get("definition") == search_parameter_url_1 and components[1].get(
                    "definition") == search_parameter_url_2:
                return orderedDict({joined_path: composite_search_parameter})
            if components[0].get("definition") == search_parameter_url_2 and components[1].get(
                    "definition") == search_parameter_url_1:
                return orderedDict({joined_path: composite_search_parameter})
        raise ValueError("Composite search parameter not found")

    def find_search_parameter(self, fhir_path_expressions: List[str]) -> OrderedDict[str, dict]:
        """
        Finds the search parameter for a fhir path expression. Only the shortest expression is considered
        :param fhir_path_expressions: fhir path expressions to be mapped to search parameters
        :return: the search parameter
        :raises ValueError: if the search parameter could not be found
        """
        def shortened_path(fhir_path: str) -> str:
            """Returns the path without its last element."""
            return fhir_path.rsplit(".", 1)[0]

        # int parameter is used to find the shortest expression and not returned in the result
        fhir_path_expressions = [expression for expression in fhir_path_expressions if
                                 not expression.startswith("Extension")]
        fhir_path_expressions = [re.sub(r'^\((.*)\)$', r'\1', expression) for expression in fhir_path_expressions]
        fhir_path_expressions_to_search_parameter: OrderedDict[str, Tuple[dict, int]] = orderedDict(
            [(expression, (None, math.inf)) for expression in fhir_path_expressions]
        )

        try:
            for search_parameter in self.search_parameters:
                expressions = self.get_cleaned_expressions(search_parameter)
                for path_expression in fhir_path_expressions:
                    if path_expression in expressions:
                        resource_type = path_expression.split('.')[0]
                        number_of_relevant_expressions = len(
                            list(filter(lambda x: x.startswith(resource_type), expressions)))
                        if not fhir_path_expressions_to_search_parameter.get(path_expression) or \
                                number_of_relevant_expressions \
                                < fhir_path_expressions_to_search_parameter.get(path_expression)[1]:
                            fhir_path_expressions_to_search_parameter[path_expression] = (search_parameter,
                                                                                          number_of_relevant_expressions)
            result = orderedDict([(key, value[0]) for key, value in fhir_path_expressions_to_search_parameter.items()])
            if missing_search_parameters := [key for key, value in result.items() if not value]:
                if any([" as " in fhir_path_expressions and '.' not in fhir_path_expressions.split("as")[1] for
                        fhir_path_expressions in missing_search_parameters]):
                    result_without_as_cast = self.find_search_parameter([fhir_path_expressions.split(" as ")[0] for
                                                                         fhir_path_expressions in
                                                                         missing_search_parameters])
                    result = orderedDict([(key if key.split(" as ")[0] not in result_without_as_cast else
                                           key.split(" as ")[0],
                                           value if key.split(" as ")[0] not in result_without_as_cast else
                                           result_without_as_cast[key.split(" as ")[0]]) for key, value in result.items()])
                else:
                    missing_search_parameters = [key for key, value in result.items() if not value]

                    # Get search parameters for the shortened paths
                    new_paths = [shortened_path(path) for path in missing_search_parameters]
                    if set(new_paths) == set(missing_search_parameters):
                        raise RecursionError("Exhausted all paths up to their base node without finding a result")
                    result_without_last_path_element = self.find_search_parameter(
                        [shortened_path(path) for path in missing_search_parameters])
                    for path in result.keys():
                        for shortened_path in result_without_last_path_element.keys():
                            if shortened_path in path:
                                result[shortened_path] = result_without_last_path_element[shortened_path]
                                result.pop(path)

                if missing_search_parameters := [key for key, value in result.items() if not value]:
                    raise ValueError(
                        f"Could not find search parameter for [{missing_search_parameters,} {fhir_path_expressions}]. "
                        f"You may need to add a custom search parameter")
            return result
        except (RecursionError, NotFoundError) as err:
            raise NotFoundError(f"Could not find search parameter for expressions {fhir_path_expressions}") from err

    def _load_all_search_parameters(self) -> List[Dict]:
        """
        Loads all search parameters (default and module specific)
        :return: all search parameters
        """
        search_parameters = self._load_default_search_parameters()
        search_parameters.extend(self._load_module_search_parameters())
        return search_parameters

    @abstractmethod
    def _load_module_search_parameters(self) -> List[Dict]:
        pass

    @staticmethod
    def _load_default_search_parameters() -> List[Dict]:
        with (files(fhir_resource_files).joinpath("fhir_search_parameter_definition.json")
                      .open(mode='r', encoding="utf-8") as f):
            search_parameter_definition = json.load(f)
        return [entry['resource'] for entry in search_parameter_definition["entry"]]

    def get_cleaned_expressions(self, search_parameter: dict) -> List[str]:
        """
        Gets the cleaned expressions of a search parameter
        :param search_parameter: the search parameter
        :return: the cleaned expressions
        """
        expressions = search_parameter.get("expression")
        if not expressions:
            return []
        expressions = [self.translate_as_function_to_operand(expression) if not re.match(r"\((.*?)\)", expression) else
                       self.translate_as_function_to_operand(expression[1:-1]) for expression in
                       expressions.split(" | ")]
        expressions = [self.convert_of_type_to_as_operand(expression) for expression in expressions]
        return expressions

    @staticmethod
    def convert_of_type_to_as_operand(expression: str) -> str:
        """
        Converts an of-type expression to an as expression
        :param expression: the expression
        :return: the converted expression
        """
        while ".ofType(" in expression:
            expression = re.sub(r"\.ofType\((.*?)\)", r" as \1", expression)
        return expression

    @staticmethod
    def translate_as_function_to_operand(expression) -> str:
        """
        fhirPath expressions like Observation.value.as(CodeableConcept) are deprecated and should be replaced with
        Observation.value as CodeableConcept
        :param expression: the expression to update
        :return: the updated expression
        """
        while "as(" in expression:
            as_start = expression.find(".as(")
            as_end = expression.find(")", as_start)

            expression = (expression[:as_start] + " as " + expression[as_start + 4:as_end] + expression[as_end + 1:])
            if len(expression) > as_end + 1 and expression[as_end + 1] == ".":
                Exception("Not implemented: Todo: Put operation in round brackets. "
                          "I.e. Observation.(value as CodeableConcept).text")
        return expression


class StandardSearchParameterResolver(SearchParameterResolver):
    def __init__(self, module_path: str | Path):
        self.__module_path = (module_path if isinstance(module_path, Path) else Path(module_path)).resolve()
        super().__init__()

    def _load_module_search_parameters(self) -> List[Dict]:
        """
        Loads module-specific search parameters from JSON files.
        :return: A list of search parameter dictionaries.
        """
        params = []
        search_param_dir_path = self.__module_path / "search_parameter"

        if not search_param_dir_path.exists() or not search_param_dir_path.is_dir():
            return params

        for filename in os.listdir(search_param_dir_path):
            if filename.endswith(".json"):
                file_path = search_param_dir_path / filename
                with open(file_path, mode="r", encoding="utf-8") as f:
                    params.append(json.load(f))

        return params