import json
from json import JSONDecodeError
from pathlib import Path
from typing import Any, Optional


def load_json(
    json_file: Path, encoding: str | list[str] = None, fail: bool = False
) -> Optional[Any]:
    """
    Attempts to parse the content of a JSON file using the provided encodings, returning the value obtained during the
    first successful attempt or `None` if all fail

    :param json_file: Path to JSON file to parse
    :param encoding: Encoding or list of encodings to try. Defaults to `["utf-8", "utf-8-sig"]`
    :param fail: If `True` and exception will be raised if all attempts failed
    :return: Parsed JSON content or `None` if all attempts fail
    """
    if encoding is None:
        encoding = ["utf-8", "utf-8-sig"]
    encodings = [encoding] if isinstance(encoding, str) else encoding
    for enc in encodings:
        try:
            with open(json_file, mode="r", encoding=enc) as f:
                return json.load(f)
        except JSONDecodeError:
            pass
    if fail:
        raise ValueError(
            f"Failed to parse JSON file content @ {json_file} for encodings {encodings}"
        )
    return None