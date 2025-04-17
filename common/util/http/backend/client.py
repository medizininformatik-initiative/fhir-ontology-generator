from __future__ import annotations

from typing import Optional, TypedDict
from requests.auth import AuthBase

from common.util.http.client import BaseClient
from common.util.http.exceptions import ClientError


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

class QueryListEntry(TypedDict):
    id: int
    label: str
    comment: str
    createdAt: str
    totalNumberOfPatients: int
    isValid: bool

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


class FeasibilityBackendClient(BaseClient):

    def __init__(self, base_url: str, auth: Optional[type[AuthBase]] = None, cert: Optional[tuple[str, str]] = None,
                 timeout: float = 60):
        super().__init__(base_url, auth, cert, timeout)

    def __del__(self):
        super().__del__()

    def query(self, query: str) -> str:
        headers = {'Content-Type': "application/json"}
        location = (self.post("/query", headers=headers, body=query)
                    .headers.get('Location'))
        if location is None: raise Exception("No Location header in response")
        else: return location

    def validate_query(self, query: str) -> tuple[bool, Optional[dict]]:
        try:
            headers = {'Content-Type': "application/json"}
            response = self.post("/query/validate", headers=headers, body=query)
            return True, response.json()
        except ClientError as err:
            if err.status_code == 400: return False, None # Invalid SQ
            else: raise

    def get_query_summary_result(self, query_id: str) -> QueryStatus:
        return self.get("/query/{query_id}/summary-result", path_params={'query_id': query_id}).json()

    def delete_saved_query(self, query_id: str) -> QuerySlots:
        return self.delete("/query/{query_id}/saved", path_params={'query_id': query_id}).json()

    def get_current_querys(self)-> list[QueryListEntry]:
        return self.get("/query").json()

    # NOTE: It is likely that a username has to be supplied via the Authorization header for this request to work
    def get_saved_query_slots(self) -> QuerySlots:
        return self.get("query/saved-query-slots").json()

    def get_terminology_search_filter(self) -> list[SearchFilter]:
        return self.get("terminology/search/filter").json()

    def get_terminology_systems(self) -> list[TerminologySystem]:
        return self.get("terminology/systems").json()

    def search_terminology_entries(self, search_term: str, contexts: Optional[list[str]] = None,
                                   terminologies: Optional[list[str]] = None, kds_modules: Optional[list[str]] = None,
                                   criteria_sets: Optional[list[str]] = None, availability: bool = False,
                                   page_size: int = 20, page: int = 0) -> ElasticSearchResult:
        query_params = {'searchterm': search_term, 'contexts': contexts, 'terminologies': terminologies,
                        'kds_modules': kds_modules, 'criteria_sets': criteria_sets, 'availability': availability,
                        'page_size': page_size, 'page': page}
        return self.get("/terminology/entry/search", query_params=query_params).json()

    def get_criterion_relations(self, criterion_id: str) -> RelationEntry:
        return self.get("/terminology/entry/{id}/relations", path_params={'id': criterion_id}).json()

    def get_criterion(self, criterion_id: str) -> ElasticSearchResult:
        return self.get("/terminology/entry/{id}", path_params={'id': criterion_id}).json()

    def get_criteria_profile_data(self, criteria_ids: list[str]) -> list[CriteriaProfileData]:
        return self.get("/terminology/criteria-profile-data", query_params={'ids': ','.join(criteria_ids)}).json()

    def search_codeable_concepts(self, search_term: str, value_sets: list[str] = None, page_size: int = 20,
                                 page: int = 0) -> CodeableConceptSearchResult:
        query_params = {'searchterm': search_term, 'value_sets': value_sets, 'page_size': page_size, 'page': page}
        return self.get("/codeable-concept/entry/search", query_params=query_params).json()

    def get_codeable_concept(self, concept_id: str) -> CodeableConceptSearchResultItem:
        return self.get("/codeable-concept/entry/{id}", path_params={'id': concept_id}).json()

    def get_dse_profile_tree(self) -> ProfileTreeNode:
        return self.get("/dse/profile-tree").json()

    def get_dse_profile_data(self, profile_ids: list[str]) -> ProfileData:
        return self.get("/dse/profile-data", query_params={'profile_ids': ','.join(profile_ids)}).json()
