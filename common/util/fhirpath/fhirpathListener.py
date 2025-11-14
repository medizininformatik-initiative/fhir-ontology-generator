# Generated from common/resources/fhirpath/fhirpath.g4 by ANTLR 4.9.3
from antlr4 import *

if __name__ is not None and "." in __name__:
    from .fhirpathParser import fhirpathParser
else:
    from fhirpathParser import fhirpathParser


# This class defines a complete listener for a parse tree produced by fhirpathParser.
class fhirpathListener(ParseTreeListener):

    # Enter a parse tree produced by fhirpathParser#entireExpression.
    def enterEntireExpression(self, ctx: fhirpathParser.EntireExpressionContext):
        pass

    # Exit a parse tree produced by fhirpathParser#entireExpression.
    def exitEntireExpression(self, ctx: fhirpathParser.EntireExpressionContext):
        pass

    # Enter a parse tree produced by fhirpathParser#indexerExpression.
    def enterIndexerExpression(self, ctx: fhirpathParser.IndexerExpressionContext):
        pass

    # Exit a parse tree produced by fhirpathParser#indexerExpression.
    def exitIndexerExpression(self, ctx: fhirpathParser.IndexerExpressionContext):
        pass

    # Enter a parse tree produced by fhirpathParser#polarityExpression.
    def enterPolarityExpression(self, ctx: fhirpathParser.PolarityExpressionContext):
        pass

    # Exit a parse tree produced by fhirpathParser#polarityExpression.
    def exitPolarityExpression(self, ctx: fhirpathParser.PolarityExpressionContext):
        pass

    # Enter a parse tree produced by fhirpathParser#additiveExpression.
    def enterAdditiveExpression(self, ctx: fhirpathParser.AdditiveExpressionContext):
        pass

    # Exit a parse tree produced by fhirpathParser#additiveExpression.
    def exitAdditiveExpression(self, ctx: fhirpathParser.AdditiveExpressionContext):
        pass

    # Enter a parse tree produced by fhirpathParser#multiplicativeExpression.
    def enterMultiplicativeExpression(
        self, ctx: fhirpathParser.MultiplicativeExpressionContext
    ):
        pass

    # Exit a parse tree produced by fhirpathParser#multiplicativeExpression.
    def exitMultiplicativeExpression(
        self, ctx: fhirpathParser.MultiplicativeExpressionContext
    ):
        pass

    # Enter a parse tree produced by fhirpathParser#unionExpression.
    def enterUnionExpression(self, ctx: fhirpathParser.UnionExpressionContext):
        pass

    # Exit a parse tree produced by fhirpathParser#unionExpression.
    def exitUnionExpression(self, ctx: fhirpathParser.UnionExpressionContext):
        pass

    # Enter a parse tree produced by fhirpathParser#orExpression.
    def enterOrExpression(self, ctx: fhirpathParser.OrExpressionContext):
        pass

    # Exit a parse tree produced by fhirpathParser#orExpression.
    def exitOrExpression(self, ctx: fhirpathParser.OrExpressionContext):
        pass

    # Enter a parse tree produced by fhirpathParser#andExpression.
    def enterAndExpression(self, ctx: fhirpathParser.AndExpressionContext):
        pass

    # Exit a parse tree produced by fhirpathParser#andExpression.
    def exitAndExpression(self, ctx: fhirpathParser.AndExpressionContext):
        pass

    # Enter a parse tree produced by fhirpathParser#membershipExpression.
    def enterMembershipExpression(
        self, ctx: fhirpathParser.MembershipExpressionContext
    ):
        pass

    # Exit a parse tree produced by fhirpathParser#membershipExpression.
    def exitMembershipExpression(self, ctx: fhirpathParser.MembershipExpressionContext):
        pass

    # Enter a parse tree produced by fhirpathParser#inequalityExpression.
    def enterInequalityExpression(
        self, ctx: fhirpathParser.InequalityExpressionContext
    ):
        pass

    # Exit a parse tree produced by fhirpathParser#inequalityExpression.
    def exitInequalityExpression(self, ctx: fhirpathParser.InequalityExpressionContext):
        pass

    # Enter a parse tree produced by fhirpathParser#invocationExpression.
    def enterInvocationExpression(
        self, ctx: fhirpathParser.InvocationExpressionContext
    ):
        pass

    # Exit a parse tree produced by fhirpathParser#invocationExpression.
    def exitInvocationExpression(self, ctx: fhirpathParser.InvocationExpressionContext):
        pass

    # Enter a parse tree produced by fhirpathParser#equalityExpression.
    def enterEqualityExpression(self, ctx: fhirpathParser.EqualityExpressionContext):
        pass

    # Exit a parse tree produced by fhirpathParser#equalityExpression.
    def exitEqualityExpression(self, ctx: fhirpathParser.EqualityExpressionContext):
        pass

    # Enter a parse tree produced by fhirpathParser#impliesExpression.
    def enterImpliesExpression(self, ctx: fhirpathParser.ImpliesExpressionContext):
        pass

    # Exit a parse tree produced by fhirpathParser#impliesExpression.
    def exitImpliesExpression(self, ctx: fhirpathParser.ImpliesExpressionContext):
        pass

    # Enter a parse tree produced by fhirpathParser#termExpression.
    def enterTermExpression(self, ctx: fhirpathParser.TermExpressionContext):
        pass

    # Exit a parse tree produced by fhirpathParser#termExpression.
    def exitTermExpression(self, ctx: fhirpathParser.TermExpressionContext):
        pass

    # Enter a parse tree produced by fhirpathParser#typeExpression.
    def enterTypeExpression(self, ctx: fhirpathParser.TypeExpressionContext):
        pass

    # Exit a parse tree produced by fhirpathParser#typeExpression.
    def exitTypeExpression(self, ctx: fhirpathParser.TypeExpressionContext):
        pass

    # Enter a parse tree produced by fhirpathParser#invocationTerm.
    def enterInvocationTerm(self, ctx: fhirpathParser.InvocationTermContext):
        pass

    # Exit a parse tree produced by fhirpathParser#invocationTerm.
    def exitInvocationTerm(self, ctx: fhirpathParser.InvocationTermContext):
        pass

    # Enter a parse tree produced by fhirpathParser#literalTerm.
    def enterLiteralTerm(self, ctx: fhirpathParser.LiteralTermContext):
        pass

    # Exit a parse tree produced by fhirpathParser#literalTerm.
    def exitLiteralTerm(self, ctx: fhirpathParser.LiteralTermContext):
        pass

    # Enter a parse tree produced by fhirpathParser#externalConstantTerm.
    def enterExternalConstantTerm(
        self, ctx: fhirpathParser.ExternalConstantTermContext
    ):
        pass

    # Exit a parse tree produced by fhirpathParser#externalConstantTerm.
    def exitExternalConstantTerm(self, ctx: fhirpathParser.ExternalConstantTermContext):
        pass

    # Enter a parse tree produced by fhirpathParser#parenthesizedTerm.
    def enterParenthesizedTerm(self, ctx: fhirpathParser.ParenthesizedTermContext):
        pass

    # Exit a parse tree produced by fhirpathParser#parenthesizedTerm.
    def exitParenthesizedTerm(self, ctx: fhirpathParser.ParenthesizedTermContext):
        pass

    # Enter a parse tree produced by fhirpathParser#nullLiteral.
    def enterNullLiteral(self, ctx: fhirpathParser.NullLiteralContext):
        pass

    # Exit a parse tree produced by fhirpathParser#nullLiteral.
    def exitNullLiteral(self, ctx: fhirpathParser.NullLiteralContext):
        pass

    # Enter a parse tree produced by fhirpathParser#booleanLiteral.
    def enterBooleanLiteral(self, ctx: fhirpathParser.BooleanLiteralContext):
        pass

    # Exit a parse tree produced by fhirpathParser#booleanLiteral.
    def exitBooleanLiteral(self, ctx: fhirpathParser.BooleanLiteralContext):
        pass

    # Enter a parse tree produced by fhirpathParser#stringLiteral.
    def enterStringLiteral(self, ctx: fhirpathParser.StringLiteralContext):
        pass

    # Exit a parse tree produced by fhirpathParser#stringLiteral.
    def exitStringLiteral(self, ctx: fhirpathParser.StringLiteralContext):
        pass

    # Enter a parse tree produced by fhirpathParser#numberLiteral.
    def enterNumberLiteral(self, ctx: fhirpathParser.NumberLiteralContext):
        pass

    # Exit a parse tree produced by fhirpathParser#numberLiteral.
    def exitNumberLiteral(self, ctx: fhirpathParser.NumberLiteralContext):
        pass

    # Enter a parse tree produced by fhirpathParser#longNumberLiteral.
    def enterLongNumberLiteral(self, ctx: fhirpathParser.LongNumberLiteralContext):
        pass

    # Exit a parse tree produced by fhirpathParser#longNumberLiteral.
    def exitLongNumberLiteral(self, ctx: fhirpathParser.LongNumberLiteralContext):
        pass

    # Enter a parse tree produced by fhirpathParser#dateLiteral.
    def enterDateLiteral(self, ctx: fhirpathParser.DateLiteralContext):
        pass

    # Exit a parse tree produced by fhirpathParser#dateLiteral.
    def exitDateLiteral(self, ctx: fhirpathParser.DateLiteralContext):
        pass

    # Enter a parse tree produced by fhirpathParser#dateTimeLiteral.
    def enterDateTimeLiteral(self, ctx: fhirpathParser.DateTimeLiteralContext):
        pass

    # Exit a parse tree produced by fhirpathParser#dateTimeLiteral.
    def exitDateTimeLiteral(self, ctx: fhirpathParser.DateTimeLiteralContext):
        pass

    # Enter a parse tree produced by fhirpathParser#timeLiteral.
    def enterTimeLiteral(self, ctx: fhirpathParser.TimeLiteralContext):
        pass

    # Exit a parse tree produced by fhirpathParser#timeLiteral.
    def exitTimeLiteral(self, ctx: fhirpathParser.TimeLiteralContext):
        pass

    # Enter a parse tree produced by fhirpathParser#quantityLiteral.
    def enterQuantityLiteral(self, ctx: fhirpathParser.QuantityLiteralContext):
        pass

    # Exit a parse tree produced by fhirpathParser#quantityLiteral.
    def exitQuantityLiteral(self, ctx: fhirpathParser.QuantityLiteralContext):
        pass

    # Enter a parse tree produced by fhirpathParser#externalConstant.
    def enterExternalConstant(self, ctx: fhirpathParser.ExternalConstantContext):
        pass

    # Exit a parse tree produced by fhirpathParser#externalConstant.
    def exitExternalConstant(self, ctx: fhirpathParser.ExternalConstantContext):
        pass

    # Enter a parse tree produced by fhirpathParser#memberInvocation.
    def enterMemberInvocation(self, ctx: fhirpathParser.MemberInvocationContext):
        pass

    # Exit a parse tree produced by fhirpathParser#memberInvocation.
    def exitMemberInvocation(self, ctx: fhirpathParser.MemberInvocationContext):
        pass

    # Enter a parse tree produced by fhirpathParser#functionInvocation.
    def enterFunctionInvocation(self, ctx: fhirpathParser.FunctionInvocationContext):
        pass

    # Exit a parse tree produced by fhirpathParser#functionInvocation.
    def exitFunctionInvocation(self, ctx: fhirpathParser.FunctionInvocationContext):
        pass

    # Enter a parse tree produced by fhirpathParser#thisInvocation.
    def enterThisInvocation(self, ctx: fhirpathParser.ThisInvocationContext):
        pass

    # Exit a parse tree produced by fhirpathParser#thisInvocation.
    def exitThisInvocation(self, ctx: fhirpathParser.ThisInvocationContext):
        pass

    # Enter a parse tree produced by fhirpathParser#indexInvocation.
    def enterIndexInvocation(self, ctx: fhirpathParser.IndexInvocationContext):
        pass

    # Exit a parse tree produced by fhirpathParser#indexInvocation.
    def exitIndexInvocation(self, ctx: fhirpathParser.IndexInvocationContext):
        pass

    # Enter a parse tree produced by fhirpathParser#totalInvocation.
    def enterTotalInvocation(self, ctx: fhirpathParser.TotalInvocationContext):
        pass

    # Exit a parse tree produced by fhirpathParser#totalInvocation.
    def exitTotalInvocation(self, ctx: fhirpathParser.TotalInvocationContext):
        pass

    # Enter a parse tree produced by fhirpathParser#function.
    def enterFunction(self, ctx: fhirpathParser.FunctionContext):
        pass

    # Exit a parse tree produced by fhirpathParser#function.
    def exitFunction(self, ctx: fhirpathParser.FunctionContext):
        pass

    # Enter a parse tree produced by fhirpathParser#paramList.
    def enterParamList(self, ctx: fhirpathParser.ParamListContext):
        pass

    # Exit a parse tree produced by fhirpathParser#paramList.
    def exitParamList(self, ctx: fhirpathParser.ParamListContext):
        pass

    # Enter a parse tree produced by fhirpathParser#quantity.
    def enterQuantity(self, ctx: fhirpathParser.QuantityContext):
        pass

    # Exit a parse tree produced by fhirpathParser#quantity.
    def exitQuantity(self, ctx: fhirpathParser.QuantityContext):
        pass

    # Enter a parse tree produced by fhirpathParser#unit.
    def enterUnit(self, ctx: fhirpathParser.UnitContext):
        pass

    # Exit a parse tree produced by fhirpathParser#unit.
    def exitUnit(self, ctx: fhirpathParser.UnitContext):
        pass

    # Enter a parse tree produced by fhirpathParser#dateTimePrecision.
    def enterDateTimePrecision(self, ctx: fhirpathParser.DateTimePrecisionContext):
        pass

    # Exit a parse tree produced by fhirpathParser#dateTimePrecision.
    def exitDateTimePrecision(self, ctx: fhirpathParser.DateTimePrecisionContext):
        pass

    # Enter a parse tree produced by fhirpathParser#pluralDateTimePrecision.
    def enterPluralDateTimePrecision(
        self, ctx: fhirpathParser.PluralDateTimePrecisionContext
    ):
        pass

    # Exit a parse tree produced by fhirpathParser#pluralDateTimePrecision.
    def exitPluralDateTimePrecision(
        self, ctx: fhirpathParser.PluralDateTimePrecisionContext
    ):
        pass

    # Enter a parse tree produced by fhirpathParser#typeSpecifier.
    def enterTypeSpecifier(self, ctx: fhirpathParser.TypeSpecifierContext):
        pass

    # Exit a parse tree produced by fhirpathParser#typeSpecifier.
    def exitTypeSpecifier(self, ctx: fhirpathParser.TypeSpecifierContext):
        pass

    # Enter a parse tree produced by fhirpathParser#qualifiedIdentifier.
    def enterQualifiedIdentifier(self, ctx: fhirpathParser.QualifiedIdentifierContext):
        pass

    # Exit a parse tree produced by fhirpathParser#qualifiedIdentifier.
    def exitQualifiedIdentifier(self, ctx: fhirpathParser.QualifiedIdentifierContext):
        pass

    # Enter a parse tree produced by fhirpathParser#identifier.
    def enterIdentifier(self, ctx: fhirpathParser.IdentifierContext):
        pass

    # Exit a parse tree produced by fhirpathParser#identifier.
    def exitIdentifier(self, ctx: fhirpathParser.IdentifierContext):
        pass


del fhirpathParser
