import csv

from model.UiDataModel import TermCode, TermEntry


def as_text(value):
    if value is None:
        return ""
    if "\n" in value:
        values = value.split()
        return max(values, key=len)
    return str(value)


def get_termcode_row(terminology_code: TermCode):
    system = terminology_code.system
    code = terminology_code.code
    version = ""
    display = terminology_code.display
    return [system, code, version, display]


def get_terminology_entry_row(terminology_entry: TermEntry):
    result = ["UNDEFINED", "UNDEFINED", "UNDEFINED", "UNDEFINED"]
    if terminology_entry.termCode:
        result = get_termcode_row(terminology_entry.termCode)
    result.append(terminology_entry.display)
    return result


def to_csv(category_list):
    def add_terminology_entry(terminology_entry: TermEntry):
        sheet.writerow(get_terminology_entry_row(terminology_entry))
        for child in terminology_entry.children:
            add_terminology_entry(child)
        if terminology_entry.uiProfile and terminology_entry.uiProfile.valueDefinition:
            for concept in terminology_entry.uiProfile.valueDefinition.referencedValueSet:
                sheet.writerow(get_termcode_row(concept))
        if terminology_entry.uiProfile and terminology_entry.uiProfile.attributeDefinitions:
            for definition in terminology_entry.uiProfile.attributeDefinitions:
                for concept in definition.referencedValueSet:
                    sheet.writerow(get_termcode_row(concept))

    for category in category_list:
        with open("csv/" + category.display.replace("/ ", "") + '.csv', 'w', newline='', encoding="utf-8") as f:
            sheet = csv.writer(f)
            for entry in category.children:
                add_terminology_entry(entry)
