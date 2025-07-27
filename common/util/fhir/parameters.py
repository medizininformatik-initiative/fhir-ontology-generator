from collections.abc import Mapping

from fhir.resources.R4B.element import Element
from fhir.resources.R4B.parameters import Parameters, ParametersParameter


def summarize_parameters(parameters: Parameters, pattern: Mapping[str, str]) -> str:
    """
    Build a summary string for the given Parameters resource instance

    :param parameters: Parameters resource instance
    :param pattern: Mapping of parameter name values to include to the expected ParametersParameter's value element name
    :return: String representing a comma-separated list of parameter names adn their values
    """
    params = []
    for parameter in parameters.parameter:
        parameter: ParametersParameter
        value_element_name = pattern.get(parameter.name)
        if value_element_name and hasattr(parameter, value_element_name):
            value_element = getattr(parameter, value_element_name)
            match value_element:
                case Element() as elem:
                    value_str = elem.model_dump_json()
                case str() as s:
                    value_str = f"'{s}"
                case _ as other:
                    value_str = str(other)
            params.append(f"{parameter.name}={value_str}")
    return ", ".join(params)
