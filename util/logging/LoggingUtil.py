import logging

default_msg_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


def init_logger(name: str, level: int) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level)
    return logger


def log_to_stream(name: str, stream, level: int, msg_format: str = default_msg_format):
    stream_handler = logging.StreamHandler(stream)
    stream_handler.setLevel(level)
    stream_handler.setFormatter(logging.Formatter(msg_format))
    logging.getLogger(name).addHandler(stream_handler)


def log_to_stdout(name: str, level: int, msg_format: str = None):
    import sys
    log_to_stream(name, sys.stdout, level, msg_format)
