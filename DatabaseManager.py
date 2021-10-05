import psycopg2
import psycopg2.extras


class DatabaseManager:
    def __init__(self):
        self.db_connection = None
        self.cursor = None

    def insert_term_codes(self, term_codes):
        values = [(term_code.system, term_code.code, term_code.version, term_code.display) for term_code in term_codes]
        psycopg2.extras.execute_batch(self.cursor, "INSERT INTO TERMCODE VALUES (%s, %s, %s, %s)", values)

    def drop_table(self, table_name):
        drop_table_command = "DROP TABLE %s;" % table_name
        self.cursor.execute(drop_table_command)

    def init_db(self):
        create_table = (
            """
                CREATE TABLE IF NOT EXISTS TERMCODE(
                    system VARCHAR(255) NOT NULL,
                    code VARCHAR(255) NOT NULL,
                    version VARCHAR(255),
                    PRIMARY KEY (system, code, version),
                    display VARCHAR(255) NOT NULL
                );
            """,
            """
                CREATE TABLE IF NOT EXISTS UI-MAPPING(
                    FOREIGN KEY(system, code, version) REFERENCES TERMCODE(system, code, version),
                    ui-category VARCHAR(255) NOT NULL
            """,
            """
                CREATE TABLE IF NOT EXISTS UI-JSON-MAPPING(
                    PRIMARY KEY (ui-category) REFERENCES UI-MAPPING(ui-category),
                    UI-JSON json NOT NULL
            """)

        self.db_connection = None
        try:
            self.db_connection = psycopg2.connect(database='codex_mapping', user='codex-mapping', host='localhost',
                                                  password=
                                                  'codex-password')
            self.cursor = self.db_connection.cursor()
            self.cursor.execute(create_table)
            self.cursor.close()
            self.db_connection.commit()
        except Exception as e:
            print(e)
        finally:
            if self.db_connection is not None:
                self.db_connection.close()
