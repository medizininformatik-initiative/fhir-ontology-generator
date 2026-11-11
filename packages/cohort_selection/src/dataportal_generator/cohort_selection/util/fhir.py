import re

from fhir.resources.R4B.parameters import Parameters

from common.util.collections import first


def canonical_of(url: str, version: str | None = None) -> str:
    """
    Builds the FHIR canonical from the provided URL and (optional) version as ``<url>[|<version>]``
    """
    return url + (("|" + version) if version else "")


def split_canonical(canonical: str) -> tuple[str, str | None]:
    """
    Splits a FHIR canonical value into its URL and (optional) version component, e.g. ``<url>[|<version>]``
    """
    split = canonical.split("|")
    return split[0], split[1] if len(split) > 1 else None


def extract_designation(parameters: Parameters, language: str, fuzzy=True) -> str | None:
    """
    Helper function for extracting language code specific designation display value from `Parameters` resource
    :param parameters: `Parameters` resource to extract display value from
    :param language: Language code identifying display value to extract
    :param fuzzy: Controls whether fuzzy matching is enabled when matching the languages codes. If `True` matches will
                  be determined using the regex '`^{language}(-\\S+)?$`'
    :return: Either `str` display value or `None` if no designation for language codes exists
    """
    for designation in filter(
        lambda p: p.name == "designation", parameters.parameter or []
    ):
        if part := designation.part:
            # Check if language code is present
            if not (lang := first(lambda p: p.name == "language", part)):
                continue
            designation_language = lang.valueCode
            # Check if usage code is present
            if not (use := first(lambda p: p.name == "use", part)):
                continue
            use_code = use.valueCoding.code
            matches = (
                re.match(rf"^{language}(-\S+)?$", designation_language)
                if fuzzy
                else (language == designation_language)
            )
            if matches and (
                use_code == "display" or use_code == "preferredForLanguage"
            ):
                if not (value := first(lambda p: p.name == "value", part)):
                    continue
                return value.valueString
    return None