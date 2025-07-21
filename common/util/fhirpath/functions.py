from typing import Optional, Iterable

from antlr4.ParserRuleContext import ParserRuleContext
from antlr4.tree.Tree import TerminalNode
from pydantic import conlist

from common.util.fhirpath import fhirpathParser, RULE_NAMES, get_rule_name


def unsupported_fhirpath_expr(
    c: ParserRuleContext,
    expected: str | conlist(str, min_length=1),
    cause: Optional[Exception] = None,
) -> ValueError:
    expected = expected if isinstance(expected, list) else [expected]
    expected = [f"'{s}'" for s in expected]
    err = ValueError(
        f"Unsupported {get_rule_name(c)} expression in FHIRPath expression @ [{c.start.start}, {c.stop.stop}]: "
        f"Expected one of {{{','.join(expected)}}}. Expression: {c.toStringTree(ruleNames=RULE_NAMES)}"
    )
    if cause:
        err.__cause__ = cause
    return err


def invalid_fhirpath_expr(
    c: ParserRuleContext, reason: str, cause: Optional[Exception] = None
) -> ValueError:
    err = ValueError(
        f"Invalid {get_rule_name(c)} expression in FHIRPath expression @ [{c.start.start}, {c.stop.stop}]: {reason}. "
        f"Expression: {c.toStringTree(ruleNames=RULE_NAMES)}"
    )
    if cause:
        err.__cause__ = cause
    return err


def get_symbol(expr: ParserRuleContext, strip: bool = True) -> Optional[str]:
    """
    Retrieves the symbol of the given (nested) expression

    :param expr:
    :param strip: If `True` removes leading and trailing quotes
    :return:
    """
    while not isinstance(expr, TerminalNode):
        match expr.getChildCount():
            case 1:
                expr = expr.getChild(0)
            case _:
                return None
    return expr.symbol.text.strip("'") if strip else expr.symbol.text


def get_path(expr: ParserRuleContext) -> (Optional[ParserRuleContext], Optional[str]):
    path = []
    while not isinstance(expr.getChild(2), fhirpathParser.FunctionInvocationContext):
        match expr:
            case fhirpathParser.InvocationExpressionContext() as iec:
                match iec.getChild(2):
                    case fhirpathParser.MemberInvocationContext() as mic:
                        path.append(get_symbol(mic))
                    case _ as c:
                        raise unsupported_fhirpath_expr(c, "member invocation")
                expr = expr.getChild(0)
            case fhirpathParser.TermExpressionContext() as tec:
                path.append(get_symbol(tec))
                expr = None
                break
            case fhirpathParser.MemberInvocationContext() as mic:
                path.append(get_symbol(mic))
            case _:
                break
    path.reverse()
    return expr, ".".join(path) if path else None


def join_fhirpath(*paths: str | None) -> str:
    """
    Joins individual FHIRPath expression strings together. `None` values, empty strings, and '$this' valued strings are
    ignored

    :param paths: List of FHIRPath expression strings
    :return: String of joined FHIRPath expressions or '$this' if none are provided
    """
    string = ".".join(
        filter(lambda x: x is not None and len(x) > 0 and x != "$this", paths)
    )
    return string if len(string) > 0 else "$this"
