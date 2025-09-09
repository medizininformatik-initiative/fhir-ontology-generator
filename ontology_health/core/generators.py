import json
import os
from typing import Mapping, Dict

import pandas
from pydantic import BaseModel, Field
from tqdm import tqdm

from common.util.log.functions import get_logger
from common.util.project import Project


class CodeSystemTranslationReportLanguage(BaseModel):
    """
    Class representing the translation state of a language of a codesystem
    """

    missing: int = Field(0, description="Number of missing codes")
    percent: float = Field(0, description="Translation percentage")
    severity: str = Field("", description="Severity of translation state")

    codes: Dict[str, bool] = Field(
        default_factory=dict,
        description="Maps each code to a bool indicating translation availability",
    )

    def calc_percent(self, total_codes: int) -> float:
        """
        Calculates the percentage the language has been translated, based on the given codes
        :param total_codes: Total number of codes present in source for this language
        :return: Percentage translated
        """
        self.percent = round(
            self.__get_present_translations_count()
            / (total_codes if total_codes else 1)
            * 100,
            1,
        )
        return self.percent

    def calc_severity(self, code_system: str) -> str:
        """
        Calculates the severity of the translation state
        :param code_system: Code system the severity should be assigned to. Used only for display purposes
        :return: String representing severity
        """
        self.severity = determine_translation_missing_severity(
            code_system, self.percent
        )
        return self.severity

    def calc_missing(self) -> int:
        """
        Calculates the number of codes with missing translations for this language
        :return: Number of codes missing translations
        """
        self.missing = sum(1 for code in self.codes.values() if not code)
        return self.missing

    def __get_present_translations_count(self) -> int:
        """
        Calculates the number of codes **which do have** translations for this language
        :return: Number of codes with translations
        """
        return sum(1 for code in self.codes.values() if code)


class CodeSystemTranslationReport(BaseModel):
    """
    Class representing the translation state of a codesystem.
    """

    languages: Dict[str, CodeSystemTranslationReportLanguage] = Field(
        default_factory=dict, description="Languages with present translations"
    )
    codes_in_total: int = Field(
        0, description="Total number of codes present in this system"
    )
    code_system: str = Field("", description="Code system in question")

    def to_dict(self) -> Dict:
        report = {
            key: value
            for lang in self.languages.keys()
            for key, value in {
                f"Missing {lang}": self.languages[lang].calc_missing(),
                f"{lang} percent": str(
                    self.languages[lang].calc_percent(self.codes_in_total)
                )
                + "%",
                f"State {lang}": self.languages[lang].calc_severity(self.code_system),
            }.items()
        }

        report["Codes in total"] = self.codes_in_total
        return report


def determine_translation_missing_severity(
    codesystem: str, translation_percent: int | float = 0
) -> str:
    """
    Returns a str representing the severity of the translation percent.:
        ❌ : <25%
        ⚠️ : <100%
        ✅ : =100%
    :param codesystem: Used only for display purposes
    :param translation_percent: Translation percent of language
    :return: Translation severity
    """
    logger = get_logger(__name__)
    match translation_percent:
        case _ if 0 <= translation_percent <= 25:
            logger.error(f"{codesystem} has little to none translations")
            return "❌"
        case _ if 25 <= translation_percent < 100:
            logger.warning(f"{codesystem} has not enough translations")
            return "⚠️"
        case _ if translation_percent == 100:
            logger.info(f"{codesystem} is fully translated")
            return "✅"
    return None


