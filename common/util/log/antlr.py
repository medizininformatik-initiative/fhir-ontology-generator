from logging import Logger
from typing import Generic

from antlr4.Parser import Parser
from antlr4.Token import Token
from antlr4.error.ErrorListener import ErrorListener
from antlr4.error.Errors import RecognitionException
from typing_extensions import TypeVar

from common.util.log.functions import get_class_logger


T = TypeVar("T", bound=Parser)


class LoggingErrorListener(ErrorListener, Generic[T]):
    __logger: Logger = get_class_logger("LoggingErrorListener")

    def logger(self) -> Logger:
        return self.__logger

    def syntaxError(
        self,
        recognizer: T,
        offendingSymbol: Token,
        line,
        column,
        msg: str,
        e: RecognitionException,
    ):
        recognizer.getTokenStream()
        self.__logger.warning(msg)
