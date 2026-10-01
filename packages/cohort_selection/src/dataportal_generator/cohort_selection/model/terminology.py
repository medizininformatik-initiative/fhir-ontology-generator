from typing import List, Dict, Set, Mapping, Tuple, Any

from pydantic import BaseModel, Field, model_serializer
from pydantic_core.core_schema import SerializerFunctionWrapHandler

from common.model.localization import TranslationDisplayElement
from dataportal_generator.common.model.terminology import TermCode, TreeMapList, TreeMap
from dataportal_generator.common.log.functions import get_logger
from typing_extensions import deprecated


_logger = get_logger(__file__)


class ContextualizedTermCode(BaseModel):
    context: TermCode
    term_code: TermCode

    @deprecated("Use ``ContextualizedTermCode.model_dump()`` directly")
    def to_dict(self, **kwargs):
        return self.model_dump(**kwargs)


class ContextualizedTermCodeInfo(BaseModel):
    term_code: TermCode
    context: TermCode
    module: TranslationDisplayElement
    children_count: int = 0
    designations: list[Designation] = Field(default_factory=list)
    siblings: list[ContextualizedTermCode] = Field(default_factory=list)
    recalculated: bool = Field(default=False, exclude=True)

    @model_serializer(mode="wrap")
    def _serialize_model(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        if not self.designations:
            self.designations = [
                Designation(language="default", display=self.term_code.display)
            ]
        if not self.recalculated:
            _logger.warning(
                f"Ensure you call update_children_count before calling to_dict, otherwise children_count will be incorrect."
            )
        return handler(self)

    @deprecated("Use ``ContextualizedTermCodeInfo.model_dump()`` directly")
    def to_dict(self, **kwargs) -> dict[str, Any]:
        return self.model_dump(**kwargs)


class ContextualizedTermCodeInfoList(BaseModel):
    entries: List[ContextualizedTermCodeInfo] = Field(default_factory=list)

    @model_serializer(mode="plain")
    def _model_serializer(self) -> list[dict[str, Any]]:
        return [entry.model_dump() for entry in self.entries]

    def update_descendant_count(self, tree_map_list: TreeMapList):
        """
        Updates the descendant count of entries of this instance

        :param tree_map_list: List of tree maps to aggregate descendants in
        """
        count_maps = {
            f"{tree_map.system}{('|' + tree_map.version) if tree_map.version else ''}": self.__get_descendant_or_self_count_map(
                tree_map
            )
            for tree_map in tree_map_list.entries
        }
        for entry in self.entries:
            term_code = entry.term_code
            if count_map := count_maps.get(f"{term_code.system}{('|' + term_code.version) if term_code.version else ''}"):
                count = count_map.get(term_code.code, 0)
                entry.children_count = count
                entry.recalculated = True
            else:
                _logger.warning(
                    f"No tree map for code system '{term_code.system}'"
                    f"{('and version ' + term_code.version) if term_code.version else ''} => Skipping"
                )
                continue

    def __get_descendant_or_self_count_map(
        self, tree_map: TreeMap
    ) -> Mapping[str, int]:
        """
        Builds up the descendant-or-self count mapping for the given tree map

        :param tree_map: `TreeMap` instance to build up descendant count mapping for
        :return: Descendant count mapping
        """
        m = {}
        entries = tree_map.entries
        for k, v in entries.items():
            if len(v.children) == 0:
                m[k] = 1
                if len(v.parents) > 0:
                    for p_key in v.parents:
                        self.__traverse_parent(p_key, {k}, tree_map, m)
        return m

    def __traverse_parent(
        self,
        parent_key: str,
        descendants: Set[str],
        tree_map: TreeMap,
        count_map: Dict[str, Tuple[int, Set[str]] | int],
    ):
        """
        Internal method for traversing `tree_map` upwards and build up the descendant count map `count_map`. Note that
        this method is built to handle poly hierarchies (like SNOMED CT) and as such there might be faster algorithms
        for other types of hierarchies. If the method was called on all parents of all leaf concepts the count map will
        be complete

        :param parent_key: Key of the parent concept in the tree map
        :param descendants: Set of descendant concepts of a child concept of the parent concept
        :param tree_map: Tree map providing information on parents and children of concepts
        :param count_map: Associates a concept to its currently identified set of descendant concepts and of how many
                          of its child concepts descendants where already merged into its descendant set. If all
                          children contributed their descendants than the value will be replaced by the total descendant
                          count identified
        """
        parent = tree_map.entries[parent_key]
        if parent_key not in count_map:
            visits = 0
            p_descendants = {parent_key}
        else:
            visits, p_descendants = count_map[parent_key]
        visits += 1
        p_descendants.update(descendants)
        if len(parent.children) <= visits:
            count_map[parent_key] = len(p_descendants)
            for p_parent_key in parent.parents:
                self.__traverse_parent(p_parent_key, p_descendants, tree_map, count_map)
        else:
            count_map[parent_key] = (visits, p_descendants)

    @deprecated("Use ``ContextualizedTermCodeInfoList.model_dump_json()`` directly")
    def to_json(self, **kwargs):
        """
        Builds a JSON string representation of this instance

        :return: JSON string
        """
        return self.model_dump_json(**kwargs)
