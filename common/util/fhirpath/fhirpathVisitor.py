# Generated from common/resources/fhirpath/fhirpath.g4 by ANTLR 4.9.3
from typing import TypeVar, Generic

from antlr4 import *

if __name__ is not None and "." in __name__:
    from .fhirpathParser import fhirpathParser
else:
    from fhirpathParser import fhirpathParser


T = TypeVar("T", covariant=True)


# This class defines a complete generic visitor for a parse tree produced by fhirpathParser.

class fhirpathVisitor(ParseTreeVisitor, Generic[T]):

    # Visit a parse tree produced by fhirpathParser#entireExpression.
    def visitEntireExpression(self, ctx: fhirpathParser.EntireExpressionContext) -> T:
        return self.visitChildren(ctx)

    # Visit a parse tree produced by fhirpathParser#indexerExpression.
    def visitIndexerExpression(self, ctx: fhirpathParser.IndexerExpressionContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by fhirpathParser#polarityExpression.
    def visitPolarityExpression(self, ctx: fhirpathParser.PolarityExpressionContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by fhirpathParser#additiveExpression.
    def visitAdditiveExpression(self, ctx: fhirpathParser.AdditiveExpressionContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by fhirpathParser#multiplicativeExpression.
    def visitMultiplicativeExpression(
        self, ctx: fhirpathParser.MultiplicativeExpressionContext
    ):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by fhirpathParser#unionExpression.
    def visitUnionExpression(self, ctx: fhirpathParser.UnionExpressionContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by fhirpathParser#orExpression.
    def visitOrExpression(self, ctx: fhirpathParser.OrExpressionContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by fhirpathParser#andExpression.
    def visitAndExpression(self, ctx: fhirpathParser.AndExpressionContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by fhirpathParser#membershipExpression.
    def visitMembershipExpression(
        self, ctx: fhirpathParser.MembershipExpressionContext
    ):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by fhirpathParser#inequalityExpression.
    def visitInequalityExpression(
        self, ctx: fhirpathParser.InequalityExpressionContext
    ):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by fhirpathParser#invocationExpression.
    def visitInvocationExpression(
        self, ctx: fhirpathParser.InvocationExpressionContext
    ):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by fhirpathParser#equalityExpression.
    def visitEqualityExpression(self, ctx: fhirpathParser.EqualityExpressionContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by fhirpathParser#impliesExpression.
    def visitImpliesExpression(self, ctx: fhirpathParser.ImpliesExpressionContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by fhirpathParser#termExpression.
    def visitTermExpression(self, ctx: fhirpathParser.TermExpressionContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by fhirpathParser#typeExpression.
    def visitTypeExpression(self, ctx: fhirpathParser.TypeExpressionContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by fhirpathParser#invocationTerm.
    def visitInvocationTerm(self, ctx: fhirpathParser.InvocationTermContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by fhirpathParser#literalTerm.
    def visitLiteralTerm(self, ctx: fhirpathParser.LiteralTermContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by fhirpathParser#externalConstantTerm.
    def visitExternalConstantTerm(
        self, ctx: fhirpathParser.ExternalConstantTermContext
    ):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by fhirpathParser#parenthesizedTerm.
    def visitParenthesizedTerm(self, ctx: fhirpathParser.ParenthesizedTermContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by fhirpathParser#nullLiteral.
    def visitNullLiteral(self, ctx: fhirpathParser.NullLiteralContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by fhirpathParser#booleanLiteral.
    def visitBooleanLiteral(self, ctx: fhirpathParser.BooleanLiteralContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by fhirpathParser#stringLiteral.
    def visitStringLiteral(self, ctx: fhirpathParser.StringLiteralContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by fhirpathParser#numberLiteral.
    def visitNumberLiteral(self, ctx: fhirpathParser.NumberLiteralContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by fhirpathParser#longNumberLiteral.
    def visitLongNumberLiteral(self, ctx: fhirpathParser.LongNumberLiteralContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by fhirpathParser#dateLiteral.
    def visitDateLiteral(self, ctx: fhirpathParser.DateLiteralContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by fhirpathParser#dateTimeLiteral.
    def visitDateTimeLiteral(self, ctx: fhirpathParser.DateTimeLiteralContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by fhirpathParser#timeLiteral.
    def visitTimeLiteral(self, ctx: fhirpathParser.TimeLiteralContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by fhirpathParser#quantityLiteral.
    def visitQuantityLiteral(self, ctx: fhirpathParser.QuantityLiteralContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by fhirpathParser#externalConstant.
    def visitExternalConstant(self, ctx: fhirpathParser.ExternalConstantContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by fhirpathParser#memberInvocation.
    def visitMemberInvocation(self, ctx: fhirpathParser.MemberInvocationContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by fhirpathParser#functionInvocation.
    def visitFunctionInvocation(self, ctx: fhirpathParser.FunctionInvocationContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by fhirpathParser#thisInvocation.
    def visitThisInvocation(self, ctx: fhirpathParser.ThisInvocationContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by fhirpathParser#indexInvocation.
    def visitIndexInvocation(self, ctx: fhirpathParser.IndexInvocationContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by fhirpathParser#totalInvocation.
    def visitTotalInvocation(self, ctx: fhirpathParser.TotalInvocationContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by fhirpathParser#function.
    def visitFunction(self, ctx: fhirpathParser.FunctionContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by fhirpathParser#paramList.
    def visitParamList(self, ctx: fhirpathParser.ParamListContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by fhirpathParser#quantity.
    def visitQuantity(self, ctx: fhirpathParser.QuantityContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by fhirpathParser#unit.
    def visitUnit(self, ctx: fhirpathParser.UnitContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by fhirpathParser#dateTimePrecision.
    def visitDateTimePrecision(self, ctx: fhirpathParser.DateTimePrecisionContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by fhirpathParser#pluralDateTimePrecision.
    def visitPluralDateTimePrecision(
        self, ctx: fhirpathParser.PluralDateTimePrecisionContext
    ):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by fhirpathParser#typeSpecifier.
    def visitTypeSpecifier(self, ctx: fhirpathParser.TypeSpecifierContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by fhirpathParser#qualifiedIdentifier.
    def visitQualifiedIdentifier(self, ctx: fhirpathParser.QualifiedIdentifierContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by fhirpathParser#identifier.
    def visitIdentifier(self, ctx: fhirpathParser.IdentifierContext):
        return self.visitChildren(ctx)

    def visit(self, tree):
        return tree.accept(self)


del fhirpathParser
