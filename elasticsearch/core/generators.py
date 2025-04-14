import os
import json
import uuid
import zipfile
from typing import Mapping
from zipfile import ZipFile
import re

from TerminologService.TermServerConstants import TERMINOLOGY_SERVER_ADDRESS
from TerminologService.valueSetToRoots import logger

from core.TerminologyDesignationResolver import TerminologyDesignationResolver, logger
from model.UiDataModel import RelationalTermcode
from util.codec.json import JSONFhirOntoEncoder

from util.log.functions import get_class_logger
from util.project import Project


class ElasticSearchGenerator:
    __logger = get_class_logger("ElasticSearchGenerator")

    def __init__(self, project: Project):
        self.__project = project
        self.__terminology_resolver = TerminologyDesignationResolver(
            project.input("translation") / "base_translations.json",
            TERMINOLOGY_SERVER_ADDRESS
        )

    @staticmethod
    def __get_contextualized_termcode_hash(context_node: dict, termcode_node: dict, namespace_uuid_str) -> str:
        context_termcode_hash_input = f"{context_node.get('system')}{context_node.get('code')}{context_node.get('version', '')}{termcode_node.get('system')}{termcode_node.get('code')}"
        namespace_uuid = uuid.UUID(namespace_uuid_str)
        return str(uuid.uuid3(namespace_uuid, context_termcode_hash_input))

    @staticmethod
    def __get_termcode_hash(termcode_node: dict, namespace_uuid_str) -> str:
        termcode_hash_input = f"{termcode_node.get('system')}{termcode_node.get('code')}"
        namespace_uuid = uuid.UUID(namespace_uuid_str)
        return str(uuid.uuid3(namespace_uuid, termcode_hash_input))

    @staticmethod
    def __build_crit_set_map(context_termcode_hash_to_crit_set, crit_set_dir, namespace_uuid_str):
        for filename in os.listdir(crit_set_dir):
            with open(os.path.join(crit_set_dir, filename), mode='r', encoding='UTF-8') as file:
                crit_set = json.load(file)

                crit_set_url = crit_set['url']

                for crit in crit_set['contextualized_term_codes']:
                    cont_term_hash = ElasticSearchGenerator.__get_contextualized_termcode_hash(crit[0], crit[1],
                                                                                               namespace_uuid_str=namespace_uuid_str)

                    if cont_term_hash not in context_termcode_hash_to_crit_set:
                        context_termcode_hash_to_crit_set[cont_term_hash] = [crit_set_url]
                    else:
                        context_termcode_hash_to_crit_set[cont_term_hash].append(crit_set_url)

    @staticmethod
    def __get_relation_crit_object(code: str|int, system: dict, context: dict, term_code_info_map: dict, namespace_uuid_str: str,
                                   terminology_resolver: TerminologyDesignationResolver) -> RelationalTermcode:
        """
        Returns the information of a given child/parent node,
        including the contextualized_termcode_hash and the translations

        :param code: code of parent/child node
        :param system: system of parent/child node
        :param context: context of parent/child node
        :param term_code_info_map: dict with all codes, saved based on their contextualized_termcode_hash
        :param namespace_uuid_str: uuid of namespace
        :param terminology_resolver: terminology resolver provides translations based on termcode
        :return: dict[str, dict] with information of the given parent/child node
        """
        term_code = {"code": code, "system": system}
        context_term_code_hash = ElasticSearchGenerator.__get_contextualized_termcode_hash(context, term_code,namespace_uuid_str)

        parent_term_code_info = term_code_info_map[context_term_code_hash]
        parent_context = parent_term_code_info['context']
        parent_term_code = parent_term_code_info['term_code']

        parent_realtional_termcode = RelationalTermcode(
            contextualized_termcode_hash= ElasticSearchGenerator.__get_contextualized_termcode_hash(
                parent_context,
                parent_term_code,
                namespace_uuid_str=namespace_uuid_str
            ),
            display= terminology_resolver.resolve_term(parent_term_code)
        )

        return parent_realtional_termcode

    def __iterate_tree(self, ui_tree_list: dict, term_code_info_map: dict, target_elastic_crit_list: list, context_termcode_hash_to_crit_set: dict,
                       namespace_uuid_str: str, terminology_resolver: TerminologyDesignationResolver):
        """
        Iterates ui tree and complements information about each node
        """
        # For now, we agreed upon just using the first termcode if there are more than one
        children_cut_off = 400

        for ui_tree in ui_tree_list:
            for entry in ui_tree['entries']:
                cur_tree_context = ui_tree['context']
                ui_tree_term_code = {
                    "system": ui_tree['system'],
                    "code": entry['key']
                }

                context_termcode_hash = self.__get_contextualized_termcode_hash(cur_tree_context, ui_tree_term_code,
                                                                                namespace_uuid_str)

                term_code_info = term_code_info_map[context_termcode_hash]

                term_code = term_code_info['term_code']
                context = term_code_info['context']
                selectable = True if term_code_info['children_count'] < children_cut_off else False
                obj = {
                    'hash': context_termcode_hash,
                    'name': term_code['display'],
                    'availability': 0,
                    'terminology': term_code['system'],
                    'termcode': term_code['code'],
                    'selectable': selectable,
                    'context': context,
                    'termcodes': [term_code_info['term_code']],
                    'criteria_sets': [],
                    'display': self.__terminology_resolver.resolve_term(term_code),
                    'parents': [],
                    'children': [],
                    'related_terms': [],
                    'kds_module': term_code_info['module']['display']
                }

                for parent_code in entry['parents']:
                    obj['parents'].append(
                        self.__get_relation_crit_object(
                            parent_code, ui_tree['system'], context,term_code_info_map, namespace_uuid_str, terminology_resolver
                        )
                    )

                for child_code in entry['children']:
                    obj['children'].append(
                        self.__get_relation_crit_object(
                            child_code, ui_tree['system'], context,term_code_info_map, namespace_uuid_str, terminology_resolver
                        )
                    )

                # TODO - Siblings - needs to be considered as it is possible to have siblings from other ui_tree
                # for sibling_code in term_code_info['siblings']:
                #    obj['children'].append(ElasticSearchGenerator.__get_relation_crit_object(child_code,ui_tree['system'],term_code_info_map, namespace_uuid_str=namespace_uuid_str))

                if obj['hash'] in context_termcode_hash_to_crit_set:
                    obj['criteria_sets'] = context_termcode_hash_to_crit_set[obj['hash']]

                target_elastic_crit_list.append(obj)

    def __convert_value_set(self, value_set, termcode_to_valueset, namespace_uuid_str):
        if len(value_set.get("expansion", {}).get("contains", [])) == 0:
            logger.warning(f"Value set [url={value_set.get('url', '<missing>')}] is not expanded or its expansion is "
                           f"empty => Skipping")
            return

        for termcode in value_set['expansion']['contains']:

            termcode_hash_input = f"{termcode['code']}{termcode['system']}"
            namespace_uuid = uuid.UUID(namespace_uuid_str)
            termcode_hash = str(uuid.uuid3(namespace_uuid, termcode_hash_input))

            if termcode_hash not in termcode_to_valueset:
                termcode_to_valueset[termcode_hash] = {
                    "hash": termcode_hash,
                    "termcode":
                        {
                            "code": termcode['code'],
                            "display": termcode['display'],
                            "system": termcode['system'],
                            "version": 2099
                        },
                    "value_sets": [value_set['url']],
                    "display": self.__terminology_resolver.resolve_term(termcode),
                }

            else:
                termcode_to_valueset[termcode_hash]["value_sets"].append(value_set['url'])

    def __write_es_import_to_file(self, current_file_index, current_file_name, json_flat, index_name, max_filesize_mb,
                                  filename_prefix, extension):
        current_file_subindex = 1
        current_file_size = 0

        elastic_dir = self.__project.output("merged_ontology", "elastic")
        with (open(current_file_name, mode='a', encoding='UTF-8') as current_file):
            for obj in json_flat:
                obj_hash = obj['hash']
                del obj['hash']
                current_line = f'{{"index": {{"_index": "{index_name}", "_id": "{obj_hash}"}}}}\n'
                current_file.write(current_line)
                current_file_size += len(current_line)
                current_line = json.dumps(obj, cls=JSONFhirOntoEncoder) + "\n"
                current_file.write(current_line)
                current_file_size += len(current_line)

                if current_file_size > max_filesize_mb * 1024 * 1024:
                    current_file_subindex += 1
                    current_file_name = elastic_dir / (f"{filename_prefix}_{index_name}_{current_file_index}_" +
                                                       f"{current_file_subindex}{extension}")
                    current_file_size = 0
                    current_file.close()
                    current_file = open(current_file_name, mode='w', encoding='UTF-8')

    @staticmethod
    def __write_es_to_file(es_availability_inserts, max_filesize_mb, filename_prefix, extension, write_dir):
        current_file_subindex = 1
        current_file_size = 0

        count = 0

        current_file_name = os.path.join(write_dir, f"{filename_prefix}_{current_file_subindex}{extension}")
        logger.debug(f"writing to file {current_file_name}")
        with open(current_file_name, mode='w+', encoding='UTF-8') as current_file:

            for insert in es_availability_inserts:
                count = count + 1
                current_line = f"{json.dumps(insert, cls=JSONFhirOntoEncoder)}\n"
                current_file.write(current_line)
                current_file_size += len(current_line)

                if current_file_size > max_filesize_mb * 1024 * 1024 and count % 2 == 0:
                    current_file_subindex += 1
                    current_file_name = os.path.join(write_dir, f"{filename_prefix}_{current_file_subindex}{extension}")
                    current_file_size = 0
                    current_file.close()
                    current_file = open(current_file_name, 'w', encoding='UTF-8')
                    logger.debug(f"writing to file {current_file_name}")

    @staticmethod
    def __zip_elastic_files(output_file, work_dir, filename_prefix, extension, include_additional_files):
        with ZipFile(output_file, mode='w', compression=zipfile.ZIP_DEFLATED) as elastic_zip:
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
    def load_termcode_info(self, tree_file_name, namespace_uuid_str) -> Mapping[str, dict]:

        term_code_info_map = {}

        folder = self.__project.output() / "merged_ontology" / "term-code-info"
        pattern = r'_ui_tree_\d+.json'
        filename_prefix = re.sub(pattern, '', tree_file_name)

        with open(folder / f"{filename_prefix}_term_code_info.json", mode='r', encoding="UTF-8") as f:
            term_code_info_list = json.load(f)

            logger.debug(f"Loaded termcode info map from file '{filename_prefix}'")
            for term_code_info in term_code_info_list:
                term_code_hash = self.__get_contextualized_termcode_hash(term_code_info['context'],
                                                                         term_code_info['term_code'],
                                                                         namespace_uuid_str)
                term_code_info_map[term_code_hash] = term_code_info

        return term_code_info_map

    def __get_hashed_tree(self) -> Mapping[str, any]:
        directory = self.__project.input() / "elastic"
        es_onto_tree = {}

        for filename in os.listdir(directory):
            if 'ontology' in filename:
                filepath = os.path.join(directory, filename)

                with open(filepath, mode='r', encoding='utf-8') as file:
                    for line in file:
                        line = line.strip()

                        if line:
                            obj = json.loads(line)

                            if "index" in obj:
                                cur_hash = obj["index"]["_id"]
                            else:
                                es_onto_tree[cur_hash] = {
                                    "availability": 0,
                                    "children": obj["children"]
                                }

        return es_onto_tree

    def __update_availability_on_hash_tree(self, avail_hash_tree, namespace_uuid_str):
        hash_set = set()

        availability_input_dir = self.__project.input("availability")

        with open(availability_input_dir / "stratum-to-context.json") as f:
            stratum_to_context = json.load(f)

        for filename in os.listdir(availability_input_dir):
            if 'measure-report' in filename:
                filepath = availability_input_dir / filename

                with open(filepath, "r") as f:
                    report = json.load(f)

                    for group in report["group"]:
                        for stratifier in group["stratifier"]:
                            if "stratum" in stratifier:
                                strat_code = stratifier["code"][0]["coding"][0]["code"]

                                if strat_code not in stratum_to_context:
                                    continue

                                context = stratum_to_context[strat_code]

                                for stratum in stratifier["stratum"]:
                                    measure_score = stratum["measureScore"]["value"]

                                    if "system" not in stratum["value"]["coding"][0]:
                                        continue

                                    strat_system = stratum["value"]["coding"][0]["system"]
                                    strat_code = stratum["value"]["coding"][0]["code"]

                                    termcode = {
                                        "system": strat_system,
                                        "code": strat_code
                                    }

                                    if context:
                                        hash = ElasticSearchGenerator.__get_contextualized_termcode_hash(
                                            context, termcode, namespace_uuid_str
                                        )

                                        hash_set.add(hash)
                                        if hash in avail_hash_tree:
                                            avail_hash_tree[hash]["availability"] = avail_hash_tree[hash][
                                                                                        "availability"] + measure_score

    @staticmethod
    def __convert_measure_score_to_ranges(measure_score):
        buckets = [0, 10, 100, 1000, 10000, 50000, 100000, 150000, 200000, 1000000]
        return max(b for b in buckets if measure_score >= b)

    @staticmethod
    def __get_avail_sum_for_all_children(parent_id, tree):
        count = tree[parent_id]["availability"]
        for child in tree[parent_id]["children"]:
            count = count + ElasticSearchGenerator.__get_avail_sum_for_all_children(child["contextualized_termcode_hash"],
                                                                                    tree)
        return count

    def generate_elasticsearch_files(self, generate_availability,
                                     namespace_uuid_str='00000000-0000-0000-0000-000000000000', index_name='ontology',
                                     filename_prefix='onto_es_', max_filesize_mb=10,
                                     update_translation_supplements=False):
        generated_ontology_dir = self.__project.output("merged_ontology")

        translations_dir = self.__project.output("translation", "supplements")

        availability_output_dir = self.__project.output("availability")

        extension = '.json'
        ui_tree_dir = generated_ontology_dir / "ui-trees"
        current_file_index = 0

        elastic_dir = generated_ontology_dir / "elastic"
        os.makedirs(elastic_dir, exist_ok=True)

        value_set_dir = generated_ontology_dir / "value-sets"

        context_termcode_hash_to_crit_set = {}
        crit_set_dir = generated_ontology_dir / "criteria-sets"
        self.__build_crit_set_map(context_termcode_hash_to_crit_set, crit_set_dir, namespace_uuid_str)

        self.__terminology_resolver.load_base_designations(ui_tree_dir, value_set_dir)
        self.__terminology_resolver.load_designations(translations_dir, update_translation_supplements)

        if generate_availability:
            logger.info('Generating availability')
            es_availability_inserts = []

            avail_hash_tree = self.__get_hashed_tree()
            logger.debug("Updating availability on hash tree")
            self.__update_availability_on_hash_tree(avail_hash_tree, namespace_uuid_str)

            for key, value in avail_hash_tree.items():
                sum_all_children = self.__get_avail_sum_for_all_children(key, avail_hash_tree)

                insert_hash = {"update": {"_id": key}}
                insert_availability = {
                    "doc": {"availability": self.__convert_measure_score_to_ranges(sum_all_children)}}
                es_availability_inserts.append(insert_hash)
                es_availability_inserts.append(insert_availability)

            self.__write_es_to_file(es_availability_inserts, max_filesize_mb,"es_availability_update",
                                    extension, availability_output_dir)

            return

        logger.info("Generating Elasticsearch term code index documents")
        for filename in os.listdir(ui_tree_dir):
            if filename.endswith(extension):
                current_file = elastic_dir / f"{filename_prefix}_{index_name}_{current_file_index}{extension}"

                with open(ui_tree_dir / filename, mode='r', encoding='UTF-8') as f:
                    json_tree = json.load(f)

                term_code_info_map = self.__load_termcode_info(filename, namespace_uuid_str)
                json_flat = []

                self.__iterate_tree(json_tree, term_code_info_map, json_flat, context_termcode_hash_to_crit_set,
                                    namespace_uuid_str)

                self.__write_es_import_to_file(current_file_index, current_file, json_flat, index_name, max_filesize_mb,
                                               filename_prefix, extension)

                current_file_index = current_file_index + 1

        logger.info("Generate Elasticsearch value set index documents")
        index_name = 'codeable_concept'
        termcode_to_valueset = {}

        current_file = elastic_dir / f"{filename_prefix}_{index_name}_{current_file_index}{extension}"

        for filename in os.listdir(value_set_dir):
            if filename.endswith(extension):
                with open(value_set_dir / filename, mode='r', encoding='UTF-8') as f:
                    value_set = json.load(f)
                    self.__convert_value_set(value_set, termcode_to_valueset, namespace_uuid_str)

        json_flat = list(termcode_to_valueset.values())

        self.__write_es_import_to_file(current_file_index, current_file, json_flat, index_name, max_filesize_mb,
                                       filename_prefix, extension)

