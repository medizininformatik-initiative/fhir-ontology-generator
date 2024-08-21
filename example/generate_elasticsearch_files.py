import argparse
from core.ElasticSearchBulkGenerator import ElasticSearchGenerator

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--input-file', dest='input_file', type=str, default='merged-ontology/backend.zip', action='store')
    parser.add_argument('-w', '--output-file', dest='output_file', type=str, default='merged-ontology/elastic.zip', action='store')
    parser.add_argument('-i', '--additional-files-directory', dest='additional_files_directory', type=str, default='merged-ontology/elastic-additional-files', action='store')
    args = parser.parse_args()
    ElasticSearchGenerator.generate_elasticsearch_files(input_file=args.input_file, output_file=args.output_file, include_additional_files=args.additional_files_directory)
