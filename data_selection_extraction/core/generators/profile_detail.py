import re
from collections.abc import Callable
from typing import Mapping, List, TypedDict, Any, Optional

from common.exceptions.profile import MissingProfileError
from cohort_selection_ontology.model.ui_data import TranslationDisplayElement, BulkTranslationDisplayElement
from common.util.fhir.structure_definition import supports_type, find_type_element, get_element_from_snapshot, \
    get_types_supported_by_element, Snapshot
from common.util.project import Project
from data_selection_extraction.core.generators.profile_tree import get_value_for_lang_code
from data_selection_extraction.model.detail import FieldDetail, ProfileDetail, Filter, ProfileReference, ReferenceDetail
from common.util.fhir.enums import FhirPrimitiveDataType, FhirComplexDataType

from common.util.log.functions import get_class_logger

Profile = Mapping[str, any]


class SearchParamPathMapping(TypedDict):
    search_param: str
    fhir_path: str


class ProfileDetailGenerator:
    __logger = get_class_logger("ProfileDetailGenerator")

    blacklisted_values_sets: List[str]
    profiles: Mapping[str, Mapping[str, Mapping[str, any]]]
    mapping_type_code: Mapping[str, SearchParamPathMapping]
    fields_to_exclude: List[str]
    fields_trees_to_exclude: List[str]
    reference_base_url: str

    def __init__(self, project: Project, profiles, mapping_type_code, blacklisted_value_sets, fields_to_exclude, field_trees_to_exclude,
                 reference_base_url):
        self.__project = project
        self.blacklisted_value_sets = blacklisted_value_sets
        self.profiles = profiles
        # Prevents having to generate the mapping over and over again
        self.__all_profiles = self.__get_profiles()
        self.mapping_type_code = mapping_type_code
        self.fields_to_exclude = fields_to_exclude
        self.field_trees_to_exclude = field_trees_to_exclude
        self.reference_base_url = reference_base_url

    def find_and_load_struct_def_from_path(self, struct_def: Mapping[str, any], path: str):
        elements = struct_def['snapshot']["element"]

        for elem in (elem for elem in elements if elem['id'] == path):

            elem_type = elem['type']

            for type_elem in (elem for elem in elem_type if re.search("Reference", elem['code'])):

                target_profile_url = next(
                    (url for url in type_elem['targetProfile'] if url.startswith(self.reference_base_url)),
                    None)

                if not target_profile_url:
                    continue

                if target_profile_url not in self.__all_profiles:
                    for profile in self.__all_profiles:
                        if target_profile_url.split("/")[-1] == profile.split("/")[-1]:
                            return self.__all_profiles[profile]['structureDefinition']

                return self.__all_profiles[target_profile_url]['structureDefinition']

        return None

    def get_value_sets_for_code_filter(self, struct_def, fhir_path):

        value_sets = []
        elements = struct_def['snapshot']["element"]
        part_match = re.search(r'\((.*?)\)', fhir_path)

        if part_match:
            struct_def = self.find_and_load_struct_def_from_path(struct_def, part_match.group(1))

            if not struct_def:
                return None

            struct_def_type = struct_def['type']
            return self.get_value_sets_for_code_filter(struct_def,
                                                       f"{struct_def_type}.{fhir_path.split(').')[-1]}")

        pattern = rf"{fhir_path}[^.]*$"

        for elem in (elem for elem in elements if re.search(pattern, elem['id'])):
            if "binding" in elem :
                value_set = elem["binding"]["valueSet"]

                if value_set not in self.blacklisted_value_sets:
                    value_sets.append(value_set)

            elif len(value_sets) == 0 and "patternCoding" in elem or "fixed" in elem:
                return None

        if len(value_sets) > 0:
            return value_sets

        pattern = rf"{fhir_path}($|\.coding$)"

        for elem in (elem for elem in elements if re.search(pattern, elem['id'])):
            if "binding" in elem:
                value_set = elem["binding"]["valueSet"]

                if value_set not in self.blacklisted_value_sets:
                    value_sets.append(value_set)

            elif "patternCoding" in elem or "fixed" in elem:
                return None

        if len(value_sets) == 0:
            return None

        return value_sets

    @staticmethod
    def __find_field(fields: List[FieldDetail], id_end: str) -> Optional[FieldDetail]:
        for index in range(0, len(fields)):
            field = fields[index]
            if field.id.endswith(id_end):
                return field
        return None

    def __insert_field_into_profile_detail(self, profile_detail: ProfileDetail, field: FieldDetail):
        match field.type:
            case FhirComplexDataType.REFERENCE:
                fields = profile_detail.references
            case _:
                fields = profile_detail.fields
        path = re.split(r"[.:]", field.id)
        path = path[1:]
        parent_recommended = False
        field_type = field.type

        if len(path) == 0:
            return

        # TODO: This is a temporary workaround to allow both the postal code and the country information to be selected
        #       during data selection. To preserve context, selecting elements with simple data types which are not on
        #       the top level of a resource is disabled (e.g. to forbid selecting just Coding.code without
        #       Coding.system etc.).
        #       In the future we should switch to a more dynamic solution were the selectable elements can be defined in
        #       externalized config files using a well-defined syntax to prevent such hard-coded solutions.
        if (field_type in FhirPrimitiveDataType and len(path) > 1 and
                field.id not in {"Patient.address:Strassenanschrift.postalCode",
                                        "Patient.address:Strassenanschrift.country"}):
            return

        for index in range(0, len(path) - 1):
            id_end = path[index]
            parent_field = self.__find_field(fields, id_end)

            if parent_field is None:
                continue

            current_field = parent_field
            fields = current_field.children

            if not parent_recommended:
                parent_recommended = current_field.recommended
            if parent_recommended:
                field.recommended = False

        fields.append(field)

    def filter_element(self, element: Mapping[str, any]) -> bool:
        # TODO: This is a temporary workaround to allow both the postal code and the country information to be selected
        #       during data selection. To preserve context, selecting elements with simple data types which are not on
        #       the top level of a resource is disabled (e.g. to forbid selecting just Coding.code without
        #       Coding.system etc.).
        #       In the future we should switch to a more dynamic solution were the selectable elements can be defined in
        #       externalized config files using a well-defined syntax to prevent such hard-coded solutions.
        element_id = element.get('id')
        if element_id in {"Patient.address:Strassenanschrift.postalCode", "Patient.address:Strassenanschrift.country"}:
            return False

        attributes_true_level_one = ["mustSupport", "isModifier", "min"]

        if all(element.get(attr) is False or element.get(attr) == 0 or attr not in element
               for attr in attributes_true_level_one):
            self.__logger.debug(f"Excluding: {element['id']} as not mustSupport, modifier or min > 0")
            return True

        attributes_true_level_two = ["mustSupport", "isModifier"]

        if all(element.get(attr) is False or element.get(attr) == 0 or attr not in element
               for attr in attributes_true_level_two) and len(element["id"].split(".")) > 2:
            self.__logger.debug(f"Excluding: {element['id']} as not mustSupport or modifier on level > 2")
            return True

        if any(element['id'].endswith(field) or f"{field}." in element['id']for field in self.fields_to_exclude):
            self.__logger.debug(f"Excluding: {element['id']} as excluded field")
            return True

        if any(f"{field}" in element['id'] for field in self.field_trees_to_exclude):
            self.__logger.debug(f"Excluding: {element['id']} as part of field tree")
            return True

        if "[x]" in element['id'] and not element['id'].endswith("[x]"):
            self.__logger.debug(f"Excluding: {element['id']} as sub-elements relevant")
            return True

        if element["base"]["path"].split(".")[0] in {"Resource", "DomainResource"} and not "mustSupport" in element:
            self.__logger.debug(f"Excluding: {element['id']} as base is Resource or DomainResource and not mustSupport")
            return True

    @staticmethod
    def check_at_least_one_in_elem_and_true(element: Mapping[str, any], attributes_to_check: List[str]) -> bool:
        path = element["id"].split(".")

        if len(path) > 2:
            return False

        if all(element.get(attr) is False or element.get(attr) == 0 or attr not in element
               for attr in attributes_to_check):
            return False

        return True

    @staticmethod
    def get_name_from_id(element_id: str) -> str:
        name = element_id.split(".")[-1]
        name = name.split(":")[-1]
        name = name.replace("[x]", "")
        return name

    def find_field_in_profile_fields(self, field_id, fields):
        for field in fields:
            if 'children' in field:
                self.find_field_in_profile_fields(field_id, field['children'])
            if field['id'] == field_id:
                return field
        return None

    @staticmethod
    def get_element_by_content_ref(content_ref: str, elements: List[Mapping[str, any]]) -> Optional[Mapping[str, any]]:
        for element in elements:
            if element['id'] == content_ref:
                return element
        return None

    @staticmethod
    def get_value_for_lang_code(data: Mapping[str, any], lang_code: str) -> str:
        for ext in data.get('extension', []):
            if any(e.get('url') == 'lang' and e.get('valueCode') == lang_code for e in ext.get('extension', [])):
                return next(e['valueString'] for e in ext['extension'] if e.get('url') == 'content')
        return ""

    @staticmethod
    def resource_type_to_date_param(resource_type: str) -> str:
        if resource_type == 'Condition':
            return "recorded-date"

        return "date"

    def __get_profiles(self, scope: Optional[str] = None) -> Mapping[str, Mapping[str, Any]]:
        """
        Returns all profile entries in a certain scope or all if none is provided
        :param scope: Scope from which to return the profile entries
        :return: All profile entries matching the provided scope
        """
        if scope:
            return self.profiles.get(scope, {})
        else:
            return {k: v for d in self.profiles.values() for k, v in d.items()}

    def __find_mii_references_by_type(self, fhir_type):

        matching_mii_references = []

        for profile in self.__all_profiles.values():

            profile_fhir_type = profile["structureDefinition"]["type"]
            if profile_fhir_type == fhir_type:
                matching_mii_references.extend(self.__resolve_selectable_profiles(profile["url"]))

        return matching_mii_references

    def __resolve_selectable_profiles(self, profile_url: str, module: Optional[str]=None) -> List[str]:
        """
        Collects profile URLs of all selectable profiles given a parent profile from which other profiles in the scope
        of this class instance (all profiles in the ProfileDetailGenerator::profiles field) might be derived. If they
        are then they would also be selectable if the parent profile defines the range of a Reference element
        :param profile_url: string representing the URL of the profile from which to start the resolution
        :param module: Optional module name string from which the profile identified by the `profile_url` parameter
                       originates
        :return: list of URLs of selectable profiles
        """
        selectable_profiles = []
        children = filter(lambda t: t[1].get('baseDefinition', None) == profile_url,
                          map(lambda p: (p.get('module'), p.get('structureDefinition', {})),
                              self.__all_profiles.values()))

        # FIXME: The logic should only rely on the value of the `abstract` element of a given StructureDefinition
        #        instance to determine whether it itself is selectable or not. Currently whether other profiles in the
        #        same module are derived from it is used to determine "abstractness"
        # Determine whether the parent profile itself should be included
        if profile_url in self.__all_profiles:
            parent_profile = self.__all_profiles.get(profile_url, {}).get('structureDefinition', None)
            if parent_profile:
                if not parent_profile.get('abstract', False):
                    if all(m != module for m, _ in children):
                        selectable_profiles.append(profile_url)
        elif profile_url not in self.__all_profiles:
            # TODO: Decide on right log level since this matches every time the FHIR base resource profiles are
            #       encountered
            # If the URL does not match any profile in any scope it might be missing
            self.__logger.debug(f"Provided profile URL '{profile_url}' is not present and cannot be analyzed further. "
                                f"Consider including it via dependencies if this is not intended.")

        for child_module, child in map(lambda p: (p.get('module'), p.get('structureDefinition', {})),
                                       self.__all_profiles.values()):
            if child.get('baseDefinition', None) == profile_url:
                child_profile_url = child.get('url', None)
                child_selectable_profiles = self.__resolve_selectable_profiles(child_profile_url, child_module)
                selectable_profiles.extend(child_selectable_profiles)
        return selectable_profiles

    def get_referenced_mii_profiles(self, element: Mapping[str, any], field_type: str,
                                    is_root: bool = True) -> List[str]:
        """
        Searches for and aggregates referenced MII profiles listed by Reference elements supporting and present within
        the scope of profiles known to this ProfileDetailGenerator instance. Given some target profile specified for a
        Reference element all MII profiles are identified that are its descendants and have no profiles based on them
        in the instances profile scope
        :param element: ElementDefinition instance for which to find MII profiles it supports
        :param field_type: Shall be either 'Reference' if it supports the Reference FHIR data type or 'Extension' if it
                           supports 'Extension' elements that support the Reference FHIR data type in their 'value'
                           element
        :param is_root: If set to 'True' the call is assumed to be the initial call of this function. It is used
                        internally and should not be set by externally
        :return: List of MII profile URLs supported by the element
        """
        mii_references = []
        supports_reference = False

        match field_type:
            case 'Reference':
                supports_reference = True
                target_profiles = []

                for element_type in element['type']:
                    target_profiles = element_type.get('targetProfile', [])

                for profile in target_profiles:
                    mii_references.extend(filter(
                        lambda p: p.startswith('https://www.medizininformatik-initiative.de'),
                        self.__resolve_selectable_profiles(profile)
                    ))

                #if len(mii_references) == 0:
                #    for profile in target_profiles:
                #        fhir_type = profile.rstrip('/').split('/')[-1]
                #        mii_references.extend(self.find_mii_references_by_type(fhir_type))

            case 'Extension':
                # Iterate over all types with type code 'Extension'
                for ext_type in filter(lambda t: t.get('code', None) == "Extension", element.get('type', [])):
                    # Iterate over all MII target profiles explicitly supported by the element
                    for ext_profile_url in ext_type.get("profile", []):
                        ext_profile = self.__all_profiles.get(ext_profile_url, None)
                        if not ext_profile:
                            raise MissingProfileError(f"Missing extension profile with URL '{ext_profile_url}' in "
                                                      f"current scope. This can likely be fixed by adding its "
                                                      f"snapshot to the DSE package snapshots directory")
                        ext_elements = ext_profile.get('structureDefinition', {}).get('snapshot', {}).get('element', [])
                        ext_value_elements = list(
                            filter(lambda e: e.get('path', "").startswith("Extension.value"), ext_elements)
                        )
                        # By definition Extension instances can only have up to one 'value' element
                        ext_value_element = ext_value_elements[0] if len(ext_value_elements) > 0 else None
                        if ext_value_element and ext_value_element.get('max') != "0":
                            # Iterate over all types supported by the extensions value element to retrieve MII profiles
                            # they support
                            for element_type in [t.get('code') for t in ext_value_element.get('type', [])]:
                                references = self.get_referenced_mii_profiles(ext_value_element, element_type, False)
                                mii_references.extend(references)

                        # Filter for Extensions element definition in the Extensions definition
                        ext_ext_elements = list(
                            filter((lambda e: e.get('path', "").startswith('Extension.extension')),
                                   ext_elements)
                        )
                        if len(ext_value_elements) > 0:
                            # There are two cases we have to cover:
                            # 1) There are references to other Extension profiles within some extension element
                            #    definitions
                            # 2) The Extension element is defined directly in the current Extension profile
                            for ext_ext_element in ext_ext_elements:
                                ext_ext_element_types = {t.get('code') for t in ext_ext_element.get('type', [])}
                                references = []
                                if 'Extension' in ext_ext_element_types:
                                    references.extend(self.get_referenced_mii_profiles(ext_ext_element, "Extension",
                                                                                       False))
                                elif 'Reference' in ext_ext_element_types:
                                    references.extend(self.get_referenced_mii_profiles(ext_ext_element, "Reference",
                                                                                       False))
                                mii_references.extend(references)

        if is_root and supports_reference and len(mii_references) == 0:
            self.__logger.warning(f"{field_type} element '{element.get('id')}' does not support any selectable MII "
                                  f"profile in the current scope. This could be fixed by adding snapshots to the "
                                  f"DSE package snapshots directory, but can also be an indicator that no MII profile "
                                  f"is in the reference chain at all")
            return []

        return mii_references

    def __determine_if_extension_elem_can_be_treated_as_reference(self, element: Mapping[str, Any], profile: Snapshot) -> bool:
        if extension_type := find_type_element(element, FhirComplexDataType.EXTENSION):
            supports_references = []

            extension_profiles = extension_type.profile
            if extension_profiles: # Type element does contain Extension profile references
                for profile_url in extension_profiles:
                    profile = self.__all_profiles.get(profile_url, {}).get('structureDefinition')
                    if not profile:
                        self.__logger.warning(f"Extension '{profile_url}' was not found. Consider adding it to "
                                              f"'{self.__project.input('dse', 'snapshots')}' => "
                                              f"Ignoring potential references")
                    else:
                        elem = get_element_from_snapshot(profile, "Extension.value[x]")
                        if not elem:
                            supports_references.append(False)
                        else:
                            supports_references.append(supports_type(elem, FhirComplexDataType.REFERENCE))
                if all(supports_references):
                    return True
                elif any(supports_references):
                    self.__logger.warning(f"Element '{element.get('id')}' does not purely support Extensions containing "
                                          f"references")
                    return True
                else:
                    return False
            else: # Type element does not contain any Extension profile references
                element_id = element.get('id') + ".value[x]"
                value_elem = get_element_from_snapshot(profile, element_id)
                if not value_elem:
                    supports_references.append(False)
                else:
                    supports_references.append(supports_type(value_elem, FhirComplexDataType.REFERENCE))
        else:
            raise ValueError(f"Element '{element.get('id')}' does not support FHIR data type 'Extension'")

    def generate_detail_for_profile(self, profile: Mapping[str, any],
                                    profile_tree: Optional[Mapping[str, any]]=None) -> Optional[ProfileDetail]:
        profile_url = profile.get('url')
        self.__logger.info(f"Generating profile detail [url='{profile_url}']")

        try:
            if not "snapshot" in profile["structureDefinition"]:
                self.__logger.warning(f"Profile has no snapshot [url='{profile_url}'] => Skipping")
                return None

            struct_def = profile["structureDefinition"]
            date_param = self.resource_type_to_date_param(struct_def['type'])

            if profile_tree and not self.__is_profile_selectable(profile_url, profile_tree):
                self.__logger.debug(f"Profile is not selectable according to profile tree [url='{profile_url}'] => "
                                    f"Skipping")
                return None

            profile_detail = ProfileDetail(
                url=profile_url,
                display=TranslationDisplayElement(
                    original=struct_def.get("title", ""),
                    translations=[
                        {
                            "language": "de-DE",
                            "value": self.get_value_for_lang_code(struct_def.get("_title", {}), "de-DE")
                        },
                        {
                            "language": "en-US",
                            "value": self.get_value_for_lang_code(struct_def.get("_title", {}), "en-US")
                        }
                    ]
                ),
                filters=[
                    Filter(type="date", name=date_param, ui_type="timeRestriction")
                ]
            )

            profile_type = profile['structureDefinition']['type']
            code_search_param = (result := self.mapping_type_code.get(profile_type, None)) and result.get("search_param",
                                                                                                          None)
            fhir_path = (result := self.mapping_type_code.get(profile_type, None)) and result.get("fhir_path", None)
            value_set_urls = None

            if fhir_path is not None:
                value_set_urls = self.get_value_sets_for_code_filter(profile['structureDefinition'], fhir_path)

            if value_set_urls:
                profile_detail.filters.append(Filter(
                    type="token",
                    name=code_search_param,
                    ui_type="code",
                    valueSetUrls=value_set_urls,
                ))

            source_elements = profile['structureDefinition']['snapshot']['element']

            # We sort the elements in ascending order by length of their ID to ensure that parent elements will be
            # processed before their children and thus generated FieldDetail instances will be inserted as children of
            # their parent into the ProfileDetail instance by the `__insert_field_into_profile_detail` method since
            # their parent was already inserted when they will be
            for element in sorted(source_elements, key=lambda e: len(e['id'])):
                field_id = element['id']

                if self.filter_element(element):
                    continue

                if 'contentReference' in element:
                    content_reference_split = element['contentReference'].split("#")
                    if len(content_reference_split) > 1:
                        content_reference = content_reference_split[1]
                    else:
                        content_reference = content_reference_split[0]

                    element = self.get_element_by_content_ref(content_reference, source_elements)

                supported_types = get_types_supported_by_element(element)
                if len(supported_types) > 1:
                    self.__logger.warning(f"Element '{element.get('id')}' supports multiple types but only fixed typed "
                                          f"elements can be represented faithfully at this point => Proceeding with "
                                          f"first type listed")
                field_type = supported_types[0].code

                if supports_type(element, FhirComplexDataType.EXTENSION):
                    supports_reference = self.__determine_if_extension_elem_can_be_treated_as_reference(element,
                                                                                                        struct_def)
                    element_type = "Extension"
                else:
                    supports_reference = supports_type(element, FhirComplexDataType.REFERENCE)
                    element_type = "Reference" if supports_reference else field_type

                is_recommended_field = (self.check_at_least_one_in_elem_and_true(element, ["min"]) or
                                        self.check_at_least_one_in_elem_and_true(element, ["isModifier"]))
                # FIXME: Temporary fix to make elements of type 'Reference' not recommended due to issues in the UI
                #        except for references to the MII Medication profile
                if supports_reference:
                    field_type = "Reference"
                    if not ".medication" in field_id:
                        is_recommended_field = False

                # FIXME: Currently this value will be hard-coded to `False` since requiring researchers to include some
                #        fields that might not have some value to their research can unnecessarily complicate access to
                #        the data since access to these fields might require additional vetting steps and explicit
                #        permission by an ethics committee (e.g. in the case of the Patient.deceased element)
                # is_required_field = self.check_at_least_one_in_elem_and_true(element, ["isModifier"])
                is_required_field = False

                # FIXME: Temporary fix to make elements of type 'Reference' not recommended due to issues in the UI
                #        except for references to the MII Medication profile
                if field_type == "Reference" and not ".medication" in field_id:
                    is_recommended_field = False

                name = self.get_name_from_id(element["id"])

                match field_type:
                    case "Reference":
                        try:
                            referenced_mii_profiles = self.get_referenced_mii_profiles(element, element_type)
                            referenced_mii_profiles = [ProfileReference(url=url,
                                                                        display=self.__get_profile_title_display(
                                                                            self.__all_profiles.get(url)
                                                                            .get('structureDefinition')),
                                                                        fields=self.__get_fields_for_profile(
                                                                            url,
                                                                            profile_tree)
                                                                        ) for url in referenced_mii_profiles]
                        except MissingProfileError as exc:
                            self.__logger.warning(
                                f"Could not resolve referenced MII profiles [element_id='{field_id}']. "
                                f"Reason: {exc}")
                            referenced_mii_profiles = []

                        if len(referenced_mii_profiles) == 0:
                            self.__logger.warning(
                                f"Element '{element.get('id')}' references profiles that do not match any "
                                f"MII profile => Discarding")
                            continue

                        field = ReferenceDetail(id=field_id, referencedProfiles=referenced_mii_profiles)

                    case _:
                        field = FieldDetail(id=field_id)
                        field.type = field_type

                field.display = TranslationDisplayElement(
                    original=name,
                    translations=[
                         {
                             "language": "de-DE",
                             "value": self.get_value_for_lang_code(element.get('_short', {}), "de-DE")
                         },
                         {
                             "language": "en-US",
                             "value": self.get_value_for_lang_code(element.get('_short', {}), "en-US")
                         }
                    ],
                )
                field.description = TranslationDisplayElement(
                    original=element.get("definition", ""),
                    translations=[
                        {
                            "language": "de-DE",
                            "value": self.get_value_for_lang_code(element.get('_definition', {}), "de-DE")
                        },
                        {
                            "language": "en-US",
                            "value": self.get_value_for_lang_code(element.get('_definition', {}), "en-US")
                        }
                    ]
                )
                field.recommended = is_recommended_field
                field.required = is_required_field

                self.__insert_field_into_profile_detail(profile_detail, field)

            return profile_detail
        except Exception as exc:
            raise Exception(f"Failed to generate profile details for profile '{profile.get('url')}'") from exc

    @staticmethod
    def __find_profile_in_tree(profile_url: str, profile_tree: Mapping[str, any]) -> Optional[Mapping[str, any]]:
        """
        Searches for a profile in the given profile tree by its URL
        :param profile_url: URL of the profile to search for
        :param profile_tree: Profile tree to search in
        :return: Profile tree entry representing the profile or `None` if no entry matches
        """
        if profile_tree.get('url') == profile_url:
            return profile_tree
        else:
            results = [ProfileDetailGenerator.__find_profile_in_tree(profile_url, tree)
                        for tree in profile_tree.get('children', [])]
            results = list(filter(lambda t: t is not None, results))
            return results[0] if len(results) > 0 else None

    @staticmethod
    def __is_profile_selectable(profile_url: str, profile_tree: Mapping[str, any]) -> bool:
        """
        Searches the profile tree to determine whether a profile (identified by the provided URL) is selectable. Returns
        False if the profile is not present in the tree or has no attribute 'selectable'
        :param profile_url: URL of the profile for which to determine whether it is selectable
        :param profile_tree: Profile tree to search
        :return: Boolean indicating whether profile is selectable
        """
        profile = ProfileDetailGenerator.__find_profile_in_tree(profile_url, profile_tree)
        return profile.get('selectable', False) if profile is not None else False

    @staticmethod
    def __get_fields_for_profile(profile_url: str, profile_tree: Mapping[str, any]) -> BulkTranslationDisplayElement:
        """
        Searches for the profile with the given profile URL in the given profile tree and returns its supported fields
        :param profile_url: URL of the profile to return the supported fields of
        :param profile_tree: Profile tree to search
        :return: `BulkTranslationDisplayElement` instances representing the supported fields names
        """
        profile = ProfileDetailGenerator.__find_profile_in_tree(profile_url, profile_tree)
        return profile.get('fields', [])

    def generate_profile_details_for_profiles_in_scope(self, scope: str,
                                                       cond: Optional[Callable[[Mapping[str, Any]], bool]] = None,
                                                       profile_tree: Mapping[str, any] = None
                                                       ) -> List[ProfileDetail]:
        """
        Generate profile details for all profiles within the given scope
        :param scope: The scope containing all the profiles to generated details for
        :param cond: Optional filter to match only certain StructureDefinition instances in scope
        :param profile_tree: Optional profile tree to determine whether a profile detail should be generated for a given
                             profile based on whether it is selectable
        :return: List of profile details for the given scope
        """
        self.__logger.info(f"Generating profile details for profiles in scope '{scope}'")
        if cond is None:
            def true(_: Any): return True
            cond = true
        profile_details = []
        profiles_in_scope = self.__get_profiles(scope)
        if len(profiles_in_scope) == 0:
            self.__logger.warning(f"No profiles in scope '{scope}' => No profile details will be generated")
            return profile_details
        for profile_entry in profiles_in_scope.values():
            sd = profile_entry.get("structureDefinition", {})
            if cond(sd):
                if profile_detail := self.generate_detail_for_profile(profile_entry, profile_tree):
                    profile_details.append(profile_detail)
            else:
                self.__logger.debug(f"Profile [url={sd.get('url')}] did not match conditions => Skipping")
        return profile_details

    @staticmethod
    def __get_profile_title_display(profile_snapshot: Mapping[str, any]) -> Optional[TranslationDisplayElement]:
        title = profile_snapshot.get('title')
        if title is None:
            return None
        else:
            _title = profile_snapshot.get('_title', {})
            return TranslationDisplayElement(
                original=title,
                translations=[
                    {'language': "de-DE", 'value': get_value_for_lang_code(_title, "de-DE")},
                    {'language': "en-US", 'value': get_value_for_lang_code(_title, "en-US")}
                ]
            )