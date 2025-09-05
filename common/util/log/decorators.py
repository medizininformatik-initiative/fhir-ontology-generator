from common.util.log.functions import get_class_logger


def inject_logger(cls):
    cls._logger = get_class_logger(cls.__qualname__)
    return cls