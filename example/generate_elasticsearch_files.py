from core.ElasticSearchBulkGenerator import ElasticSearchGenerator

if __name__ == '__main__':
    ElasticSearchGenerator.generate_elasticsearch_files(input_file='mii_core_data_set/ontology/backend.zip')
