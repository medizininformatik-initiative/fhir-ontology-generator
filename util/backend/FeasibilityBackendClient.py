from __future__ import annotations

from typing import Mapping, Optional, TypedDict

from requests import Session, Response
from requests.auth import AuthBase

from core.exceptions.http.ClientError import ClientError
from core.exceptions.http.ServerError import ServerError


def _format_query_params(query_params: Mapping[str, any]) -> Mapping[str, any]:
    return {k.replace('_', '-'): v for k, v in query_params.items()}


def _insert_path_params(url: str, **path_params: str) -> str:
    split = url.split("?", 1)
    return split[0].format(path_params) + split[1] if len(split) > 1 else ""


def _merge_urls(url_a: str, url_b: str) -> str:
    if len(url_a) == 0 and len(url_b) == 0:
        return ""
    match (url_a.endswith("/") + url_b.startswith("/")):
        case 0:
            return url_a + "/" + url_b
        case 1:
            return url_a + url_b
        case 2:
            return url_a + url_b.lstrip("/")


def _raise_appropriate_exception(response: Response) -> None:
    if 400 <= response.status_code < 500:
        raise ClientError(response.status_code, response.reason)
    elif 500 <= response.status_code < 600:
        raise ServerError(response.status_code, response.reason)


class SiteResult(TypedDict):
    siteName: str
    numberOfPatients: int


class QueryStatus(TypedDict):
    totalNumberOfPatients: int
    queryId: str
    resultLines: list[SiteResult]


class QuerySlots(TypedDict):
    used: int
    total: int


class SearchFilter(TypedDict):
    name: str
    values: list[str]


class TerminologySystem(TypedDict):
    url: str
    name: str


class TranslationEntry(TypedDict):
    language: str
    value: str


class DisplayEntry(TypedDict):
    original: str
    translations: list[TranslationEntry]


class ElasticSearchResultEntry(TypedDict):
    display: DisplayEntry
    id: str
    availability: int
    context: str
    terminology: str
    termcode: str
    kdsModule: str
    selectable: bool


class ElasticSearchResult(TypedDict):
    totalHits: int
    results: list[ElasticSearchResultEntry]


class Relative(TypedDict):
    name: str
    contextualizedTermcodeHash: str


class RelationEntry(TypedDict):
    display: DisplayEntry
    parents: list[Relative]
    children: list[Relative]
    relatedTerms: list[Relative]


class TermCode(TypedDict):
    system: str
    code: str
    display: str
    version: str


class AttributeDefinition(TypedDict):
    allowedUnits: list[TermCode]
    attributeCode: TermCode
    max: int
    min: int
    optional: bool
    precision: int
    referencedCriteriaSet: str
    referencedValueSet: str
    type: str


class UIProfile(TypedDict):
    name: str
    timeRestrictionAllowed: bool
    valueDefinition: AttributeDefinition
    attributeDefinition: list[AttributeDefinition]


class CriteriaProfileData(TypedDict):
    id: str
    display: DisplayEntry
    context: TermCode
    termCodes: list[TermCode]
    uiprofile: UIProfile


class CodeableConceptSearchResultItem(TypedDict):
    termCode: TermCode
    display: DisplayEntry


class CodeableConceptSearchResult(TypedDict):
    totalHits: int
    results: list[CodeableConceptSearchResultItem]


class ProfileTreeNode(TypedDict):
    id: str
    children: list[ProfileTreeNode]
    name: str
    display: DisplayEntry


class ProfileDataField(TypedDict):
    id: str
    display: DisplayEntry
    description: DisplayEntry
    type: str
    recommended: bool
    required: bool
    children: list[ProfileDataField]


class ProfileDataFilter(TypedDict):
    type: str
    name: str
    ui_type: str
    referencedCriteriaSet: str


class ProfileData(TypedDict):
    url: str
    display: DisplayEntry
    fields: list[ProfileDataField]
    filters: list[ProfileDataFilter]
    errorCode: str
    errorCause: str


