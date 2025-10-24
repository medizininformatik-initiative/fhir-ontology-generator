from urllib3 import Retry, HTTPResponse
from common.util.log.functions import get_logger


class CustomRetry(Retry):
    def __init__(self, *args, **kwargs):
        """
        Retry wrapper with custom logging
        :param total: nr of total retries. None for infinite
        :param backoff_factor: Time to wait between retries
                {backoff factor} * (2 ** ({number of total retries} - 1))
        :param status_forcelist: list of status codes to retry on
        :param allowed_methods: list of allowed methods. ["GET", "POST"]
        """
        logger = get_logger("Retry")
        logger.info("Init CustomRetry")
        super().__init__(*args, **kwargs)

    def increment(self, *args, **kwargs)->Retry:
        logger = get_logger("Retry")
        response: HTTPResponse = kwargs.get('response')
        status_code = response.status if response is not None else "N/A"
        attempt_nr = self.total - self.remaining if self.total is not None else 0
        logger.info(f"Retrying {kwargs.get('url', '')} due to {status_code} (attempt {attempt_nr} of {self.total if self.total is not None else "∞"})")
        return super().increment(*args, **kwargs)


