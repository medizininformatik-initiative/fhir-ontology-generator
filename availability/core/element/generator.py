from logging import Logger

from common.util.log.decorators import inject_logger


@inject_logger
class ProfileMeasureGenerator:
    _logger: Logger
