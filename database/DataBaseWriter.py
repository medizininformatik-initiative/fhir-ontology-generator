from time import sleep
from typing import List, Tuple, Dict

import psycopg2.extras
import psycopg2

from model.UIProfileModel import UIProfile
from model.UiDataModel import TermCode, TermEntry

"""
creates the table TermCode:
system | code | version | display 
With the combination of system, code and version as primary key
"""
create_term_code_table = """
    CREATE TABLE IF NOT EXISTS TERMCODE(
    id SERIAL PRIMARY KEY,
    system TEXT NOT NULL,
    code TEXT NOT NULL,
    version TEXT,
    UNIQUE (system, code, version),
    display VARCHAR(255) NOT NULL
    );
"""

"""
creates the table UI_PROFILE:
ic | UI_Profile 
With the combination of system, code and version as primary key
"""
create_ui_profile_table = """
    CREATE TABLE IF NOT EXISTS UI_PROFILE(
    id TEXT PRIMARY KEY,
    UI_Profile JSON NOT NULL
    );
"""

"""
creates the table CONTEXT:
system | code | display | version
With the combination of system and code as primary key
"""
create_context_table = """
    CREATE TABLE IF NOT EXISTS CONTEXT(
    id SERIAL PRIMARY KEY,
    system TEXT NOT NULL,
    code TEXT NOT NULL,
    version TEXT,
    UNIQUE (system, code, version),
    display TEXT NOT NULL
    );
"""

"""
creates the table CONTEXTUALIZED_CONCEPT_TO_UI_PROFILE:
with the primary key from the table CONTEXT, the table TERMCODE and the table UI_PROFILE_TABLE
"""
create_contextualized_concept_to_ui_profile_table = """
    CREATE TABLE IF NOT EXISTS CONTEXTUALIZED_CONCEPT_TO_UI_PROFILE(
    context_id INTEGER NOT NULL,
    termcode_id INTEGER NOT NULL,
    profile_id TEXT NOT NULL,
    CONSTRAINT CONTEXT_ID_FK FOREIGN KEY (context_id)  
        REFERENCES CONTEXT (id) ON DELETE CASCADE,
    CONSTRAINT CONCEPT_ID_FK FOREIGN KEY (termcode_id) 
        REFERENCES TERMCODE(id) ON DELETE CASCADE,
    CONSTRAINT PROFILE_ID_FK FOREIGN KEY (profile_id)
        REFERENCES UI_PROFILE(id) ON DELETE CASCADE
    );
"""

"""
creates the table MAPPING:
mapping_name | mapping_type | mapping_json
With the combination of mapping_name and mapping_type as primary key
"""
create_mapping_table = """
    CREATE TABLE IF NOT EXISTS MAPPING(
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    UNIQUE (name, type),
    content JSON NOT NULL
    );
"""

"""
creates the table CONTEXTUALIZED_CONCEPT_TO_MAPPING:
with the primary key from the table CONTEXT, the table TERMCODE and the table MAPPING
"""
create_contextualized_concept_to_mapping_table = """
    CREATE TABLE IF NOT EXISTS CONTEXTUALIZED_CONCEPT_TO_MAPPING(
    context_id INTEGER NOT NULL,
    termcode_id INTEGER NOT NULL,
    mapping_id INTEGER NOT NULL,
    CONSTRAINT CONTEXT_ID_FK FOREIGN KEY (context_id)
        REFERENCES CONTEXT (id) ON DELETE CASCADE,
    CONSTRAINT CONCEPT_ID_FK FOREIGN KEY (termcode_id)
        REFERENCES TERMCODE (id) ON DELETE CASCADE,
    CONSTRAINT MAPPING_ID_FK FOREIGN KEY (mapping_id)
        REFERENCES MAPPING (id) ON DELETE CASCADE
    );
"""

"""
creates the table VALUE_SET:
"""
create_value_set_table = """
    CREATE TABLE IF NOT EXISTS VALUE_SET(
    canonical_url TEXT NOT NULL,
    system TEXT NOT NULL,
    code TEXT NOT NULL,
    version TEXT,
    PRIMARY KEY (canonical_url, system, code, version)
    );
"""

add_value_set_table_canonical_url_index = """
    CREATE INDEX IF NOT EXISTS canonical_url_index ON VALUE_SET(canonical_url);
"""

