import os
import json
import uuid
from zipfile import ZipFile


class ElasticSearchGenerator:
    """
    This class takes a zip file containing json files from an ontology. It iterates through those files and generates
    "json" files that can then be used in the bulk upload of elastic search. Those files will be added to the zipfile.
    """

    def __init__(self):
        pass

    @staticmethod
    def __get_contextualized_termcode_hash(context_node, termcode_node, namespace_uuid_str):
        context_system = context_node['system']
        context_code = context_node['code']
        if 'version' in context_node:
            context_version = context_node['version']
        else:
            context_version = ''

        termcode_system = termcode_node['system']
        termcode_code = termcode_node['code']
        if 'version' in termcode_node:
            termcode_version = termcode_node['version']
        else:
            termcode_version = ''

        context_termcode_hash_input = context_system + \
            context_code + \
            context_version + \
            termcode_system + \
            termcode_code + \
            termcode_version

        namespace_uuid = uuid.UUID(namespace_uuid_str)
        return str(uuid.uuid3(namespace_uuid, context_termcode_hash_input))

    @staticmethod
    def __iterate_tree(node, target, parent, namespace_uuid_str):
        # For now, we agreed upon just using the first termcode if there are more than one
        term_code = node['termCodes'][0]
        obj = {}
        obj['hash'] = ElasticSearchGenerator.__get_contextualized_termcode_hash(node['context'], term_code,
                                                                                namespace_uuid_str=namespace_uuid_str)
        obj['name'] = term_code['display']
        obj['availability'] = 0
        obj['terminology'] = term_code['system']
        obj['termcode'] = term_code['code']
        # Not present in ui_tree files
        # obj['kdsModule'] = term_code['module']
        obj['selectable'] = node['selectable']
        obj['context'] = node['context']
        obj['termcodes'] = node['termCodes']
        # not yet available in ontology generator...
        obj['criteria_sets'] = []
        obj['translations'] = []
        obj['parents'] = []
        obj['children'] = []
        obj['related_terms'] = []
        if parent:
            # For now, we agreed upon just using the first termcode if there are more than one
            parent_term_code = parent['termCodes'][0]
            parent_obj = {}
            parent_obj['name'] = parent_term_code['display']
            parent_obj['contextualized_termcode_hash']\
                = ElasticSearchGenerator.__get_contextualized_termcode_hash(parent['context'], parent_term_code,
                                                                            namespace_uuid_str=namespace_uuid_str)
            obj['parents'].append(parent_obj)
        if len(node['termCodes']) > 1:
            for relatedTerm in node['termCodes']:
                if relatedTerm == term_code:
                    continue
                related_terms_obj = {}
                related_terms_obj['name'] = relatedTerm['display']
                # Currently, the contextualizedtermcodehash is on node-lvl. Related terms will always have the same id.
                # THIS IS A PROBLEM!
                related_terms_obj['contextualized_termcode_hash'] \
                    = ElasticSearchGenerator.__get_contextualized_termcode_hash(node['context'], relatedTerm,
                                                                                namespace_uuid_str=namespace_uuid_str)
                obj['related_terms'].append(related_terms_obj)

        target.append(obj)
        if 'children' in node:
            for child in node['children']:
                for childTermCode in child['termCodes']:
                    child_obj = {}
                    child_obj['name'] = childTermCode['display']
                    child_obj['contextualized_termcode_hash'] \
                        = ElasticSearchGenerator.__get_contextualized_termcode_hash(
                        child['context'], childTermCode, namespace_uuid_str=namespace_uuid_str)
                    obj['children'].append(child_obj)
                ElasticSearchGenerator.__iterate_tree(child, target, node, namespace_uuid_str=namespace_uuid_str)

    @staticmethod
    def generate_elasticsearch_files(input_file,
                                     work_dir='.',
                                     namespace_uuid_str='00000000-0000-0000-0000-000000000000',
                                     index_name='ontology',
                                     filename_prefix='onto_es_',
                                     max_filesize_mb=20):
        extension = '.json'
        zip_folder = 'ontology/backend'

        with ZipFile(input_file, 'r') as backend_zip:
            zip_contents = backend_zip.namelist()

            source_files = [file for file in zip_contents if file.startswith(zip_folder) and file.endswith(extension)]
            current_file_index = 1
            current_file_size = 0

            for source_file in source_files:
                with backend_zip.open(source_file) as f:
                    if work_dir:
                        current_file_name = f"{work_dir}/{filename_prefix}_{current_file_index}{extension}"
                    else:
                        current_file_name = f"{filename_prefix}_{current_file_index}{extension}"
                    json_tree = json.load(f)
                    json_flat = []

                    ElasticSearchGenerator.__iterate_tree(json_tree, json_flat, None,
                                                          namespace_uuid_str=namespace_uuid_str)

                    with open(current_file_name, 'a', encoding='utf-8') as current_file:
                        for obj in json_flat:
                            obj_hash = obj['hash']
                            del obj['hash']
                            current_line = f'{{"index": {{"_index": "{index_name}", "_id": "{obj_hash}"}}}}\n'
                            current_file.write(current_line)
                            current_file_size += len(current_line)
                            current_line = json.dumps(obj) + "\n"
                            current_file.write(current_line)
                            current_file_size += len(current_line)

                            if current_file_size > max_filesize_mb * 1024 * 1024:
                                current_file_index += 1
                                if work_dir:
                                    current_file_name = f"{work_dir}/{filename_prefix}_{current_file_index}{extension}"
                                else:
                                    current_file_name = f"{filename_prefix}_{current_file_index}{extension}"
                                current_file_size = 0
                                current_file.close()
                                current_file = open(current_file_name, 'w')

        with ZipFile(input_file, 'a') as backend_zip:
            # Add the new files to the zipfile
            for root, dirs, files in os.walk(work_dir):
                for file in files:
                    if file.startswith(filename_prefix) and file.endswith(extension):
                        os.chdir(root)
                        backend_zip.write(filename=file, arcname=f"elastic/{file}")
                        os.remove(file)
