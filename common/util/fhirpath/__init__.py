from antlr4.CommonTokenStream import CommonTokenStream
from antlr4.InputStream import InputStream
from antlr4.ParserRuleContext import ParserRuleContext

from common.util.fhirpath.fhirpathLexer import fhirpathLexer
from common.util.fhirpath.fhirpathListener import fhirpathListener
from common.util.fhirpath.fhirpathParser import fhirpathParser

# Aliases
FhirPathLexer = fhirpathLexer
FhirPathListener = fhirpathListener
FhirPathParser = fhirpathParser


_lexer = FhirPathLexer(InputStream(""))
_parser = FhirPathParser(CommonTokenStream(_lexer))
RULE_NAMES = _parser.ruleNames


def parser_for(fhir_path_expr: str) -> FhirPathParser:
    """
    Returns a parser object for the given FHIRPath expression string

    :param fhir_path_expr: String representing a FHIRPath expression
    :return: Parser object for parsed expression
    """
    lexer = FhirPathLexer(InputStream(fhir_path_expr))
    stream = CommonTokenStream(lexer)
    return FhirPathParser(stream)


def parse_expr(fhir_path_expr: str) -> fhirpathParser.EntireExpressionContext:
    """
    Parses the given FHIRPath expression string and returns the parse tree

    :param fhir_path_expr: String representing a FHIRPath expression
    :return: Parse tree of the FHIRPath expression
    """
    return parser_for(fhir_path_expr).entireExpression()


def get_rule_name(tree: ParserRuleContext) -> str:
    """
    Returns the rule name of the root node of the given parse tree

    :param tree: Root node of the parse tree
    :return: String representing the rule name
    """
    return RULE_NAMES[tree.getRuleIndex()] if hasattr(tree, "getRuleIndex") else str(tree)


def show_tree(tree: ParserRuleContext, pretty: bool = False) -> str:
    """
    Returns the string representation of the given parse tree. Note, this is not the original FHIRPath expression string

    :param tree: Parse tree to return string representation for
    :param pretty: If `True` returns an indented version of the parse tree
    :return: String representation of the parse tree
    """
    if pretty:
        return __show_pretty_tree(tree)
    else:
        return tree.toStringTree(recog=_parser)


def __show_pretty_tree(tree: ParserRuleContext, _indent: int = 0) -> str:
    spaces = '  ' * _indent
    if tree.getChildCount() == 0:
        return f"{spaces}{tree.getText()}"

    rule_name = get_rule_name(tree)
    parent_str = f"{spaces}{rule_name}"

    child_strs = [__show_pretty_tree(tree.getChild(i), _indent + 1) for i in range(tree.getChildCount())]
    return parent_str + '\n' + '\n'.join(child_strs)