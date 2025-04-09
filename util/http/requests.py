import requests

from util.log.functions import get_logger

logger = get_logger(__file__)


def is_responsive(url: str, expect: int = 200) -> bool:
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == expect:
            return True
        logger.info(f"Got unexpected status code: {response.status_code} from url: {url}")
    except requests.RequestException:
        pass
    return False