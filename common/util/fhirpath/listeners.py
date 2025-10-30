from antlr4 import Token, RecognitionException

from common.util.fhirpath import fhirpathParser
from common.util.log.antlr import LoggingErrorListener


class FHIRPathLoggingErrorListener(LoggingErrorListener[fhirpathParser]):
    def syntaxError(
        self,
        recognizer: fhirpathParser,
        offendingSymbol: Token,
        line,
        column,
        msg: str,
        e: RecognitionException,
    ):
        expr_str = str(recognizer.getTokenStream().tokenSource.inputStream)
        super().logger().warning(f"{msg}. Expression: \"{expr_str}\"")
