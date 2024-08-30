import os
import json
import uuid
import zipfile
from zipfile import ZipFile


class ElasticSearchGenerator:
    """
    This class takes a zip file containing json files from an ontology. It iterates through those files and generates
    "json" files that can then be used in the bulk upload of elastic search. Those files will be added to the zipfile.
    """

    def __init__(self):
        pass

    @staticmethod
    def __get_contextualized_termcode_hash(context_node: dict, termcode_node: dict, namespace_uuid_str):

        context_termcode_hash_input = f"{context_node.get('system')}{context_node.get('code')}{context_node.get('version', '')}{termcode_node.get('system')}{termcode_node.get('code')}"

        namespace_uuid = uuid.UUID(namespace_uuid_str)
        return str(uuid.uuid3(namespace_uuid, context_termcode_hash_input))

    @staticmethod
    def __get_termcode_hash(termcode_node: dict, namespace_uuid_str):

        termcode_hash_input = f"{termcode_node.get('system')}{termcode_node.get('code')}"

        namespace_uuid = uuid.UUID(namespace_uuid_str)
        return str(uuid.uuid3(namespace_uuid, termcode_hash_input))

    @staticmethod
    def __build_crit_set_map(context_termcode_hash_to_crit_set, crit_set_dir, namespace_uuid_str):

        for filename in os.listdir(crit_set_dir):

            with open(f'{crit_set_dir}/{filename}', "r") as file:
                crit_set = json.load(file)

                crit_set_url = crit_set['url']

                for crit in crit_set['contextualized_term_codes']:
                    cont_term_hash = ElasticSearchGenerator.__get_contextualized_termcode_hash(crit[0], crit[1], namespace_uuid_str=namespace_uuid_str)

                    if cont_term_hash not in context_termcode_hash_to_crit_set:
                        context_termcode_hash_to_crit_set[cont_term_hash] = [crit_set_url]
                    else:
                        context_termcode_hash_to_crit_set[cont_term_hash].append(crit_set_url)

    @staticmethod
    def __get_relation_crit_object(code, system, term_code_info_map, namespace_uuid_str):

        term_code_hash = ElasticSearchGenerator.__get_termcode_hash(
            {"code": code, "system": system}, namespace_uuid_str=namespace_uuid_str)


        parent_term_code_info = term_code_info_map[term_code_hash]
        parent_context = parent_term_code_info['context']
        parent_term_code = parent_term_code_info['term_code']

        return {'name': parent_term_code_info['term_code']['display'],
                      'contextualized_termcode_hash': ElasticSearchGenerator.__get_contextualized_termcode_hash(
                          parent_context, parent_term_code,
                          namespace_uuid_str=namespace_uuid_str)}


    @staticmethod
    def __iterate_tree(ui_tree_list, term_code_info_map, target_elastic_crit_list, context_termcode_hash_to_crit_set, namespace_uuid_str):
        # For now, we agreed upon just using the first termcode if there are more than one

        children_cut_off = 400

        for  ui_tree in ui_tree_list:

            for entry in ui_tree['entries']:

                term_code_hash = ElasticSearchGenerator.__get_termcode_hash({"code": entry['key'], "system": ui_tree['system']},namespace_uuid_str)
                term_code_info = term_code_info_map[term_code_hash]

                term_code = term_code_info['term_code']
                selectable = True if term_code_info['children_count']  < children_cut_off else False
                obj = {
               'hash': ElasticSearchGenerator.__get_contextualized_termcode_hash(term_code_info['context'], term_code, namespace_uuid_str),
               'name': term_code['display'],
               'availability': 0,
               'terminology': term_code['system'],
               'termcode': term_code['code'],
               'selectable': selectable,
               'context': term_code_info['context'],
               'termcodes': [term_code_info['term_code']],
               'criteria_sets': [],
               'translations': [],
               'parents': [],
               'children': [],
               'related_terms': [],
               'kdsModule': term_code_info['module']['display']
               }

                for parent_code in entry['parents']:
                    obj['parents'].append(ElasticSearchGenerator.__get_relation_crit_object(parent_code,ui_tree['system'],term_code_info_map,namespace_uuid_str))

                for child_code in entry['children']:
                    obj['children'].append(ElasticSearchGenerator.__get_relation_crit_object(child_code,ui_tree['system'],term_code_info_map,namespace_uuid_str))

                # TODO - Siblings - needs to be considered as it is possible to have siblings from other ui_tree
                #for sibling_code in term_code_info['siblings']:
                #    obj['children'].append(ElasticSearchGenerator.__get_relation_crit_object(child_code,ui_tree['system'],term_code_info_map, namespace_uuid_str=namespace_uuid_str))

                if obj['hash'] in context_termcode_hash_to_crit_set:
                    obj['criteria_sets'] = context_termcode_hash_to_crit_set[obj['hash']]

                target_elastic_crit_list.append(obj)

    @staticmethod
    def __convert_value_set(value_set, termcode_to_valueset, namespace_uuid_str):

        for termcode in value_set['expansion']['contains']:

            termcode_hash_input = f"{termcode['code']}{termcode['system']}"
            namespace_uuid = uuid.UUID(namespace_uuid_str)
            termcode_hash = str(uuid.uuid3(namespace_uuid, termcode_hash_input))

            if termcode_hash not in termcode_to_valueset:
                termcode_to_valueset[termcode_hash] = {"hash": termcode_hash, "termcode": {"code": termcode['code'],
                                                                                           "display": termcode[
                                                                                               'display'],
                                                                                           "system": termcode['system'],
                                                                                           "version": 2099},
                                                       "value_sets": [value_set['url']]}

            else:
                termcode_to_valueset[termcode_hash]["value_sets"].append(value_set['url'])

    @staticmethod
    def __write_es_import_to_file(current_file_index, current_file_name, json_flat, index_name, max_filesize_mb,
                                  filename_prefix, extension,
                                  ontology_dir):
        current_file_subindex = 1
        current_file_size = 0

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
                    current_file_subindex += 1
                    current_file_name = f"{ontology_dir}/elastic/{filename_prefix}_{index_name}_{current_file_index}_{current_file_subindex}{extension}"
                    current_file_size = 0
                    current_file.close()
                    current_file = open(current_file_name, 'w')

    @staticmethod
    def __zip_elastic_files(output_file, work_dir, filename_prefix, extension, include_additional_files):
        with ZipFile(output_file, 'w', zipfile.ZIP_DEFLATED) as elastic_zip:
            # Add the new files to the zipfile
            for root, dirs, files in os.walk(work_dir):
                for file in files:
                    if file.startswith(filename_prefix) and file.endswith(extension):
                        os.chdir(root)
                        elastic_zip.write(filename=file, arcname=f"{file}")
                        os.remove(file)
            # Add files from additional folders if any
            if include_additional_files:
                for root, dirs, files in os.walk(include_additional_files):
                    for file in files:
                        file_path = os.path.join(root, file)
                        elastic_zip.write(file_path, os.path.relpath(file_path, include_additional_files))

    @staticmethod
    def load_termcode_info(ontology_dir, tree_file_name, namespace_uuid_str):

        term_code_info_map = {}

        folder = f'{ontology_dir}/term-code-info'
        filename_prefix = tree_file_name.replace("_tree.json", "")

        with open(f"{folder}/{filename_prefix}_term_code_info.json", 'r') as f:
            print(f"{folder}/{filename_prefix}_term_code_info.json")

            term_code_info_list = json.load(f)

            print(f"loaded termcode info map from file {filename_prefix}")
            for term_code_info in term_code_info_list:
                term_code_hash = ElasticSearchGenerator.__get_termcode_hash(term_code_info['term_code'],namespace_uuid_str )
                term_code_info_map[term_code_hash] = term_code_info

        return term_code_info_map


    @staticmethod
    def generate_elasticsearch_files(ontology_dir,
                                     work_dir='.',
                                     namespace_uuid_str='00000000-0000-0000-0000-000000000000',
                                     index_name='ontology',
                                     filename_prefix='onto_es_',
                                     max_filesize_mb=20):
        extension = '.json'
        folder = f'{ontology_dir}/ui-trees'
        current_file_index = 0

        elastic_dir = f'{ontology_dir}/elastic'
        os.makedirs(elastic_dir, exist_ok=True)

        context_termcode_hash_to_crit_set = {}
        crit_set_dir = f'{ontology_dir}/criteria-sets'
        ElasticSearchGenerator.__build_crit_set_map(context_termcode_hash_to_crit_set, crit_set_dir, namespace_uuid_str)

        for filename in os.listdir(folder):

            if filename.endswith(extension):
                current_file_name = f"{ontology_dir}/elastic/{filename_prefix}_{index_name}_{current_file_index}{extension}"

                with open(f"{folder}/{filename}", 'r') as f:
                    print(f"{folder}/{filename}")
                    json_tree = json.load(f)


                term_code_info_map = ElasticSearchGenerator.load_termcode_info(ontology_dir, filename, namespace_uuid_str)
                json_flat = []

                ElasticSearchGenerator.__iterate_tree(json_tree, term_code_info_map, json_flat,context_termcode_hash_to_crit_set,namespace_uuid_str)

                ElasticSearchGenerator.__write_es_import_to_file(current_file_index, current_file_name, json_flat,
                                                                 index_name,
                                                                 max_filesize_mb, filename_prefix, extension,
                                                                 ontology_dir)

                current_file_index = current_file_index + 1

        # Generate import from value-set files
        folder = f'{ontology_dir}/value-sets'
        index_name = 'codeable_concept'

        termcode_to_valueset = {}

        current_file_name = f"{ontology_dir}/elastic/{filename_prefix}_{index_name}_{current_file_index}{extension}"

        for filename in os.listdir(folder):

            if filename.endswith(extension):


                with open(f'{folder}/{filename}', 'r') as f:
                    value_set = json.load(f)

                ElasticSearchGenerator.__convert_value_set(value_set, termcode_to_valueset, namespace_uuid_str)


        json_flat = list(termcode_to_valueset.values())

        ElasticSearchGenerator.__write_es_import_to_file(current_file_index, current_file_name, json_flat, index_name,
                                                         max_filesize_mb, filename_prefix,
                                                         extension,
                                                         ontology_dir)

        # ElasticSearchGenerator.__zip_elastic_files(output_file, work_dir, filename_prefix, extension, include_additional_files)
