import logging.config

from typing import Any, Optional

from common.constants.project import PROJECT_ROOT

GLOBAL_LOGGING_CONFIG_FILE = PROJECT_ROOT / "logging.toml"
logging.config.fileConfig(GLOBAL_LOGGING_CONFIG_FILE)
logging.info(f"Logging using configuration options defined @ {GLOBAL_LOGGING_CONFIG_FILE}",
             extra={'className': ""})


def get_logger(name: Optional[str] = None) -> logging.LoggerAdapter:
    """
    Returns a logger while also initializing project log if not done already
    :param name: Name of the logger
    :return: `log.LoggerAdapter` instance to log with
    """
    return logging.LoggerAdapter(logging.getLogger(name), extra={'className': ""})


def get_class_logger(cls: Any | str) -> logging.LoggerAdapter:
    """
    Returns a class logger while also initializing project log if not done already
    :param cls: Class object or name to create a logger for
    :return: `log.LoggerAdapter` instance to log with
    """
    class_name = cls if isinstance(cls, str) else cls.__name__
    return logging.LoggerAdapter(logging.getLogger(class_name), extra={'className': f".{class_name}"})