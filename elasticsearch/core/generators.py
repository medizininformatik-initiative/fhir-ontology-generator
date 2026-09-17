import os
import json
import shutil
import uuid
from pathlib import Path
from typing import Mapping, Any, Callable, TypeVar
import re

from cohort_selection_ontology.model.ui_data import RelationalTermcode
from common.util.codec.json import JSONFhirOntoEncoder
from data_selection_extraction.model.profile_tree import ProfileTreeNode, ProfileTreeTA
from elasticsearch.core.resolvers.designation import TerminologyDesignationResolver

from common.util.log.functions import get_logger
from common.util.project import Project
from elasticsearch.model.profile_index import ProfileIndexDocument

_logger = get_logger(__file__)


########################################################################################################################
# Serialization functions
########################################################################################################################


def _ontology_doc_ser(_, doc: Any) -> tuple[bytes, bytes]:
    obj_hash = doc["hash"]
    del doc["hash"]
    action_and_metadata_d = (
        f'{{"index": {{"_index": "ontology", "_id": "{obj_hash}"}}}}\n'.encode("utf-8")
    )
    doc_b = (json.dumps(doc, cls=JSONFhirOntoEncoder) + "\n").encode("utf-8")
    return action_and_metadata_d, doc_b


def _codeable_concept_doc_ser(_, doc: Any) -> tuple[bytes, bytes]:
    obj_hash = doc["hash"]
    del doc["hash"]
    action_and_metadata_d = (
        f'{{"index": {{"_index": "codeable_concept", "_id": "{obj_hash}"}}}}\n'.encode(
            "utf-8"
        )
    )
    doc_b = (json.dumps(doc, cls=JSONFhirOntoEncoder) + "\n").encode("utf-8")
    return action_and_metadata_d, doc_b


def _profile_doc_ser(idx: int, doc: ProfileIndexDocument) -> tuple[bytes, bytes]:
    action_and_metadata_b = (
        f'{{"index": {{"_index": "profile", "_id": "{idx}"}}}}\n'.encode("utf-8")
    )
    doc_bytes_b = (doc.model_dump_json() + "\n").encode(encoding="utf-8")
    return action_and_metadata_b, doc_bytes_b


########################################################################################################################


T = TypeVar("T")


def _write_es_documents(
    dst: Path,
    file_name_prefix: str,
    index_name: str,
    documents: list[T],
    serializer: Callable[[int, T], tuple[bytes, bytes]],
    max_doc_cnt: int = 10_000,
    max_file_size_mb: int = 10,
):
    """
    Serializes list of objects as Elasticsearch index documents and writes them as bulk import NDJSON files to the disk.
    A new files is created if either ``max_doc_count`` or ``max_file_size_mb`` is exceeded

    :param dst: Path to the destination directory
    :param file_name_prefix: Name prefix of the NDJSON files
    :param index_name: Name of the Elasticsearch index the documents should be uploaded to
    :param documents: List of objects that are part of the bulk import
    :param serializer: Callable taking in the index of the object in the list and the object itself. It should return a
                       tuple where the first entry is the action JSON object and the second the serialized data to index
    :param max_doc_cnt: Maximum number of documents to be part of a single NDJSON file
    :param max_file_size_mb: Maximum NDJSON file size (in MB)
    """
    if not documents:
        _logger.warning(f"No documents to write for index {repr(index_name)}")
        return
    max_file_size_bytes = max_file_size_mb * 1024 * 1024
    current_file_subindex = 0
    current_file_size = 0
    current_doc_cnt = 0

    fd = (dst / f"{file_name_prefix}_{current_file_subindex}.ndjson").open(mode="wb")
    try:
        for idx, doc in enumerate(documents):
            action_and_metadata_b, doc_b = serializer(idx, doc)
            num_new_bytes = len(action_and_metadata_b) + len(doc_b)
            current_doc_cnt += 2
            if (
                current_file_size + num_new_bytes
            ) >= max_file_size_bytes or current_doc_cnt >= max_doc_cnt:
                fd.close()
                current_file_subindex += 1
                current_file_size = num_new_bytes
                current_doc_cnt = 2
                fd = (dst / f"{file_name_prefix}_{current_file_subindex}.ndjson").open(
                    mode="wb"
                )
            fd.write(action_and_metadata_b)
            fd.write(doc_b)
    finally:
        fd.close()


