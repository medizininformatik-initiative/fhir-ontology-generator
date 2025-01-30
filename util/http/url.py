from typing import Mapping, Optional


def format_query_params(query_params: Optional[Mapping[str, any]] = None) -> Optional[Mapping[str, any]]:
    if query_params is None:
        return None
    return {k.replace('_', '-'): v for k, v in query_params.items()}


def insert_path_params(url: str, **path_params) -> str:
    split = url.split("?", 1)
    return split[0].format(path_params) + (split[1] if len(split) > 1 else "")


def merge_urls(url_a: str, url_b: str) -> str:
    if len(url_a) == 0 and len(url_b) == 0:
        return ""
    match (url_a.endswith("/") + url_b.startswith("/")):
        case 0:
            return url_a + "/" + url_b
        case 1:
            return url_a + url_b
        case 2:
            return url_a + url_b.lstrip("/")