add_join_index_for_contextualized_mapping = """
    CREATE INDEX idx_mapping_name_mapping ON MAPPING (name);
    CREATE INDEX idx_mapping_name_contextualized ON CONTEXTUALIZED_CONCEPT_TO_MAPPING (mapping_id);
"""


class DataBaseWriter:
    """
    DataBaseWriter is a class that handles the connection to the database and the insertion of data into the database
    for the feasibility tool ontology.
    """

    def __init__(self):
        self.db_connection = None
        for _ in range(30):  # retry for 30 times
            try:
                self.db_connection = psycopg2.connect(
                    database='codex_ui',
                    user='codex-postgres',
                    host='localhost',
                    password='codex-password'
                )
                # if connection is established, break the loop
                break
            except psycopg2.OperationalError:
                # wait for 1 second before trying again
                sleep(1)
        else:
            # raise error if connection could not be established after 30 attempts
            raise Exception("Cannot connect to database")
        if self.db_connection:
            self.cursor = self.db_connection.cursor()
            self.cursor.execute(create_term_code_table)
            self.cursor.execute(create_ui_profile_table)
            self.cursor.execute(create_context_table)
            self.cursor.execute(create_contextualized_concept_to_ui_profile_table)
            self.cursor.execute(create_mapping_table)
            self.cursor.execute(create_contextualized_concept_to_mapping_table)
            self.cursor.execute(add_join_index_for_contextualized_mapping)
            self.cursor.execute(create_value_set_table)
            self.cursor.execute(add_value_set_table_canonical_url_index)
            self.db_connection.commit()

    def __del__(self):
        """
        Closes the connection to the database
        """
        if self.db_connection is not None:
            self.cursor.close()
            self.db_connection.close()

    def insert_term_codes(self, term_codes: List[TermCode]):
        """
        Inserts the term codes into the database
        :param term_codes: the term codes to be inserted
        """
        values = set(
            (term_code.system, term_code.code, term_code.version if term_code.version else "", term_code.display)
            for term_code in term_codes)
        psycopg2.extras.execute_batch(self.cursor,
                                      "INSERT INTO TERMCODE (system, code, version, display) VALUES (%s, %s, %s, %s)",
                                      values)
        self.db_connection.commit()

    def insert_context_codes(self, context_codes: List[TermCode]):
        """
        Inserts the context codes into the database
        :param context_codes: the context codes to be inserted
        """
        values = set((context_code.system, context_code.code, context_code.version if context_code.version else "",
                      context_code.display)
                     for context_code in context_codes)
        psycopg2.extras.execute_batch(self.cursor,
                                      "INSERT INTO CONTEXT (system, code, version, display) VALUES (%s, %s, %s, %s)",
                                      values)
        self.db_connection.commit()

    def context_exists(self, context: TermCode):
        """
        Checks if the given context exists in the CONTEXT table
        :param context: the context to be checked
        :return: True if exists, False otherwise
        """
        self.cursor.execute("SELECT 1 FROM CONTEXT WHERE system = %s AND code = %s AND version = %s",
                            (context.system, context.code, context.version if context.version else ''))
        return bool(self.cursor.fetchone())

    def termcode_exists(self, term_code: TermCode):
        """
        Checks if the given termcode exists in the TERMCODES table
        :param term_code: the termcode to be checked
        :return: True if exists, False otherwise
        """
        self.cursor.execute("SELECT 1 FROM TERMCODE WHERE system = %s AND code = %s AND version = %s",
                            (term_code.system, term_code.code, term_code.version if term_code.version else ''))
        result = self.cursor.fetchone()
        return bool(result)

    def ui_profile_exists(self, ui_profile_name):
        """
        Checks if the given ui profile exists in the UI_PROFILE table
        :param ui_profile_name: the ui profile name to be checked
        :return: True if exists, False otherwise
        """
        self.cursor.execute("SELECT 1 FROM UI_PROFILE WHERE id = %s", (ui_profile_name,))
        return bool(self.cursor.fetchone())

    def link_contextualized_term_code_to_ui_profile(self,
                                                    contextualized_term_codes: List[Tuple[TermCode, TermCode, str]]):
        """
        Links a list of contextualized term codes to their corresponding ui profiles
        :param contextualized_term_codes: List of tuples each containing a context, a term code, and a UI profile name
        """
        values = [(context.system, context.code, context.version if context.version else '',
                   term_code.system, term_code.code, term_code.version if term_code.version else '',
                   ui_profile_name)
                  for context, term_code, ui_profile_name in contextualized_term_codes]

        psycopg2.extras.execute_batch(self.cursor, """
            INSERT INTO CONTEXTUALIZED_CONCEPT_TO_UI_PROFILE (context_id, termcode_id, profile_id) 
            SELECT C.id, T.id, U.id
            FROM 
                (SELECT id FROM CONTEXT WHERE system = %s AND code = %s AND version = %s) C,
                (SELECT id FROM TERMCODE WHERE system = %s AND code = %s AND version = %s) T,
                (SELECT id FROM UI_PROFILE WHERE id = %s) U
            ON CONFLICT DO NOTHING;
            """, values)

        self.db_connection.commit()

    def link_contextualized_term_code_to_mapping(self,
                                                 contextualized_term_codes: List[Tuple[TermCode, TermCode, str, str]]):
        values = [(context.system, context.code, context.version if context.version else '',
                   term_code.system, term_code.code, term_code.version if term_code.version else '',
                   mapping_name, mapping_type)
                  for context, term_code, mapping_name, mapping_type in contextualized_term_codes]
        psycopg2.extras.execute_batch(self.cursor, """
            INSERT INTO CONTEXTUALIZED_CONCEPT_TO_MAPPING (context_id, termcode_id, mapping_id) 
            SELECT C.id, T.id, M.id
            FROM 
                (SELECT id FROM CONTEXT WHERE system = %s AND code = %s AND version = %s) C,
                (SELECT id FROM TERMCODE WHERE system = %s AND code = %s AND version = %s) T,
                (SELECT id FROM MAPPING WHERE name = %s AND type = %s) M
            ON CONFLICT DO NOTHING;
            """, values)

    def insert_ui_profiles(self, named_ui_profile: Dict[str, UIProfile]):
        """
        Inserts the ui profile into the database
        :param named_ui_profile: the ui profile to be inserted
        """
        # Insert the UI profile
        values = [(name, profile.to_json()) for name, profile in named_ui_profile.items()]
        psycopg2.extras.execute_batch(self.cursor,
                                      "INSERT INTO UI_PROFILE (id , UI_Profile) VALUES (%s, %s)", values)
        self.db_connection.commit()

    def insert_mappings(self, named_mappings: Dict, mapping_type):
        """
        Inserts the mappings into the database
        :param named_mappings: the mappings to be inserted
        :param mapping_type: the type of the mappings
        """
        # Insert the Mapping
        values = [(name, mapping_type, mapping.to_json()) for name, mapping in named_mappings.items()]
        psycopg2.extras.execute_batch(self.cursor,
                                      "INSERT INTO MAPPING (name, type, content) VALUES (%s, %s, %s)", values)
        self.db_connection.commit()

    def insert_mapping(self, context: TermCode, term_code: TermCode, mapping_name: str, mapping_type: str,
                       mapping_json: str):
        """
        Inserts the mapping into the database
        :param context: The context associated with the term code and mapping
        :param term_code: The term code defining the primary key to resolve the mapping
        :param mapping_name: the name of the mapping
        :param mapping_type: the type of the mapping
        :param mapping_json: the json of the mapping
        """
        if not self.context_exists(context) or not self.termcode_exists(term_code):
            raise Exception("Context or term code does not exist in database")

        # Insert the Mapping
        self.cursor.execute(
            "INSERT INTO MAPPING (name, type, content) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING RETURNING id",
            (mapping_name, mapping_type, mapping_json))
        mapping_id = self.cursor.fetchone()[0]

        # Fetch IDs of the context and term code
        self.cursor.execute("SELECT id FROM CONTEXT WHERE system = %s AND code = %s AND version = %s",
                            (context.system, context.code, context.version if context.version else ''))
        context_id = self.cursor.fetchone()[0]

        self.cursor.execute("SELECT id FROM TERMCODE WHERE system = %s AND code = %s AND version = %s",
                            (term_code.system, term_code.code, term_code.version if term_code.version else ''))
        termcode_id = self.cursor.fetchone()[0]

        # Insert into CONTEXTUALIZED_CONCEPT_TO_MAPPING
        self.cursor.execute(
            "INSERT INTO CONTEXTUALIZED_CONCEPT_TO_MAPPING (context_id, termcode_id, mapping_id) "
            "VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
            (context_id, termcode_id, mapping_id))

        self.db_connection.commit()

    def drop_tables(self, table_name: str):
        """
        Drops the table with the given name
        :param table_name: name of the table to be dropped
        """
        drop_table_command = "DROP TABLE %s;" % table_name
        self.cursor.execute(drop_table_command)

    def get_ui_profile(self, context: TermCode, term_code: TermCode):
        """
        Gets the ui profile for the given term code
        :param context: context to get the ui profile for
        :param term_code: term code to get the ui profile for
        :return: the ui profile for the given term code
        """
        self.cursor.execute("""
            SELECT UP.UI_Profile
            FROM CONTEXTUALIZED_CONCEPT_TO_UI_PROFILE AS CCTUP
            INNER JOIN CONTEXT AS C ON CCTUP.context_id = C.id
            INNER JOIN TERMCODE AS T ON CCTUP.termcode_id = T.id
            INNER JOIN UI_PROFILE AS UP ON CCTUP.profile_id = UP.id
            WHERE C.system = %s AND C.code = %s AND C.version = %s
            AND T.system = %s AND T.code = %s AND T.version = %s;
            """, (context.system, context.code, context.version if context.version else '', term_code.system,
                  term_code.code, term_code.version if term_code.version else ''))
        result = self.cursor.fetchall()
        return result[0][0] if result else None

    def get_mapping(self, context: TermCode, term_code: TermCode, mapping_type: str):
        """
        Gets the mapping for the given term code
        :param context: context to get the mapping for
        :param term_code: term code to get the mapping for
        :param mapping_type: type of the mapping [CQL, FHIR_SERACH, FHIR_PATH, AQL]
        :return: the mapping for the given term code
        """
        self.cursor.execute("""
            SELECT M.content
            FROM CONTEXTUALIZED_CONCEPT_TO_MAPPING AS CCTM
            INNER JOIN CONTEXT AS C ON CCTM.context_id = C.id
            INNER JOIN TERMCODE AS T ON CCTM.termcode_id = T.id
            INNER JOIN MAPPING AS M ON CCTM.mapping_id = M.id
            WHERE C.system = %s AND C.code = %s AND (C.version = %s OR C.version IS NULL)
            AND T.system = %s AND T.code = %s AND (T.version = %s OR T.version IS NULL)
            AND M.type = %s;
            """, (context.system, context.code, context.version if context.version else '', term_code.system,
                  term_code.code, term_code.version if term_code.version else '', mapping_type))
        result = self.cursor.fetchall()
        print(result)
        return result[0][0] if result else None

    def add_ui_profiles_to_db(self, entries: List[TermEntry]):
        """
        Adds the ui profiles for each term entry to the database
        :param entries: term entries to add the ui profiles for
        """
        for entry in entries:
            if entry.selectable:
                if entry.uiProfile:
                    for term_code in entry.termCodes:
                        self.insert_ui_profile(entry.context, term_code, entry.uiProfile.to_json())
                else:
                    print(entry.termCode.display)
            self.add_ui_profiles_to_db(entry.children)

    def add_value_set(self, canonical_url, entries: List[TermCode]):
        """
        Adds the value set to the database
        :param canonical_url: canonical url of the value set
        :param entries: entries to add to the value set
        """
        values = [(canonical_url, entry.system, entry.code, entry.version if entry.version else '') for entry in
                  entries]
        psycopg2.extras.execute_batch(self.cursor,
                                      "INSERT INTO VALUE_SET (canonical_url, system, code, version) "
                                      "VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING",
                                      values)
        self.db_connection.commit()

    def get_term_codes_from_value_set(self, canonical_url) -> List[TermCode]:
        """
        Gets the term codes from the value set with the given canonical url
        :param canonical_url: canonical url of the value set
        :return: the term codes from the value set with the given canonical url
        """
        self.cursor.execute(
            "SELECT system, code, version FROM VALUE_SET WHERE canonical_url = %s",
            (canonical_url,))
        return [TermCode(row[0], row[1], row[2]) for row in self.cursor.fetchall()]

    def does_value_set_contain(self, canonical_url, term_code: TermCode):
        """
        Checks if the value set contains the given term code
        """
        self.cursor.execute(
            "SELECT 1 FROM VALUE_SET WHERE canonical_url = %s AND system = %s AND code = %s AND version = %s",
            (canonical_url, term_code.system, term_code.code, term_code.version if term_code.version else ''))
        return bool(self.cursor.fetchone())
