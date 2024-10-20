import argparse
from core.ElasticSearchBulkGenerator import ElasticSearchGenerator

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--ontology_dir', type=str)
    parser.add_argument( '--availability_input_dir', type=str)
    parser.add_argument('--generate_availability', action='store_true')
    args = parser.parse_args()
    ElasticSearchGenerator.generate_elasticsearch_files(ontology_dir=args.ontology_dir, generate_availability=args.generate_availability, availability_input_dir=args.availability_input_dir)
