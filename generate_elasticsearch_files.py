import argparse

from core.ElasticSearchBulkGenerator import ElasticSearchGenerator
from util.log.functions import get_logger
from util.project import Project

logger = get_logger(__file__)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', type=str,
                        help="Name of the project to generate Elasticsearch file for")
    parser.add_argument('--generate_availability', action='store_true')
    parser.add_argument('--update_translation_supplements', action='store_true')

    args = parser.parse_args()

    logger.info("Generating Elasticsearch files")

    project = Project(name=args.project)

    generator = ElasticSearchGenerator(project)
    generator.generate_elasticsearch_files(generate_availability=args.generate_availability,
                                           update_translation_supplements=args.update_translation_supplements)
