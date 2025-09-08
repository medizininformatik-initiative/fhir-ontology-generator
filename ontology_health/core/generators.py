import json
import os
from typing import List, Mapping

import pandas
from pydantic import BaseModel
from tqdm import tqdm

from common.util.project import Project


class CodeSystemTranslationReport(BaseModel):
    # code        missing de? en? original?
    missing: Mapping[str, Mapping[str, bool]] = {}


class OntologyHealthReportGenerator:
    def __init__(self, project: Project):
        self.__project = project
        self.__merged_ontology = self.__project.output.mkdirs("merged_ontology")

    def generate_report(
        self,
        elastic_translation_codeable_concept: bool = True,
        elastic_translation_terminology: bool = True,
    )->str:

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

    def generate_es_codeable_concept_translations_health_report(self):

        # load es files
        elastic_search_folder = self.__merged_ontology / "elastic"

        # code_systems = {}
        report: Mapping[str, CodeSystemTranslationReport] = {}

        # es_codeable concept
        for file in [
            file
            for file in os.listdir(elastic_search_folder)
            if file.startswith("onto_es__codeable_concept") and file.endswith(".json")
        ]:
            with open(os.path.join(elastic_search_folder, file), "r") as f:
                for line in tqdm(f.readlines()):
                    entry = json.loads(line)
                    if "termcode" not in entry:
                        continue
                    # print(entry)

                    termcode_system = entry["termcode"]["system"]
                    termcode_code = entry["termcode"]["code"]

                    if not report.get(termcode_system):
                        report[termcode_system] = (
                            CodeSystemTranslationReport()
                        )

                    report[termcode_system].missing[termcode_code] = {
                        "de": bool(entry["display"]["de"]),
                        "en": bool(entry["display"]["en"]),
                    }
        return {
            code_system: {
                "de": sum(1 for code in codes.missing.values() if not code["de"]),
                "en": sum(1 for code in codes.missing.values() if not code["en"]),
                "total": len(codes.missing),
            }
            for code_system, codes in report.items()
        }

    def generate_es_terminology_translations_health_report(self):

        # load es files
        elastic_search_folder = self.__merged_ontology / "elastic"

        # code_systems = {}
        report: Mapping[str, CodeSystemTranslationReport] = {}

        # es_codeable concept
        for file in [
            file
            for file in os.listdir(elastic_search_folder)
            if file.startswith("onto_es__ontology") and file.endswith(".json")
        ]:
            with open(os.path.join(elastic_search_folder, file), "r") as f:
                for line in tqdm(f.readlines()):
                    entry = json.loads(line)
                    if "termcode" not in entry:
                        continue
                    # print(entry)

                    termcode_system = entry["terminology"]
                    termcode_code = entry["termcode"]

                    if not report.get(termcode_system):
                        report[termcode_system] = (
                            CodeSystemTranslationReport()
                        )

                    report[termcode_system].missing[termcode_code] = {
                        "de": bool(entry["display"]["de"]),
                        "en": bool(entry["display"]["en"]),
                    }

        # count

        return {
            code_system: {
                "de": sum(1 for code in codes.missing.values() if not code["de"]),
                "en": sum(1 for code in codes.missing.values() if not code["en"]),
                "total": len(codes.missing),
            }
            for code_system, codes in report.items()
        }
        # write to file