class ElasticSearchGenerator:

    def __init__(self, project: Project):
        self.__project = project
        self.__designation_resolver = TerminologyDesignationResolver(
            project, project.input.translation / "base_translations.json"
        )

    @staticmethod
    def __get_contextualized_termcode_hash(
        context_node: dict, termcode_node: dict, namespace_uuid_str
    ) -> str:
        context_termcode_hash_input = f"{context_node.get('system')}{context_node.get('code')}{context_node.get('version', '')}{termcode_node.get('system')}{termcode_node.get('code')}"
        namespace_uuid = uuid.UUID(namespace_uuid_str)
        return str(uuid.uuid3(namespace_uuid, context_termcode_hash_input))

    @staticmethod
    def __get_termcode_hash(termcode_node: dict, namespace_uuid_str) -> str:
        termcode_hash_input = (
            f"{termcode_node.get('system')}{termcode_node.get('code')}"
        )
        namespace_uuid = uuid.UUID(namespace_uuid_str)
        return str(uuid.uuid3(namespace_uuid, termcode_hash_input))

    @staticmethod
    def __build_crit_set_map(
        context_termcode_hash_to_crit_set, crit_set_dir, namespace_uuid_str
    ):
        for filename in os.listdir(crit_set_dir):
            with open(
                os.path.join(crit_set_dir, filename), mode="r", encoding="UTF-8"
            ) as file:
                crit_set = json.load(file)

                crit_set_url = crit_set["url"]

                for crit in crit_set["contextualized_term_codes"]:
                    cont_term_hash = (
                        ElasticSearchGenerator.__get_contextualized_termcode_hash(
                            crit[0], crit[1], namespace_uuid_str=namespace_uuid_str
                        )
                    )

                    if cont_term_hash not in context_termcode_hash_to_crit_set:
                        context_termcode_hash_to_crit_set[cont_term_hash] = [
                            crit_set_url
                        ]
                    else:
                        context_termcode_hash_to_crit_set[cont_term_hash].append(
                            crit_set_url
                        )

    def __get_relation_crit_object(
        self,
        code: str | int,
        system: dict,
        context: dict,
        term_code_info_map: dict,
        namespace_uuid_str: str,
    ) -> RelationalTermcode:
        """
        Returns the information of a given child/parent node,
        including the contextualized_termcode_hash and the translations

        :param code: code of parent/child node
        :param system: system of parent/child node
        :param context: context of parent/child node
        :param term_code_info_map: dict with all codes, saved based on their contextualized_termcode_hash
        :param namespace_uuid_str: uuid of namespace
        :return: dict[str, dict] with information of the given parent/child node
        """
        term_code = {"code": code, "system": system}
        context_term_code_hash = self.__get_contextualized_termcode_hash(
            context, term_code, namespace_uuid_str
        )

        parent_term_code_info = term_code_info_map[context_term_code_hash]
        parent_context = parent_term_code_info["context"]
        parent_term_code = parent_term_code_info["term_code"]

        parent_relational_termcode = RelationalTermcode(
            contextualized_termcode_hash=self.__get_contextualized_termcode_hash(
                parent_context, parent_term_code, namespace_uuid_str=namespace_uuid_str
            ),
            display=self.__designation_resolver.resolve_term(parent_term_code),
            terminology=system,
            term_code=code,
            selectable=self.__determine_if_termcode_selectable(parent_term_code_info),
        )

        return parent_relational_termcode

    def __determine_if_termcode_selectable(self, term_code_info: dict) -> bool:
        # For now, we agreed upon just using the first termcode if there are more than one
        children_cut_off = 400
        return term_code_info["children_count"] < children_cut_off

    def __iterate_tree(
        self,
        ui_tree_list: dict,
        term_code_info_map: dict,
        target_elastic_crit_list: list,
        context_termcode_hash_to_crit_set: dict,
        namespace_uuid_str: str,
    ):
        """
        Iterates ui tree and complements information about each node
        """
        for ui_tree in ui_tree_list:
            if not self.__designation_resolver.has_designations_for(
                ui_tree.get("system")
            ):
                _logger.warning(
                    f"No designations are loaded for code system '{ui_tree.get('system')}' => No translations will be "
                    f"available"
                )

            for entry in ui_tree["entries"]:
                cur_tree_context = ui_tree["context"]
                ui_tree_term_code = {"system": ui_tree["system"], "code": entry["key"]}

                context_termcode_hash = self.__get_contextualized_termcode_hash(
                    cur_tree_context, ui_tree_term_code, namespace_uuid_str
                )

                term_code_info = term_code_info_map[context_termcode_hash]

                term_code = term_code_info["term_code"]
                context = term_code_info["context"]
                selectable = self.__determine_if_termcode_selectable(term_code_info)
                obj = {
                    "hash": context_termcode_hash,
                    "name": term_code["display"],
                    "availability": 0,
                    "terminology": term_code["system"],
                    "termcode": term_code["code"],
                    "selectable": selectable,
                    "context": context,
                    "termcodes": [term_code_info["term_code"]],
                    "criteria_sets": [],
                    "display": self.__designation_resolver.resolve_term(term_code),
                    "parents": [],
                    "children": [],
                    "related_terms": [],
                    "kds_module": term_code_info["module"]["display"],
                }

                for parent_code in entry["parents"]:
                    obj["parents"].append(
                        self.__get_relation_crit_object(
                            parent_code,
                            ui_tree["system"],
                            context,
                            term_code_info_map,
                            namespace_uuid_str,
                        )
                    )

                for child_code in entry["children"]:
                    obj["children"].append(
                        self.__get_relation_crit_object(
                            child_code,
                            ui_tree["system"],
                            context,
                            term_code_info_map,
                            namespace_uuid_str,
                        )
                    )

                # TODO - Siblings - needs to be considered as it is possible to have siblings from other ui_tree
                # for sibling_code in term_code_info['siblings']:
                #    obj['children'].append(ElasticSearchGenerator.__get_relation_crit_object(child_code,ui_tree['system'],term_code_info_map, namespace_uuid_str=namespace_uuid_str))

                if obj["hash"] in context_termcode_hash_to_crit_set:
                    obj["criteria_sets"] = context_termcode_hash_to_crit_set[
                        obj["hash"]
                    ]

                target_elastic_crit_list.append(obj)

    def __convert_value_set(self, value_set, termcode_to_valueset, namespace_uuid_str):
        if len(value_set.get("expansion", {}).get("contains", [])) == 0:
            _logger.warning(
                f"Value set [url={value_set.get('url', '<missing>')}] is not expanded or its "
                f"expansion is empty => Skipping"
            )
            return

        for termcode in value_set["expansion"]["contains"]:

            termcode_hash_input = f"{termcode['code']}{termcode['system']}"
            namespace_uuid = uuid.UUID(namespace_uuid_str)
            termcode_hash = str(uuid.uuid3(namespace_uuid, termcode_hash_input))

            if termcode_hash not in termcode_to_valueset:
                tc = {
                    "code": termcode["code"],
                    "display": termcode["display"],
                    "system": termcode["system"],
                }
                if v := termcode.get("version"):
                    tc["version"] = v
                termcode_to_valueset[termcode_hash] = {
                    "hash": termcode_hash,
                    "termcode": tc,
                    "value_sets": [value_set["url"]],
                    "display": self.__designation_resolver.resolve_term(termcode),
                }

            else:
                termcode_to_valueset[termcode_hash]["value_sets"].append(
                    value_set["url"]
                )

    @staticmethod
    def __update_es_files_with_availability(
        es_availability_inserts, max_filesize_mb, filename_prefix, extension, write_dir
    ):
        current_file_subindex = 1
        current_file_size = 0

        count = 0

        current_file_name = os.path.join(
            write_dir, f"{filename_prefix}_{current_file_subindex}{extension}"
        )
        _logger.debug(f"Writing to file {current_file_name}")
        with open(current_file_name, mode="w+", encoding="UTF-8") as current_file:

            for insert in es_availability_inserts:
                count = count + 1
                current_line = f"{json.dumps(insert, cls=JSONFhirOntoEncoder)}\n"
                current_file.write(current_line)
                current_file_size += len(current_line)

                if current_file_size > max_filesize_mb * 1024 * 1024 and count % 2 == 0:
                    current_file_subindex += 1
                    current_file_name = os.path.join(
                        write_dir,
                        f"{filename_prefix}_{current_file_subindex}{extension}",
                    )
                    current_file_size = 0
                    current_file.close()
                    current_file = open(current_file_name, mode="w", encoding="UTF-8")
                    _logger.debug(f"Writing to file {current_file_name}")

    def __load_termcode_info(
        self, tree_file_name, namespace_uuid_str
    ) -> Mapping[str, dict]:
        term_code_info_map = {}

        folder = self.__project.output.mkdirs("merged_ontology", "term-code-info")
        pattern = r"_ui_tree_\d+.json"
        filename_prefix = re.sub(pattern, "", tree_file_name)

        with open(
            folder / f"{filename_prefix}_term_code_info.json",
            mode="r",
            encoding="UTF-8",
        ) as f:
            term_code_info_list = json.load(f)

            _logger.debug(f"Loaded termcode info map from file '{filename_prefix}'")
            for term_code_info in term_code_info_list:
                term_code_hash = self.__get_contextualized_termcode_hash(
                    term_code_info["context"],
                    term_code_info["term_code"],
                    namespace_uuid_str,
                )
                term_code_info_map[term_code_hash] = term_code_info

        return term_code_info_map

    def __get_hashed_tree(self) -> Mapping[str, Any]:
        directory = self.__project.input.elastic
        es_onto_tree = {}

        for filename in os.listdir(directory):
            if "ontology" in filename:
                filepath = os.path.join(directory, filename)

                with open(filepath, mode="r", encoding="utf-8") as file:
                    for line in file:
                        line = line.strip()

                        if line:
                            obj = json.loads(line)

                            if "index" in obj:
                                cur_hash = obj["index"]["_id"]
                            else:
                                es_onto_tree[cur_hash] = {
                                    "availability": 0,
                                    "children": obj["children"],
                                }

        return es_onto_tree

    def __update_availability_on_hash_tree(self, avail_hash_tree, namespace_uuid_str):
        hash_set = set()

        availability_input_dir = self.__project.input.availability

        with open(availability_input_dir / "stratum-to-context.json") as f:
            stratum_to_context = json.load(f)

        for filename in os.listdir(availability_input_dir.path):
            if "measure-report" in filename:
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

                                    strat_system = stratum["value"]["coding"][0][
                                        "system"
                                    ]
                                    strat_code = stratum["value"]["coding"][0]["code"]

                                    termcode = {
                                        "system": strat_system,
                                        "code": strat_code,
                                    }

                                    if context:
                                        hash = ElasticSearchGenerator.__get_contextualized_termcode_hash(
                                            context, termcode, namespace_uuid_str
                                        )

                                        hash_set.add(hash)
                                        if hash in avail_hash_tree:
                                            avail_hash_tree[hash]["availability"] = (
                                                avail_hash_tree[hash]["availability"]
                                                + measure_score
                                            )

    @staticmethod
    def __convert_measure_score_to_ranges(measure_score):
        buckets = [0, 10, 100, 1000, 10000, 50000, 100000, 150000, 200000, 1000000]
        return max(b for b in buckets if measure_score >= b)

    @staticmethod
    def __get_avail_sum_for_all_children(parent_id, tree):
        count = tree[parent_id]["availability"]
        for child in tree[parent_id]["children"]:
            count = count + ElasticSearchGenerator.__get_avail_sum_for_all_children(
                child["contextualized_termcode_hash"], tree
            )
        return count

    def __generate_documents_from_profile_tree_node(
        self,
        node: ProfileTreeNode,
        parent: ProfileIndexDocument | None = None,
    ) -> list[ProfileIndexDocument]:
        doc = ProfileIndexDocument.from_profile_tree_node(node)
        doc.parents = [parent.to_ref()] if parent else []
        return [
            doc,
            *(
                desc_doc
                for child in node.children
                for desc_doc in self.__generate_documents_from_profile_tree_node(
                    child, doc
                )
            ),
        ]

    def generate_profile_tree_files(
        self, profile_tree: list[ProfileTreeNode]
    ) -> list[ProfileIndexDocument]:
        # Get module-level nodes
        documents = []
        for tree_node in profile_tree:
            documents.extend(
                self.__generate_documents_from_profile_tree_node(tree_node, None)
            )
        return documents

    def generate_elasticsearch_files(
        self,
        generate_availability,
        namespace_uuid_str="00000000-0000-0000-0000-000000000000",
        max_filesize_mb=10,
        update_translation_supplements=False,
    ):
        generated_ontology_dir = self.__project.output.mkdirs("merged_ontology")
        translations_dir = self.__project.output.translation.mkdirs("supplements")
        availability_output_dir = self.__project.output.availability

        ui_tree_dir = generated_ontology_dir / "ui-trees"
        current_file_index = 0

        elastic_dir = generated_ontology_dir / "elastic"
        _logger.debug(f"Cleaning up output directory @ {elastic_dir}")
        if elastic_dir.exists():
            shutil.rmtree(elastic_dir)
        os.makedirs(elastic_dir, exist_ok=True)

        value_set_dir = generated_ontology_dir / "value-sets"

        context_termcode_hash_to_crit_set = {}
        crit_set_dir = generated_ontology_dir / "criteria-sets"
        self.__build_crit_set_map(
            context_termcode_hash_to_crit_set, crit_set_dir, namespace_uuid_str
        )

        self.__designation_resolver.load_base_designations(ui_tree_dir, value_set_dir)
        self.__designation_resolver.load_designations(
            translations_dir, update_translation_supplements
        )

        if generate_availability:
            _logger.info("Generating availability")
            es_availability_inserts = []

            avail_hash_tree = self.__get_hashed_tree()
            _logger.debug("Updating availability on hash tree")
            self.__update_availability_on_hash_tree(avail_hash_tree, namespace_uuid_str)

            for key, value in avail_hash_tree.items():
                sum_all_children = self.__get_avail_sum_for_all_children(
                    key, avail_hash_tree
                )

                insert_hash = {"update": {"_id": key}}
                insert_availability = {
                    "doc": {
                        "availability": self.__convert_measure_score_to_ranges(
                            sum_all_children
                        )
                    }
                }
                es_availability_inserts.append(insert_hash)
                es_availability_inserts.append(insert_availability)

            self.__update_es_files_with_availability(
                es_availability_inserts,
                max_filesize_mb,
                "es_availability_update",
                ".ndjson",
                availability_output_dir,
            )

            return

        _logger.info("Generating Elasticsearch term code index documents")
        for filename in os.listdir(ui_tree_dir):
            if filename.endswith(".json"):
                _logger.info(f"Processing {filename}")

                with open(ui_tree_dir / filename, mode="r", encoding="UTF-8") as f:
                    json_tree = json.load(f)

                term_code_info_map = self.__load_termcode_info(
                    filename, namespace_uuid_str
                )
                json_flat = []

                self.__iterate_tree(
                    json_tree,
                    term_code_info_map,
                    json_flat,
                    context_termcode_hash_to_crit_set,
                    namespace_uuid_str,
                )

                _write_es_documents(
                    self.__project.output.mkdirs("merged_ontology", "elastic"),
                    f"onto_es__ontology_{current_file_index}",
                    "ontology",
                    json_flat,
                    _ontology_doc_ser,
                )

                current_file_index = current_file_index + 1

        _logger.info("Generating Elasticsearch value set index documents")
        termcode_to_valueset = {}

        for filename in os.listdir(value_set_dir):
            if filename.endswith(".json"):
                _logger.info(f"Processing value set file {filename}")
                with open(value_set_dir / filename, mode="r", encoding="UTF-8") as f:
                    value_set = json.load(f)
                self.__convert_value_set(
                    value_set, termcode_to_valueset, namespace_uuid_str
                )

        json_flat = list(termcode_to_valueset.values())

        _write_es_documents(
            self.__project.output.mkdirs("merged_ontology", "elastic"),
            "onto_es__codeable_concept",
            "codeable_concept",
            json_flat,
            _codeable_concept_doc_ser,
        )

        _logger.info("Generating Elasticsearch profile index documents")

        dse_output_dir = self.__project.output.dse
        with (dse_output_dir / "profile_tree.json").open(
            mode="r", encoding="utf-8"
        ) as fd:
            profile_tree = ProfileTreeTA.validate_json(fd.read())

        documents = self.generate_profile_tree_files(profile_tree)

        _write_es_documents(
            self.__project.output.mkdirs("merged_ontology", "elastic"),
            "onto_es__profile",
            "profile",
            documents,
            _profile_doc_ser,
        )
