import urllib.request

from bs4 import BeautifulSoup

from model.UiDataModel import TerminologyEntry, TermCode


def url_get_contents(url):
    """ Opens a website and read its binary contents (HTTP Response Body) """
    req = urllib.request.Request(url=url)
    f = urllib.request.urlopen(req)
    return f.read()


def download_sonderverzeichnis_mortality():
    url = 'https://www.dimdi.de/static/de/klassifikationen/icd/icd-10-who/kode-suche/htmlamtl2019/zusatz-10' \
          '-sonderverzeichnisse-mortalitaet-morbiditaet.htm '
    xhtml = url_get_contents(url).decode('utf-8')

    bs = BeautifulSoup(xhtml, "lxml")

    tables = bs.find_all('table')

    mortality_adult = tables[0]
    mortality_child = tables[2]

    return extract_table_data(mortality_adult)


def extract_table_data(table):
    root_entries = []
    root_entry = None
    for row in table.find_all('tr'):
        if table_entries := row.find_all('td'):
            code, display, children = table_entries
            if code.strong:
                root_entry = TerminologyEntry([TermCode("icd10-who-mortalitaet", code.text,
                                                        display.text + " (currently not supported)")],
                                              "Concept", False, False)
                root_entries.append(root_entry)
            else:
                root_entry.children.append(
                    TerminologyEntry([TermCode("icd10-who-mortalitaet", code.text,
                                               display.text + " (currently not supported)")],
                                     "Concept", True, True))
    return root_entries


# if __name__ == '__main__':
#     module_category_entry = TerminologyEntry([TermCode("mii_abide", "Todesursache", "Todesursache")], False, False)
#     module_category_entry.children += download_sonderverzeichnis_mortality()
#     f = open("test" + ".json", 'w', encoding="utf-8")
#     f.write(module_category_entry.to_json())
#     f.close()
