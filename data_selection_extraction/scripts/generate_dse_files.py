import argparse
import collections
import os
import json
from pathlib import Path

from typing import Union, Literal, Mapping, List, Any, Optional
from urllib.parse import urlparse

from fhir.resources.R4B.valueset import ValueSet

from common.util.codec.json import JSONFhirOntoEncoder
from common.util.fhir.package.manager import FirelyPackageManager
from common.util.http.exceptions import ClientError
from common.util.http.terminology.client import FhirTerminologyClient
from common.util.project import Project
from data_selection_extraction.config.profile_detail import FieldsConfig
from data_selection_extraction.core.generators.profile_detail import (
    ProfileDetailGenerator,
)
from data_selection_extraction.core.generators.profile_tree import (
    ProfileTreeGenerator,
    SnapshotPackageScope,
)
from cohort_selection_ontology.core.terminology.client import (
    CohortSelectionTerminologyClient,
    remove_non_direct_ancestors,
)
from cohort_selection_ontology.model.tree_map import TreeMap, TermEntryNode
from cohort_selection_ontology.model.ui_data import TermCode, TranslationDisplayElement
from common.util.log.functions import get_logger


_logger = get_logger(__file__)


def configure_args_parser():
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("--download_packages", action="store_true")
    arg_parser.add_argument("--generate_profile_details", action="store_true")
    arg_parser.add_argument("--download_value_sets", action="store_true")
    arg_parser.add_argument("--generate_mapping_trees", action="store_true")
    arg_parser.add_argument("--copy_snapshots", action="store_true")
    arg_parser.add_argument(
        "--profiles",
        nargs="+",
        help="List of profiles to process - if none process all",
    )
    arg_parser.add_argument(
        "-p",
        "--project",
        required=True,
        help="Name of the project to generate the "
        "data selection and extraction ontology for",
    )
    return arg_parser


def download_simplifier_packages(
    package_names: list[str], project: Project
) -> FirelyPackageManager:
    manager = FirelyPackageManager(
        project.output.dse.mkdirs("fhir_packages"), reinit=True
    )
    manager.install(*package_names, inflate=True)
    return manager


def extend_terminology_display_mapping(
    value_sets: List[Mapping[str, Any]], project: Project
):
    with (project.input.terminology / "terminology_systems.json").open(
        mode="r", encoding="utf-8"
    ) as f:
        term_mapping_list = json.load(f)
    term_mapping = {e.get("url"): e for e in term_mapping_list}
    for vs in value_sets:
        vs_url = vs.get("url")
        if title := vs.get("title"):
            original = title
        elif name := vs.get("name"):
            _logger.warning(
                f"No title found for value set '{vs_url}' => Using name instead"
            )
            original = name
        else:
            _logger.warning(
                f"No suitable display value found for value set '{vs_url}' => Skipping"
            )
            original = None
        if original:
            if entry := term_mapping.get(vs_url):
               entry.get("display", {})["original"] = original
            else:
                term_mapping[vs_url] = {"url": vs_url, "display": {"original": original}}
    with (project.output.terminology / "terminology_systems.json").open(
        mode="w", encoding="utf-8"
    ) as f:
        json.dump(list(term_mapping.values()), f)


def download_and_save_value_set(
    value_set_url, project: Project
) -> Optional[Mapping[str, Any]]:
    value_set_folder = project.output.dse.mkdirs("value-sets")
    client = FhirTerminologyClient.from_project(project)

    try:
        value_set = client.expand_value_set(value_set_url)
        value_set_name = value_set.get(
            "name",
            urlparse(value_set.get("url"))
            .path.split("/ValueSet/", 1)[-1]
            .replace("/", ""),
        )

        with open(
            value_set_folder / f"{value_set_name}.json", mode="w+", encoding="utf-8"
        ) as value_set_file:
            json.dump(value_set, value_set_file)

        return value_set
    except ClientError as ce:
        _logger.warning(f"Failed to download value set '{value_set_url}' <- {ce}")
        return None


def download_all_value_sets(profile_details, project: Project):
    value_set_urls = set()

    for detail in profile_details:
        for filter in (filter for filter in detail.filters if filter.ui_type == "code"):
            for value_set_url in filter.valueSetUrls:
                value_set_urls.add(value_set_url)

    value_sets = []
    for value_set_url in list(value_set_urls):
        vs = download_and_save_value_set(value_set_url, project)
        if vs:
            value_sets.append(vs)

    extend_terminology_display_mapping(value_sets, project)