class OntologyHealthReportGenerator:
    """
    Class used for generating the ontology health report.
    """

    def __init__(self, project: Project):
        """
        :param project: Project which the health report should be generated for
        """
        self.__project = project
        self.__merged_ontology = self.__project.output.mkdirs("merged_ontology")

    def generate_report(
        self,
        elastic_translation_codeable_concept: bool = True,
        elastic_translation_terminology: bool = True,
    ) -> str:
        """
        Generates the ontology health report as a str.
        Current output format: MD using pandas python module.
        :param elastic_translation_codeable_concept: Include Elastic Search codeable concept files if TRUE
        :param elastic_translation_terminology: Include Elastic Search terminology files if TRUE
        :return: str ontology health report
        """

        report = "# Ontology Health Report\n"

        if elastic_translation_codeable_concept:
            report += "## Missing translations for elastic search codeable concepts\n"
            report += pandas.DataFrame(
                self.generate_es_codeable_concept_translations_health_report()
            ).T.to_markdown()

            report += "\n"

        if elastic_translation_terminology:
            report += "## Missing translations for elastic search terminology\n"
            report += pandas.DataFrame(
                self.generate_es_terminology_translations_health_report()
            ).T.to_markdown()
            report += "\n"

        return report

    def generate_es_codeable_concept_translations_health_report(self) -> dict:
        """
        Generates the codeable concept translation report as a dict.
        :return: dictionary mapping **codesystem name** -> CodeSystemTranslationReport.to_dict()
        """
        elastic_search_folder = self.__merged_ontology / "elastic"
        report: Mapping[str, CodeSystemTranslationReport] = {}

        for file in tqdm(
            [
                file
                for file in os.listdir(elastic_search_folder)
                if file.startswith("onto_es__codeable_concept")
                and file.endswith(".json")
            ]
        ):
            with open(os.path.join(elastic_search_folder, file), "r", encoding="utf-8") as f:
                for line in f.readlines():
                    entry = json.loads(line)
                    if "termcode" not in entry:
                        continue
                    language_codes = list(
                        filter(lambda w: w != "original", entry["display"].keys())
                    )

                    termcode_system = entry["termcode"]["system"]
                    termcode_code = entry["termcode"]["code"]

                    if not report.get(termcode_system):
                        report[termcode_system] = CodeSystemTranslationReport(
                            code_system=termcode_system
                        )

                    for lang in language_codes:
                        if lang not in report[termcode_system].languages:
                            report[termcode_system].languages[lang] = CodeSystemTranslationReportLanguage()

                        report[termcode_system].languages[lang].codes[termcode_code] = (
                            bool(entry["display"][lang])
                        )

                    report[termcode_system].codes_in_total += 1

        summary_dict = {}
        for code_system, code_system_report in report.items():
            summary_dict[code_system] = code_system_report.to_dict()

        return summary_dict

    def generate_es_terminology_translations_health_report(self):
        """
        Generates the terminology translation report as a dict.
        :return: dictionary mapping **codesystem name** -> CodeSystemTranslationReport.to_dict()
        """
        elastic_search_folder = self.__merged_ontology / "elastic"
        report: Mapping[str, CodeSystemTranslationReport] = {}
        for file in tqdm(
            [
                file
                for file in os.listdir(elastic_search_folder)
                if file.startswith("onto_es__ontology") and file.endswith(".json")
            ]
        ):
            with open(
                os.path.join(elastic_search_folder, file), "r", encoding="utf-8"
            ) as f:
                for line in f.readlines():
                    entry = json.loads(line)
                    if "termcode" not in entry:
                        continue
                    language_codes = list(
                        filter(lambda w: w != "original", entry["display"].keys())
                    )

                    termcode_system = entry["terminology"]
                    termcode_code = entry["termcode"]

                    if not report.get(termcode_system):
                        report[termcode_system] = CodeSystemTranslationReport(
                            code_system=termcode_system
                        )
                        for lang in language_codes:
                            report[termcode_system].languages[
                                lang
                            ] = CodeSystemTranslationReportLanguage()

                    for lang in language_codes:
                        report[termcode_system].languages[lang].codes[termcode_code] = (
                            bool(entry["display"][lang])
                        )
                    report[termcode_system].codes_in_total += 1

        summary_dict = {}
        for code_system, code_system_report in report.items():
            summary_dict[code_system] = code_system_report.to_dict()

        return summary_dict
