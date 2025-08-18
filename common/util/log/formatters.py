import logging
from enum import Enum


class Colors(Enum):
    BOLD_RED = "\x1b[31;1m"
    RED = "\x1b[31;20m"
    YELLOW = "\x1b[33;20m"
    GREEN = "\x1b[32;20m"
    BLUE = "\x1b[36;20m"
    DEFAULT = "\x1b[38;20m"
    RESET = "\x1b[0m"


class ColorFormatter(logging.Formatter):
    __color_map = {
        logging.DEBUG: Colors.GREEN,
        logging.INFO: Colors.BLUE,
        logging.WARN: Colors.YELLOW,
        logging.WARNING: Colors.YELLOW,
        logging.ERROR: Colors.RED,
        logging.CRITICAL: Colors.BOLD_RED,
    }

    @staticmethod
    def __get_color(level: int) -> Colors:
        match level:
            case logging.DEBUG:
                return Colors.GREEN
            case logging.INFO:
                return Colors.BLUE
            case logging.WARN:
                return Colors.YELLOW
            case logging.WARNING:
                return Colors.YELLOW
            case logging.ERROR:
                return Colors.RED
            case logging.CRITICAL:
                return Colors.BOLD_RED
            case _:
                return Colors.DEFAULT

    def format(self, record: logging.LogRecord):
        fmt = f"{self.__get_color(record.levelno).value}{self._fmt}{Colors.RESET.value}"
        return logging.Formatter(fmt).format(record)