class FeasibilityBackendClient:
    __session: Session
    __base_url: str
    __timeout: float

    def __init__(self, base_url: str, auth: type[AuthBase] = None, timeout: float = 60):
        self.__session = Session()
        self.__session.auth = auth
        self.__base_url = base_url
        self.__timeout = timeout

    def __del__(self):
        self.__session.close()

    def get(self, url, headers: Mapping[str, str] = None, path_params: Mapping[str, str] = None,
            **query_params) -> Response:
        request_url = _insert_path_params(url, **path_params) if path_params is not None else url
        response = self.__session.get(request_url, params=_format_query_params(query_params), headers=headers,
                                      timeout=self.__timeout)
        if response.ok: return response
        else: _raise_appropriate_exception(response)

    def post(self, url, body: str, headers: Mapping[str, str] = None, path_params: Mapping[str, str] = None,
            **query_params) -> Response:
        request_url = _insert_path_params(url, **path_params) if path_params is not None else url
        response = self.__session.post(request_url, data=body, params=_format_query_params(query_params),
                                       headers=headers, timeout=self.__timeout)
        if response.ok: return response
        else: _raise_appropriate_exception(response)

    def delete(self, url, headers: Mapping[str, str] = None, path_params: Mapping[str, str] = Response,
               **query_params) -> Response:
        request_url = _insert_path_params(url, **path_params) if path_params is not None else url
        response = self.__session.delete(request_url, params=query_params, headers=headers, timeout=self.__timeout)
        if response.ok:
            return response
        else:
            _raise_appropriate_exception(response)

    def query(self, query: str) -> str:
        location = self.post(_merge_urls(self.__base_url, "/query"), body=query).headers.get('Location')
        if location is None: raise Exception("No Location header in response")
        else: return location

    def validate_query(self, query: str) -> tuple[bool, Optional[dict]]:
        try:
            response = self.post(_merge_urls(self.__base_url, "/query/validate"), body=query)
            return True, response.json()
        except ClientError as e:
            if e.status_code == 400: return False, None # Invalid SQ
            else: raise

    def get_query_summary_result(self, query_id: str) -> QueryStatus:
        return self.get(_merge_urls(self.__base_url, "query/{query_id}/summary-result"),
                        path_params={'query_id': query_id}).json()

    def delete_saved_query(self, query_id: str) -> QuerySlots:
        return self.delete(_merge_urls(self.__base_url, "query/{query_id}/saved"),
                           path_params={'query_id': query_id}).json()

    # NOTE: It is likely that a username has to be supplied via the Authorization header for this request to work
    def get_saved_query_slots(self) -> QuerySlots:
        return self.get(_merge_urls(self.__base_url, "query/saved-query-slots")).json()

    def get_terminology_search_filter(self) -> list[SearchFilter]:
        return self.get(_merge_urls(self.__base_url, "terminology/search/filter")).json()

    def get_terminology_systems(self) -> list[TerminologySystem]:
        return self.get(_merge_urls(self.__base_url, "terminology/systems")).json()

    def search_terminology_entries(self, search_term: str, contexts: Optional[list[str]] = None,
                                   terminologies: Optional[list[str]] = None, kds_modules: Optional[list[str]] = None,
                                   criteria_sets: Optional[list[str]] = None, availability: bool = False,
                                   page_size: int = 20, page: int = 0) -> ElasticSearchResult:
        return self.get(_merge_urls(self.__base_url, "/terminology/entry/search"), searchterm=search_term,
                        contexts=contexts, terminologies=terminologies, kds_modules=kds_modules,
                        criteria_sets=criteria_sets, availability=availability, page_size=page_size, page=page).json()

    def get_criterion_relations(self, criterion_id: str) -> RelationEntry:
        return self.get(_merge_urls(self.__base_url, "/terminology/entry/{id}/relations"),
                        path_params={'id': criterion_id}).json()

    def get_criterion(self, criterion_id: str) -> ElasticSearchResult:
        return self.get(_merge_urls(self.__base_url, "/terminology/entry/{id}"),
                        path_params={'id': criterion_id}).json()

    def get_criteria_profile_data(self, criteria_ids: list[str]) -> CriteriaProfileData:
        return self.get(_merge_urls(self.__base_url, "/terminology/criteria-profile-data"),
                        path_params={'ids': ','.join(criteria_ids)}).json()

    def search_codeable_concepts(self, search_term: str, value_sets: list[str] = None, page_size: int = 20,
                                 page: int = 0) -> CodeableConceptSearchResult:
        return self.get(_merge_urls(self.__base_url, "/codeable-concept/entry/search"), searchterm=search_term,
                        value_sets=value_sets, page_size=page_size, page=page).json()

    def get_codeable_concept(self, concept_id: str) -> CodeableConceptSearchResultItem:
        return self.get(_merge_urls(self.__base_url, "/codeable-concept/entry/{id}"),
                        path_params={'id': concept_id}).json()

    def get_dse_profile_tree(self) -> ProfileTreeNode:
        return self.get(_merge_urls(self.__base_url, "/dse/profile-tree")).json()

    def get_dse_profile_data(self, profile_ids: list[str]) -> ProfileData:
        return self.get(_merge_urls(self.__base_url, "/dse/profile-data"),
                        profile_ids=','.join(profile_ids)).json()
