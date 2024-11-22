import argparse
from email.policy import default

from core.ElasticSearchBulkGenerator import ElasticSearchGenerator
from core.StrucutureDefinitionParser import parse

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--ontology_dir', type=str)
    parser.add_argument('--availability_input_dir', type=str)
    parser.add_argument('--generate_availability', action='store_true')
    parser.add_argument('--code_system_translations_folder', type=str, default='example/code_systems_translations')
    parser.add_argument('--base_translation_config', type=str,
                        default='example/fdpg-ontology/resources/translation/base_translations.json')
    parser.add_argument('--update_translation_supplements', action='store_true')

    args = parser.parse_args()
    ElasticSearchGenerator.generate_elasticsearch_files(ontology_dir=args.ontology_dir,
                                                        generate_availability=args.generate_availability,
                                                        availability_input_dir=args.availability_input_dir,
                                                        code_system_translations_folder=args.code_system_translations_folder,
                                                        base_translation_conf=args.base_translation_config,
                                                        update_translation_supplements=args.update_translation_supplements
                                                        )