def generate_r_load_sql(profile_details):
    with open(
        dse_output_dir / "R__load_latest_dse_profiles.sql", mode="w+", encoding="utf-8"
    ) as sql_file:
        sql_file.write("DELETE FROM dse_profile;\n")
        sql_file.write("ALTER SEQUENCE public.dse_profile_id_seq RESTART WITH 1;\n")
        sql_file.write("INSERT INTO dse_profile(id, url, entry) VALUES \n")

        for index, profile_detail in enumerate(profile_details):
            profile_detaildb = json.dumps(
                profile_detail, cls=JSONFhirOntoEncoder
            ).replace("'", "''")
            value_line = f"({index + 1},'{profile_detail.url}','{profile_detaildb}')"
            sql_file.write(value_line)
            if index < len(profile_details) - 1:
                sql_file.write(",\n")
            else:
                sql_file.write(";")


def extract_concepts_from_value_set(
    vs: dict, target: dict, mode: Literal["compose", "expansion"]
) -> None:
    match mode:
        case "compose":
            for cs_entry in vs["compose"]["include"]:
                system = cs_entry.get("system", None)
                version = cs_entry.get("version", None)
                if system not in target:
                    target[system] = dict()
                system_dict = target[system]
                if version not in system_dict:
                    system_dict[version] = set()
                concept_set = system_dict[version]
                for concept in cs_entry.get("concept", []):
                    concept_set.add((concept["code"], concept.get("display", None)))
        case "expansion":

            if "contains" not in vs["expansion"]:
                return

            for concept in vs["expansion"]["contains"]:
                system = concept.get("system", None)
                version = concept.get("version", None)
                code = concept.get("code", None)
                display = concept.get("display", None)
                if system not in target:
                    target[system] = dict()
                system_dict = target[system]
                if version not in system_dict:
                    system_dict[version] = set()
                concept_set = system_dict[version]
                concept_set.add((code, display))
        case _:
            raise Exception(
                f"No such mode [actual='{mode}',expected={{'compose','expansion'}}]"
            )


def generate_cs_tree_map(
    system: str, version: str | None, concepts: set, project: Project
) -> TreeMap:
    _logger.debug("Initializing closure table")
    client = CohortSelectionTerminologyClient(project)

    closure_name = client.create_concept_map()
    _logger.debug(f"Created closure table [name='{closure_name}']")
    term_codes = list(
        map(
            lambda t: TermCode(system=system, code=t[0], display=t[1], version=version),
            concepts,
        )
    )
    treemap: TreeMap = TreeMap({}, None, system, version)
    treemap.entries = {
        term_code.code: TermEntryNode(term_code=term_code) for term_code in term_codes
    }
    _logger.debug("Building closure table")
    try:
        closure_map = client.get_closure_map(term_codes, closure_name)
        cs_path = Path("maps")
        cs_path.mkdir(parents=True, exist_ok=True)
        with (cs_path / f"{closure_name}.fhir.json").open(
            mode="w+", encoding="utf-8"
        ) as cs_f:
            cs_f.write(closure_map.model_dump_json())
        if groups := closure_map.group:
            if len(groups) > 1:
                raise Exception(
                    "Multiple groups in closure map. Currently not supported."
                )
            _logger.debug("Building tree map")
            for group in groups:
                mapping = group.element
                subsumption_map = collections.defaultdict(list)  # Dict of lists
                for item in mapping:
                    for target in item.target:
                        if target.code is not None:
                            subsumption_map[item.code].append(target.code)
                        else:
                            _logger.warning(
                                f"Coding [system={group.source}, code={item.code}] "
                                f"has no target coding for system '{group.target}' and will not be "
                                f"added [equivalence={target.equivalence}, "
                                f"comment='{target.comment}']"
                            )
                # subsumption_map = {item['code']: [target['code'] for target in item['target']] for item in
                #                   subsumption_map if 'code' in item}
                for _, parents in subsumption_map.items():
                    remove_non_direct_ancestors(parents, subsumption_map)
                for (
                    node,
                    parents,
                ) in subsumption_map.items():
                    treemap.entries[node].parents += parents
                    for parent in parents:
                        treemap.entries[parent].children.append(node)
    except Exception as e:
        _logger.error(e)
        _logger.debug("Traceback:\n", exc_info=e)

    return treemap


def generate_dse_mapping_trees(
    vs_dir_path: Union[str, os.PathLike], project: Project
) -> list[dict]:
    # Check presence of downloaded value sets
    if not os.path.isdir(vs_dir_path):
        _logger.error("Directory with downloaded value sets does not exist")
        raise Exception(
            f"Directory with downloaded value sets does not exist [path='{os.path.abspath(vs_dir_path)}']"
        )
    elif len(os.listdir(vs_dir_path)) == 0:
        _logger.warning(
            "Downloaded value set dir is empty. Empty mapping tree file will be generated"
        )

    # Read value sets and aggregate concepts by code systems
    _logger.info("Aggregating code system concepts from value sets")
    code_systems = dict()
    for file_name in os.listdir(vs_dir_path):
        if not file_name.endswith(".json"):
            _logger.warning(
                f"Directory entry '{file_name}' is not a JSON file. Skipping"
            )
        else:
            _logger.info(f"Processing value set file '{file_name}'")
            with open(
                os.path.join(vs_dir_path, file_name), mode="r", encoding="utf-8"
            ) as file:
                # We assume JSON format
                vs_json = json.load(file)
                if "compose" in vs_json:
                    extract_concepts_from_value_set(vs_json, code_systems, "compose")
                elif "expansion" in vs_json:
                    extract_concepts_from_value_set(vs_json, code_systems, "expansion")
                else:
                    _logger.warning(
                        "Value set does not lists content explicitly. Skipping"
                    )

    # Generate mapping tree for each code system
    _logger.info("Generating mapping tree")
    tree_maps = []
    for system, version_map in code_systems.items():
        for version, concept_set in version_map.items():
            _logger.info(f"Generating tree map [system='{system}',version='{version}']")
            tree_maps.append(
                generate_cs_tree_map(system, version, concept_set, project)
            )

    return [tree_map.to_dict() for tree_map in tree_maps]


