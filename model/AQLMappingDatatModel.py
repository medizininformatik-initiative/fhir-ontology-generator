import json

from typing import List

from model.UiDataModel import del_keys, del_none

from model.UiDataModel import TermCode


class ValuePathElement:
    def __init__(self, open_ehr_type, archetype_id):
        self.openEhrType = open_ehr_type
        self.archetypeId = archetype_id

    def __repr__(self):
        return self.openEhrType + self.archetypeId


ValuePathList = List[ValuePathElement]


class AQLMapEntry:
    DO_NOT_SERIALIZE = ["DO_NOT_SERIALIZE", "valueOfInterests"]

    def __init__(self, term_code: TermCode, open_ehr_type, term_code_path, term_code_path_elements,
                 value_path, value_path_elements):
        self.valueOfInterests = []
        self.key = term_code
        self.openEhrType = open_ehr_type
        self.valuePath = value_path
        self.valuePathElements = value_path_elements
        self.termCodePath = term_code_path
        self.termCodePathElements = term_code_path_elements

    def __eq__(self, other):
        return self.key == other.key

    def __ne__(self, other):
        return not self.__eq__(other)

    def __lt__(self, other):
        return self.key < other.key

    def __hash__(self):
        return hash(self.key)

    def to_json(self):
        return json.dumps(self, default=lambda o: del_none(
            del_keys(o.__dict__, self.DO_NOT_SERIALIZE)), sort_keys=True, indent=4)
