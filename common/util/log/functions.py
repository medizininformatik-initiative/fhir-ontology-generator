import logging.config
import os
import sys

from typing import Any, Optional

from common.constants.project import PROJECT_ROOT
from common.util.log import GLOBAL_LOGGING_CONFIG_FILE, LOGGING_DIR


# Process logging.yaml file and set logging config after
LOGGING_DIR.mkdir(parents=True, exist_ok=True)

with open(GLOBAL_LOGGING_CONFIG_FILE, mode="rb") as config_f:
    import yaml

    config = yaml.load(config_f, Loader=yaml.Loader)

for name, handler in config["handlers"].items():
    if handler.get("class") == "logging.FileHandler":
        file_name = handler["filename"]
        script_name = os.path.splitext(os.path.basename(sys.argv[0]))[0]
        handler["filename"] = str(
            PROJECT_ROOT.joinpath(
                file_name.format(log_file_name=script_name + ".log")
            ).resolve()
        )
logging.config.dictConfig(config)

logging.info(
    f"Logging using configuration options defined @ {GLOBAL_LOGGING_CONFIG_FILE}",
    extra={"className": ""},
)


def get_logger(name: Optional[str] = None) -> logging.LoggerAdapter:
    """
    Returns a logger while also initializing project log if not done already
    :param name: Name of the logger
    :return: `logging.LoggerAdapter` instance to log with
    """
    return logging.LoggerAdapter(logging.getLogger(name))


def get_class_logger(cls: Any | str) -> logging.LoggerAdapter:
    """
    Returns a class logger while also initializing project log if not done already
    :param cls: Class object or name to create a logger for
    :return: `log.LoggerAdapter` instance to log with
    """
    class_name = cls if isinstance(cls, str) else cls.__name__
    return logging.LoggerAdapter(
        logging.getLogger(class_name), extra={"className": f".{class_name}"}
    )
