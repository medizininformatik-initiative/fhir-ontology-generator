from MapperDataModel import generate_map
from UiDataModel import TerminologyEntry
from geccoToUI import create_terminology_definition_for, get_categories, IGNORE_CATEGORIES, MAIN_CATEGORIES
from termEntryToExcel import to_excel
from queryTermCodeMapper import to_term_code_node


if __name__ == '__main__':
    others = TerminologyEntry(None, "CategoryEntry", selectable=False)
    others.display = "Andere"
    category_entries = create_terminology_definition_for(get_categories())
    map_entries = generate_map(category_entries)
    for entry in map_entries:
        print(entry.to_json())
    term_code_tree = to_term_code_node(category_entries)
    term_code_file = open("result/" + "TermCodeTree.json", 'w')
    term_code_file.write(term_code_tree.to_json())
    to_excel(category_entries)
    for category in category_entries:
        if category in IGNORE_CATEGORIES:
            continue
        if category.display in MAIN_CATEGORIES:
            f = open("result/" + category.display.replace("/ ", "") + ".json", 'w')
            f.write(category.to_json())
        else:
            others.children.append(category)
    f = open("result/" + others.display + ".json", 'w')
    f.write(others.to_json())
