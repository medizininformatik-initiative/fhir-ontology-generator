import urllib.request

from bs4 import BeautifulSoup

from model.UiDataModel import TermEntry, TermCode


def url_get_contents(url: str):
    """
    Opens a website and read its binary contents (HTTP Response Body)
    :param url: The URL of the website
    """
    req = urllib.request.Request(url=url)
    f = urllib.request.urlopen(req)
    return f.read()


def download_sonderverzeichnis_mortality():
    """
    Downloads the ICD-10 mortality codes from the WHO website and returns them in the hierarchical structure of roots of
    term entries.
    :return: roots of term entries representing the mortality codes hierarchy
    """
    url = 'https://www.dimdi.de/static/de/klassifikationen/icd/icd-10-who/kode-suche/htmlamtl2019/zusatz-10' \
          '-sonderverzeichnisse-mortalitaet-morbiditaet.htm '
    xhtml = url_get_contents(url).decode('utf-8')

    bs = BeautifulSoup(xhtml, "lxml")

    tables = bs.find_all('table')

    mortality_adult = tables[0]
    mortality_child = tables[2]

    return extract_table_data(mortality_adult)


def extract_table_data(table):
    """
    Extracts the mortality codes from the table and returns them in the hierarchical structure of roots of term entries.
    :param table: csv table of mortality codes
    :return: roots of term entries representing the mortality codes hierarchy
    """
    root_entries = []
    root_entry = None
    for row in table.find_all('tr'):
        if table_entries := row.find_all('td'):
            code, display, children = table_entries
            if code.strong:
                root_entry = TermEntry([TermCode("icd10-who-mortalitaet", code.text,
                                                 display.text + " (currently not supported)")],
                                       "Concept", False, False, context=TermCode("mii.fdpg",
                                                                                 "icd10-who-mortalitaet",
                                                                                 "ICD-10 WHO Mortilität"))
                root_entries.append(root_entry)
            else:
                root_entry.children.append(
                    TermEntry([TermCode("icd10-who-mortalitaet", code.text,
                                        display.text + " (currently not supported)")],
                              "Concept", True, True), context=TermCode("mii.fdpg", "icd10-who-mortalitaet",
                                                                                   "ICD-10 WHO Mortilität"))
    return root_entries

# if __name__ == '__main__':
#     module_category_entry = TerminologyEntry([TermCode("mii_abide", "Todesursache", "Todesursache")], False, False)
#     module_category_entry.children += download_sonderverzeichnis_mortality()
#     f = open("test" + ".json", 'w', encoding="utf-8")
#     f.write(module_category_entry.to_json())
#     f.close()
