import psycopg2.extras
import psycopg2

from model.UIProfileModel import generate_default_ui_profile
from model.UiDataModel import TermCode

create_term_code_table = """
                CREATE TABLE IF NOT EXISTS TERMCODE(
                system VARCHAR(255) NOT NULL,
                code VARCHAR(255) NOT NULL,
                version VARCHAR(255),
                PRIMARY KEY (system, code, version),
                display VARCHAR(255) NOT NULL
            );
"""

create_ui_profile_table = """
    CREATE TABLE IF NOT EXISTS UI_PROFILE_TABLE(
    system VARCHAR(255) NOT NULL,
    code VARCHAR(255) NOT NULL,
    version VARCHAR(255),
    PRIMARY KEY (system, code, version),
    UI_Profile JSON NOT NULL
    );
"""


class DataBaseWriter:
    def __init__(self):
        self.db_connection = None
        try:
            self.db_connection = psycopg2.connect(database='codex_ui', user='codex-postgres', host='localhost',
                                                  password=
                                                  'codex-password')
        except Exception as e:
            print(e)
        if self.db_connection:
            self.cursor = self.db_connection.cursor()
            self.drop_tables('TERMCODE')
            self.drop_tables('UI_PROFILE_TABLE')
            self.cursor.execute(create_term_code_table)
            self.cursor.execute(create_ui_profile_table)
            self.db_connection.commit()

    def __del__(self):
        if self.db_connection is not None:
            self.cursor.close()
            self.db_connection.close()

    def insert_term_codes(self, term_codes):
        values = [(term_code.system, term_code.code, term_code.version if term_code.version else "", term_code.display)
                  for term_code in term_codes]
        psycopg2.extras.execute_batch(self.cursor, "INSERT INTO TERMCODE VALUES (%s, %s, %s, %s)", values)
        self.db_connection.commit()

    def insert_ui_profile(self, term_code, ui_profile):
        values = (term_code.system, term_code.code, term_code.version if term_code.version else "", ui_profile)
        self.cursor.execute("INSERT INTO UI_PROFILE_TABLE VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING", values)
        self.db_connection.commit()

    # Deletes old table
    def drop_tables(self, table_name):
        drop_table_command = "DROP TABLE %s;" % table_name
        self.cursor.execute(drop_table_command)

    def get_ui_profile(self, term_code):
        self.cursor.execute("SELECT UI_PROFILE from UI_PROFILE_TABLE "
                            "where (system = %s) and (code = %s) and (version = %s)"
                            , (term_code.system, term_code.code, term_code.version if term_code.version else ""))
        result = self.cursor.fetchall()
        return result[0][0]

    def add_ui_profiles_to_db(self, entries):
        for entry in entries:
            if entry.selectable:
                if entry.uiProfile:
                    for term_code in entry.termCodes:
                        self.insert_ui_profile(term_code, entry.uiProfile.to_json())
                else:
                    print(entry.termCode.display)
            self.add_ui_profiles_to_db(entry.children)


if __name__ == "__main__":
    dbw = DataBaseWriter()

    tc = TermCode("http://fhir.de/CodeSystem/bfarm/icd-10-gm", "C90.0", "Vadadustat", "2021")
    # test_profile = generate_default_ui_profile("test", None)
    # dbw.insert_term_codes([tc])
    # dbw.insert_ui_profile(tc, test_profile.to_json())
    print(dbw.get_ui_profile(tc))
