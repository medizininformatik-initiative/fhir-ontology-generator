import logging
from typing import Self

from urllib3 import Retry, HTTPResponse


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
        super().__init__(*args, **kwargs)

    def increment(self, *args, **kwargs) -> Self:
        response: HTTPResponse = kwargs.get("response")
        status_code = response.status if response is not None else "N/A"
        # attempt_nr = self.total
        backoff = self.get_backoff_time()
        delay_text = f" in {backoff:.2f}s" if backoff and backoff > 0 else ""
        logging.debug(
            f"Retrying due to {status_code} "
            f"(attempts remaining: {self.total if self.total is not None else '∞'}){delay_text}"
        )
        new_entry = super().increment(*args, **kwargs)

        if response is not None:
            new_entry.last_response = response
        return new_entry
