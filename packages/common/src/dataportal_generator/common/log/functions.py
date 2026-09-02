import functools
import logging.config
import os
import sys
from pathlib import Path

from typing import Any, Optional

from dataportal_generator.common.log import DEFAULT_LOGGING_CONFIG_FILE


@functools.cache
def configure_logging(project_dir: Path):
    # Process logging.yaml file and set logging config after
    logging_config_file = project_dir / "logging.yaml"
    if not logging_config_file.exists():
        logging_config_file = DEFAULT_LOGGING_CONFIG_FILE

    with open(logging_config_file, mode="rb") as config_f:
        import yaml

        config = yaml.load(config_f, Loader=yaml.Loader)

    logging_dir = project_dir / "logs"
    logging_dir.mkdir(parents=True, exist_ok=True)

    for name, handler in config["handlers"].items():
        if handler.get("class") == "logging.FileHandler":
            file_name = handler["filename"]
            script_name = os.path.splitext(os.path.basename(sys.argv[0]))[0]
            handler["filename"] = str(
                logging_dir.joinpath(
                    file_name.format(log_file_name=script_name + ".log")
                ).resolve()
            )
    logging.config.dictConfig(config)

    logging.info(
        f"Logging using configuration options defined @ {repr(logging_config_file)}",
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