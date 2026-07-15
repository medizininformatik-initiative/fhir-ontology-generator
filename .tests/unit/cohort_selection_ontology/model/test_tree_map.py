from collections.abc import Mapping

import pytest

from cohort_selection_ontology.model.tree_map import (
    TreeMapList,
    ContextualizedTermCodeInfoList,
    ContextualizedTermCodeInfo,
    TreeMap,
    TermEntryNode,
)
from cohort_selection_ontology.model.ui_data import TermCode, Module

########################################################################################################################
# ... ContextualizedTermCodeInfoListTest ...............................................................................
########################################################################################################################

_TEST_CONTEXT = TermCode(system="http://context.org", code="test", display="Test")
_TEST_MODULE = Module(code="test", display="Test")


@pytest.mark.parametrize(
    argnames=["instance", "tree_map_list", "counts"],
    argvalues=[
        (
            ContextualizedTermCodeInfoList(
                entries=[
                    ContextualizedTermCodeInfo(
                        term_code=TermCode(
                            system="http://snomed.info/sct",
                            code="165197003",
                            display="Diagnostic assessment",
                            version="http://snomed.info/sct/900000000000207008/version/20240701",
                        ),
                        context=_TEST_CONTEXT,
                        module=_TEST_MODULE,
                    ),
                    ContextualizedTermCodeInfo(
                        term_code=TermCode(
                            system="http://snomed.info/sct",
                            code="363679005",
                            display="Imaging",
                            version="http://snomed.info/sct/900000000000207008/version/20240701",
                        ),
                        context=_TEST_CONTEXT,
                        module=_TEST_MODULE,
                    ),
                    ContextualizedTermCodeInfo(
                        term_code=TermCode(
                            system="http://snomed.info/sct",
                            code="387713003",
                            display="Surgical procedure",
                            version="http://snomed.info/sct/900000000000207008/version/20240701",
                        ),
                        context=_TEST_CONTEXT,
                        module=_TEST_MODULE,
                    ),
                    ContextualizedTermCodeInfo(
                        term_code=TermCode(
                            system="http://snomed.info/sct",
                            code="18629005",
                            display="Administration of drug or medicament",
                            version="http://snomed.info/sct/900000000000207008/version/20240701",
                        ),
                        context=_TEST_CONTEXT,
                        module=_TEST_MODULE,
                    ),
                    ContextualizedTermCodeInfo(
                        term_code=TermCode(
                            system="http://snomed.info/sct",
                            code="277132007",
                            display="Therapeutic procedure",
                            version="http://snomed.info/sct/900000000000207008/version/20240701",
                        ),
                        context=_TEST_CONTEXT,
                        module=_TEST_MODULE,
                    ),
                    ContextualizedTermCodeInfo(
                        term_code=TermCode(
                            system="http://snomed.info/sct",
                            code="394841004",
                            display="Other category",
                            version="http://snomed.info/sct/900000000000207008/version/20240701",
                        ),
                        context=_TEST_CONTEXT,
                        module=_TEST_MODULE,
                    ),
                ]
            ),
            TreeMapList(
                module_name=_TEST_MODULE.code,
                entries=[
                    TreeMap(
                        context=_TEST_CONTEXT,
                        system="http://snomed.info/sct",
                        version="http://snomed.info/sct/900000000000207008/version/20240701",
                        entries={
                            "165197003": TermEntryNode(
                                term_code=TermCode(
                                    system="http://snomed.info/sct",
                                    code="165197003",
                                    display="Diagnostic assessment",
                                ),
                                parents=[],
                                children=[],
                            ),
                            "363679005": TermEntryNode(
                                term_code=TermCode(
                                    system="http://snomed.info/sct",
                                    code="363679005",
                                    display="Imaging",
                                ),
                                parents=[],
                                children=[],
                            ),
                            "387713003": TermEntryNode(
                                term_code=TermCode(
                                    system="http://snomed.info/sct",
                                    code="387713003",
                                    display="Surgical procedure",
                                ),
                                parents=[],
                                children=[],
                            ),
                            "18629005": TermEntryNode(
                                term_code=TermCode(
                                    system="http://snomed.info/sct",
                                    code="18629005",
                                    display="Administration of drug or medicament",
                                ),
                                parents=[],
                                children=[],
                            ),
                            "277132007": TermEntryNode(
                                term_code=TermCode(
                                    system="http://snomed.info/sct",
                                    code="277132007",
                                    display="Therapeutic procedure",
                                ),
                                parents=[],
                                children=[],
                            ),
                            "394841004": TermEntryNode(
                                term_code=TermCode(
                                    system="http://snomed.info/sct",
                                    code="394841004",
                                    display="Other category",
                                ),
                                parents=[],
                                children=[],
                            ),
                        },
                    )
                ],
            ),
            {
                "165197003": 1,
                "363679005": 1,
                "387713003": 1,
                "18629005": 1,
                "277132007": 1,
                "394841004": 1,
            },
        ),
        (
            ContextualizedTermCodeInfoList(
                entries=[
                    ContextualizedTermCodeInfo(
                        term_code=TermCode(
                            system="http://codesystem.org",
                            code="a",
                            display="A",
                            version="1.0.0",
                        ),
                        context=_TEST_CONTEXT,
                        module=_TEST_MODULE,
                    ),
                    ContextualizedTermCodeInfo(
                        term_code=TermCode(
                            system="http://codesystem.org",
                            code="b",
                            display="B",
                            version="1.0.0",
                        ),
                        context=_TEST_CONTEXT,
                        module=_TEST_MODULE,
                    ),
                    ContextualizedTermCodeInfo(
                        term_code=TermCode(
                            system="http://codesystem.org",
                            code="c",
                            display="C",
                            version="1.0.0",
                        ),
                        context=_TEST_CONTEXT,
                        module=_TEST_MODULE,
                    ),
                    ContextualizedTermCodeInfo(
                        term_code=TermCode(
                            system="http://codesystem.org",
                            code="d",
                            display="D",
                            version="1.0.0",
                        ),
                        context=_TEST_CONTEXT,
                        module=_TEST_MODULE,
                    ),
                    ContextualizedTermCodeInfo(
                        term_code=TermCode(
                            system="http://codesystem.org",
                            code="e",
                            display="E",
                            version="1.0.0",
                        ),
                        context=_TEST_CONTEXT,
                        module=_TEST_MODULE,
                    ),
                    ContextualizedTermCodeInfo(
                        term_code=TermCode(
                            system="http://codesystem.org",
                            code="f",
                            display="F",
                            version="1.0.0",
                        ),
                        context=_TEST_CONTEXT,
                        module=_TEST_MODULE,
                    ),
                    ContextualizedTermCodeInfo(
                        term_code=TermCode(
                            system="http://codesystem.org",
                            code="g",
                            display="G",
                            version="1.0.0",
                        ),
                        context=_TEST_CONTEXT,
                        module=_TEST_MODULE,
                    ),
                    ContextualizedTermCodeInfo(
                        term_code=TermCode(
                            system="http://codesystem.org",
                            code="h",
                            display="H",
                            version="1.0.0",
                        ),
                        context=_TEST_CONTEXT,
                        module=_TEST_MODULE,
                    ),
                    ContextualizedTermCodeInfo(
                        term_code=TermCode(
                            system="http://codesystem.org",
                            code="i",
                            display="I",
                            version="1.0.0",
                        ),
                        context=_TEST_CONTEXT,
                        module=_TEST_MODULE,
                    ),
                    ContextualizedTermCodeInfo(
                        term_code=TermCode(
                            system="http://codesystem.org",
                            code="j",
                            display="J",
                            version="1.0.0",
                        ),
                        context=_TEST_CONTEXT,
                        module=_TEST_MODULE,
                    ),
                    ContextualizedTermCodeInfo(
                        term_code=TermCode(
                            system="http://codesystem.org",
                            code="k",
                            display="K",
                            version="1.0.0",
                        ),
                        context=_TEST_CONTEXT,
                        module=_TEST_MODULE,
                    ),
                    ContextualizedTermCodeInfo(
                        term_code=TermCode(
                            system="http://codesystem.org",
                            code="l",
                            display="L",
                            version="1.0.0",
                        ),
                        context=_TEST_CONTEXT,
                        module=_TEST_MODULE,
                    ),
                    ContextualizedTermCodeInfo(
                        term_code=TermCode(
                            system="http://codesystem.org",
                            code="m",
                            display="M",
                            version="1.0.0",
                        ),
                        context=_TEST_CONTEXT,
                        module=_TEST_MODULE,
                    ),
                    ContextualizedTermCodeInfo(
                        term_code=TermCode(
                            system="http://codesystem.org",
                            code="n",
                            display="N",
                            version="1.0.0",
                        ),
                        context=_TEST_CONTEXT,
                        module=_TEST_MODULE,
                    ),
                    ContextualizedTermCodeInfo(
                        term_code=TermCode(
                            system="http://codesystem.org",
                            code="o",
                            display="O",
                            version="1.0.0",
                        ),
                        context=_TEST_CONTEXT,
                        module=_TEST_MODULE,
                    ),
                    ContextualizedTermCodeInfo(
                        term_code=TermCode(
                            system="http://codesystem.org",
                            code="p",
                            display="P",
                            version="1.0.0",
                        ),
                        context=_TEST_CONTEXT,
                        module=_TEST_MODULE,
                    ),
                    ContextualizedTermCodeInfo(
                        term_code=TermCode(
                            system="http://codesystem.org",
                            code="q",
                            display="Q",
                            version="1.0.0",
                        ),
                        context=_TEST_CONTEXT,
                        module=_TEST_MODULE,
                    ),
                    ContextualizedTermCodeInfo(
                        term_code=TermCode(
                            system="http://codesystem.org",
                            code="r",
                            display="R",
                            version="1.0.0",
                        ),
                        context=_TEST_CONTEXT,
                        module=_TEST_MODULE,
                    ),
                    ContextualizedTermCodeInfo(
                        term_code=TermCode(
                            system="http://codesystem.org",
                            code="s",
                            display="S",
                            version="1.0.0",
                        ),
                        context=_TEST_CONTEXT,
                        module=_TEST_MODULE,
                    ),
                    ContextualizedTermCodeInfo(
                        term_code=TermCode(
                            system="http://codesystem.org",
                            code="t",
                            display="T",
                            version="1.0.0",
                        ),
                        context=_TEST_CONTEXT,
                        module=_TEST_MODULE,
                    ),
                    ContextualizedTermCodeInfo(
                        term_code=TermCode(
                            system="http://codesystem.org",
                            code="u",
                            display="U",
                            version="1.0.0",
                        ),
                        context=_TEST_CONTEXT,
                        module=_TEST_MODULE,
                    ),
                ]
            ),
            TreeMapList(
                module_name=_TEST_MODULE.code,
                entries=[
                    TreeMap(
                        context=_TEST_CONTEXT,
                        system="http://codesystem.org",
                        version="1.0.0",
                        entries={
                            "a": TermEntryNode(
                                term_code=TermCode(
                                    system="http://codesystem.org",
                                    code="a",
                                    display="A",
                                ),
                                parents=[],
                                children=["c", "d", "e"],
                            ),
                            "b": TermEntryNode(
                                term_code=TermCode(
                                    system="http://codesystem.org",
                                    code="b",
                                    display="B",
                                ),
                                parents=[],
                                children=["e", "f", "g"],
                            ),
                            "c": TermEntryNode(
                                term_code=TermCode(
                                    system="http://codesystem.org",
                                    code="c",
                                    display="C",
                                ),
                                parents=["a"],
                                children=["h", "i"],
                            ),
                            "d": TermEntryNode(
                                term_code=TermCode(
                                    system="http://codesystem.org",
                                    code="d",
                                    display="D",
                                ),
                                parents=["a"],
                                children=["i", "j"],
                            ),
                            "e": TermEntryNode(
                                term_code=TermCode(
                                    system="http://codesystem.org",
                                    code="e",
                                    display="E",
                                ),
                                parents=["a", "b"],
                                children=["j", "k", "r"],
                            ),
                            "f": TermEntryNode(
                                term_code=TermCode(
                                    system="http://codesystem.org",
                                    code="f",
                                    display="F",
                                ),
                                parents=["b"],
                                children=["l", "t"],
                            ),
                            "g": TermEntryNode(
                                term_code=TermCode(
                                    system="http://codesystem.org",
                                    code="g",
                                    display="G",
                                ),
                                parents=["b"],
                                children=["m"],
                            ),
                            "h": TermEntryNode(
                                term_code=TermCode(
                                    system="http://codesystem.org",
                                    code="h",
                                    display="H",
                                ),
                                parents=["c"],
                                children=["n", "o"],
                            ),
                            "i": TermEntryNode(
                                term_code=TermCode(
                                    system="http://codesystem.org",
                                    code="i",
                                    display="I",
                                ),
                                parents=["c", "d"],
                                children=["n"],
                            ),
                            "j": TermEntryNode(
                                term_code=TermCode(
                                    system="http://codesystem.org",
                                    code="j",
                                    display="J",
                                ),
                                parents=["d", "e"],
                                children=["o", "p", "q"],
                            ),
                            "k": TermEntryNode(
                                term_code=TermCode(
                                    system="http://codesystem.org",
                                    code="k",
                                    display="K",
                                ),
                                parents=["e"],
                                children=["q"],
                            ),
                            "l": TermEntryNode(
                                term_code=TermCode(
                                    system="http://codesystem.org",
                                    code="l",
                                    display="L",
                                ),
                                parents=["f"],
                                children=["r", "s"],
                            ),
                            "m": TermEntryNode(
                                term_code=TermCode(
                                    system="http://codesystem.org",
                                    code="m",
                                    display="M",
                                ),
                                parents=["g"],
                                children=["s", "t"],
                            ),
                            "n": TermEntryNode(
                                term_code=TermCode(
                                    system="http://codesystem.org",
                                    code="n",
                                    display="N",
                                ),
                                parents=["h", "i"],
                            ),
                            "o": TermEntryNode(
                                term_code=TermCode(
                                    system="http://codesystem.org",
                                    code="o",
                                    display="O",
                                ),
                                parents=["h", "j"],
                            ),
                            "p": TermEntryNode(
                                term_code=TermCode(
                                    system="http://codesystem.org",
                                    code="p",
                                    display="P",
                                ),
                                parents=["j"],
                            ),
                            "q": TermEntryNode(
                                term_code=TermCode(
                                    system="http://codesystem.org",
                                    code="q",
                                    display="Q",
                                ),
                                parents=["j", "k"],
                            ),
                            "r": TermEntryNode(
                                term_code=TermCode(
                                    system="http://codesystem.org",
                                    code="r",
                                    display="R",
                                ),
                                parents=["e", "l"],
                            ),
                            "s": TermEntryNode(
                                term_code=TermCode(
                                    system="http://codesystem.org",
                                    code="s",
                                    display="S",
                                ),
                                parents=["l", "m"],
                            ),
                            "t": TermEntryNode(
                                term_code=TermCode(
                                    system="http://codesystem.org",
                                    code="t",
                                    display="T",
                                ),
                                parents=["f", "m"],
                            ),
                            "u": TermEntryNode(
                                term_code=TermCode(
                                    system="http://codesystem.org",
                                    code="u",
                                    display="U",
                                ),
                                parents=[],
                            ),
                        },
                    )
                ],
            ),
            {
                "a": 13,
                "b": 14,
                "c": 5,
                "d": 7,
                "e": 7,
                "f": 5,
                "g": 4,
                "h": 3,
                "i": 2,
                "j": 4,
                "k": 2,
                "l": 3,
                "m": 3,
                "n": 1,
                "o": 1,
                "p": 1,
                "q": 1,
                "r": 1,
                "s": 1,
                "t": 1,
                "u": 1,
            },
        ),
    ],
    ids=["flat-hierarchy-between-concepts", "poly-hierarchy"],
    scope="module",
)
def test_update_descendant_count(
    instance: ContextualizedTermCodeInfoList,
    tree_map_list: TreeMapList,
    counts: Mapping[str, int],
):
    instance.update_descendant_count(tree_map_list)
    for ctci in instance.entries:
        assert ctci.recalculated, (
            "The contained ContextualizedTermCodeInfo object should indicate that their descendant count has been "
            "recalculated"
        )
        assert (
            ctci.children_count == counts[ctci.term_code.code]
        ), "Incorrect number of concepts qualifying as 'descendants or self' of the concept was calculated"


########################################################################################################################
