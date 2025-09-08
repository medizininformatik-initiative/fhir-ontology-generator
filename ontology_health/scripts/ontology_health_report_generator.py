import argparse
import os

from common.util.log.functions import get_logger
from common.util.project import Project
from ontology_health.core.generators import OntologyHealthReportGenerator

logger = get_logger(__file__)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', type=str,
                        help="Name of the project to generate Elasticsearch file for")
    args = parser.parse_args()

    logger.info("Generating Elasticsearch files")

    project = Project(name=args.project)

    onto_reporter = OntologyHealthReportGenerator(project=project)

    report = onto_reporter.generate_report()

    output_folder = project.output.generated_ontology / "ontology_report"
    os.makedirs(output_folder, exist_ok=True)

    with open(os.path.join(output_folder, "ontology_health_report.md"), "w", encoding="utf-8") as outfile:
        outfile.write(report)

