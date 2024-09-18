import argparse
from core.ElasticSearchBulkGenerator import ElasticSearchGenerator

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--ontology_dir', type=str)
    args = parser.parse_args()
    ElasticSearchGenerator.generate_elasticsearch_files(ontology_dir=args.ontology_dir)