if __name__ == "__main__":
    parser = configure_args_parser()
    args = parser.parse_args()

    project = Project(args.project)
    dse_input_dir = project.input.dse
    dse_output_dir = project.output.dse
    project.package_manager.restore(inflate=True)

    with open(dse_input_dir / "module_config.json", "r", encoding="utf-8") as f:
        module_config = json.load(f)

    module_translation = module_config.get("module_translation")
    module_order = module_config.get("module_order")
    reference_resolve_base_url = module_config.get("reference_resolve_base_url")

    if args.download_packages:
        with open(
            dse_input_dir / "required-packages.json", mode="r", encoding="utf-8"
        ) as f:
            required_packages = json.load(f)

        download_simplifier_packages(required_packages, project)

    with open(dse_input_dir / "excluded-dirs.json", mode="r", encoding="utf-8") as f:
        excluded_dirs = json.load(f)

    with open(
        dse_input_dir / "excluded-profiles.json", mode="r", encoding="utf-8"
    ) as f:
        excluded_profiles = json.load(f)

    packages_dir = dse_input_dir / "dependencies"
    snapshots_dir = dse_input_dir / "snapshots"
    # .extension cant be removed
    with (project.input.dse / "field_config.json").open(
        mode="r", encoding="utf-8"
    ) as f:
        fields_config = FieldsConfig.model_validate_json(f.read())
    fields_to_exclude = ["meta", "id", "modifierExtension", "name", "address"]
    field_trees_to_exclude = [
        "Patient.name",
        "Patient.location",
        "Patient.identifier",
        "Patient.address",
        "Patient.link",
    ]

    tree_generator = ProfileTreeGenerator(
        packages_dir=packages_dir,
        snapshots_dir=snapshots_dir,
        excluded_dirs=excluded_dirs,
        excluded_profiles=excluded_profiles,
        module_order=module_order,
        module_translation=module_translation,
        fields_config=fields_config,
        profiles_to_process=args.profiles,
        project=project,
    )

    if args.copy_snapshots:
        tree_generator.copy_profile_snapshots()

    tree_generator.get_profile_snapshots()
    profile_tree = tree_generator.generate_profiles_tree()

    with open(dse_output_dir / "profile_tree.json", mode="w", encoding="utf-8") as f:
        json.dump(profile_tree, f, ensure_ascii=False, cls=JSONFhirOntoEncoder)

    with open(
        dse_input_dir / "mapping-type-code.json", mode="r", encoding="utf-8"
    ) as f:
        mapping_type_code = json.load(f)

    blacklisted_value_sets = ["http://hl7.org/fhir/ValueSet/observation-codes"]

    if args.generate_profile_details:
        _logger.info("Loading fields config")

        profiles = tree_generator.profiles
        profile_detail_generator = ProfileDetailGenerator(
            project=project,
            profiles=profiles,
            mapping_type_code=mapping_type_code,
            blacklisted_value_sets=blacklisted_value_sets,
            fields_config=fields_config,
            reference_base_url=reference_resolve_base_url,
            module_translation=module_translation,
        )

        profile_details = (
            profile_detail_generator.generate_profile_details_for_profiles_in_scope(
                SnapshotPackageScope.MII,
                cond=lambda p: p.kind == "resource",
                profile_tree=profile_tree,
            )
        )

        with open(
            dse_output_dir / "profile_details_all.json", mode="w+", encoding="utf-8"
        ) as p_details_f:
            json.dump(profile_details, p_details_f, cls=JSONFhirOntoEncoder)

        generate_r_load_sql(profile_details)

        if args.download_value_sets:
            download_all_value_sets(profile_details, project)

        if args.generate_mapping_trees:
            dse_mapping_trees = generate_dse_mapping_trees(
                dse_output_dir / "value-sets", project
            )

            with open(
                dse_output_dir / "dse_mapping_tree.json", mode="w+", encoding="utf-8"
            ) as dse_tree_f:
                json.dump(dse_mapping_trees, dse_tree_f, cls=JSONFhirOntoEncoder)
