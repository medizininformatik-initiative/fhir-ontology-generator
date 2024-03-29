import json
import os

from helper import get_term_selectable_codes_from_ui_profile
from model.UiDataModel import TermCode


def load_keys():
    with open("mapping/codex-term-code-mapping.json") as json_data:
        mapping = json.load(json_data)
        return {TermCode(**(entry.get("key"))) for entry in mapping}


if __name__ == "__main__":
    keys = load_keys()

    for ui_profile_name in [f.name for f in os.scandir("ui-profiles/")]:
        with open("ui-profiles/" + ui_profile_name, 'r', encoding="utf-8") as ui_profile_json:
            ui_profile = json.load(ui_profile_json)
            entries_requiring_map_entry = get_term_selectable_codes_from_ui_profile(ui_profile)
            print(ui_profile_name)
            print(entries_requiring_map_entry - keys)
