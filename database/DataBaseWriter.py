import uuid
from time import sleep
from typing import List, Tuple, Dict

import psycopg2.extras
import psycopg2

from TerminologService.ValueSetResolver import get_termcodes_from_onto_server
from model.UIProfileModel import UIProfile
from model.UiDataModel import TermCode, TermEntry

NAMESPACE_UUID = uuid.UUID('00000000-0000-0000-0000-000000000000')

"""
creates the table TermCode:
system | code | version | display 
With the combination of system, code and version as primary key
"""
create_term_code_table = """
    CREATE TABLE IF NOT EXISTS termcode(
    id SERIAL PRIMARY KEY,
    system TEXT NOT NULL,
    code TEXT NOT NULL,
    version TEXT,
    UNIQUE NULLS NOT DISTINCT (system, code, version),
    display TEXT NOT NULL
    );
"""

"""
creates the table UI_PROFILE:
id | name | UI_Profile 
With the combination of system, code and version as primary key
"""
create_ui_profile_table = """
    CREATE TABLE IF NOT EXISTS ui_profile(
    id         SERIAL PRIMARY KEY,
    name       TEXT NOT NULL,
    ui_profile JSON NOT NULL
    );
"""

"""
creates the table MAPPING:
id | name | type| content
"""
create_mapping_table = """
    CREATE TABLE IF NOT EXISTS mapping(
        id      SERIAL PRIMARY KEY,
        name    TEXT NOT NULL,
        type    TEXT NOT NULL,
        UNIQUE (name, type),
        content JSON NOT NULL
    );
"""

"""
creates the table CONTEXT:
system | code | display | version
With the combination of system and code as primary key
"""
create_context_table = """
    CREATE TABLE IF NOT EXISTS context(
    id SERIAL PRIMARY KEY,
    system TEXT NOT NULL,
    code TEXT NOT NULL,
    version TEXT,
    UNIQUE NULLS NOT DISTINCT (system, code, version),
    display TEXT NOT NULL
    );
"""

"""
creates the table contextualized_termcode:
context_termcode_hash | context_id | termcode_id | mapping_id | ui_profile_id
"""
create_contextualized_term_code = """
    CREATE TABLE IF NOT EXISTS contextualized_termcode(
    context_termcode_hash TEXT PRIMARY KEY,
    context_id            INTEGER NOT NULL,
    termcode_id           INTEGER NOT NULL,
    mapping_id            INTEGER,
    ui_profile_id         INTEGER,
    CONSTRAINT CONTEXT_ID_FK FOREIGN KEY (context_id)
        REFERENCES CONTEXT (id) ON DELETE CASCADE,
    CONSTRAINT CONCEPT_ID_FK FOREIGN KEY (termcode_id)
        REFERENCES termcode (id) ON DELETE CASCADE,
    CONSTRAINT mapping_id_fk FOREIGN KEY (mapping_id)
        REFERENCES mapping (id),
    CONSTRAINT ui_profile_id_fk FOREIGN KEY (ui_profile_id)
        REFERENCES ui_profile (id),
    UNIQUE (context_id, termcode_id)
    );
"""

"""
creates the table VALUE_SET:
"""
create_contextualized_value_set = """
    CREATE TABLE IF NOT EXISTS criteria_set(
    id  SERIAL PRIMARY KEY,
    url TEXT UNIQUE NOT NULL
    );
"""

"""
creates the contextualized term code to contextualized value set table:
"""
create_contextualized_term_code_to_contextualized_value_set = """
    CREATE TABLE IF NOT EXISTS contextualized_termcode_to_criteria_set(
    context_termcode_hash       TEXT    NOT NULL,
    criteria_set_id INTEGER NOT NULL,
    UNIQUE (context_termcode_hash, criteria_set_id),
    CONSTRAINT criteria_set_ID_FK FOREIGN KEY (criteria_set_id)
        REFERENCES criteria_set (id) ON DELETE CASCADE ,
    CONSTRAINT CONTEXTUALIZED_TERMCODE_ID_FK FOREIGN KEY (context_termcode_hash)
        REFERENCES CONTEXTUALIZED_TERMCODE (context_termcode_hash) ON DELETE CASCADE
    );
"""

add_join_index_for_contextualized_mapping = """
    CREATE INDEX idx_mapping_name_mapping ON mapping (name);
    CREATE INDEX idx_contextualized_termcode_termcode_fk ON contextualized_termcode (termcode_id);
"""

add_comment_on_context_termcode_hash = """
    COMMENT ON COLUMN contextualized_termcode.context_termcode_hash IS 'This value is hashed using UUID-V3 (MD5) from 
    the concatenated string of (context.system, context.code, context.version, termcode.system, termcode.code, 
    termcode.version), omitting null values for version and without any delimiters.';
"""


class DataBaseWriter:
    """
    DataBaseWriter is a class that handles the connection to the database and the insertion of data into the database
    for the feasibility tool ontology.
    """

    def __init__(self, port=5432):
        self.db_connection = None
        for _ in range(30):  # retry for 30 times
            try:
                self.db_connection = psycopg2.connect(
                    database='codex_ui',
                    user='codex-postgres',
                    host='localhost',
                    password='codex-password',
                    port=port

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
            self.cursor.execute(create_context_table)
            self.cursor.execute(create_ui_profile_table)
            self.cursor.execute(create_mapping_table)
            self.cursor.execute(create_contextualized_term_code)
            self.cursor.execute(create_contextualized_value_set)
            self.cursor.execute(create_contextualized_term_code_to_contextualized_value_set)
            self.cursor.execute(add_join_index_for_contextualized_mapping)
            self.cursor.execute(add_comment_on_context_termcode_hash)
            self.db_connection.commit()

    def __del__(self):
        """
        Closes the connection to the database
        """
        if self.db_connection is not None:
            self.cursor.close()
            self.db_connection.close()

    @staticmethod
    def calculate_context_term_code_hash(context: TermCode, term_code: TermCode) -> str:
        """
        Calculates the hash for the context term code
        :param context: the context
        :param term_code: the term code
        :return: the hash
        """
        return str(uuid.uuid3(NAMESPACE_UUID,
                              f"{context.system}{context.code}{context.version if context.version else ''}"
                              f"{term_code.system}{term_code.code}{term_code.version if term_code.version else ''}"))

    def insert_term_codes(self, term_codes: List[TermCode]):
        """
        Inserts the term codes into the database
        :param term_codes: the term codes to be inserted
        """
        values = set(
            (term_code.system, term_code.code, term_code.version if term_code.version else "", term_code.display)
            for term_code in term_codes)
        psycopg2.extras.execute_batch(self.cursor,
                                      "INSERT INTO termcode (system, code, version, display) VALUES (%s, %s, %s, %s)"
                                      "ON CONFLICT DO NOTHING",
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
                                      "INSERT INTO context (system, code, version, display) VALUES (%s, %s, %s, %s)"
                                      "ON CONFLICT DO NOTHING",
                                      values)
        self.db_connection.commit()

    def context_exists(self, context: TermCode):
        """
        Checks if the given context exists in the CONTEXT table
        :param context: the context to be checked
        :return: True if exists, False otherwise
        """
        self.cursor.execute("SELECT 1 FROM context WHERE system = %s AND code = %s AND version = %s",
                            (context.system, context.code, context.version if context.version else ''))
        return bool(self.cursor.fetchone())

    def termcode_exists(self, term_code: TermCode):
        """
        Checks if the given termcode exists in the TERMCODES table
        :param term_code: the termcode to be checked
        :return: True if exists, False otherwise
        """
        self.cursor.execute("SELECT 1 FROM termcode WHERE system = %s AND code = %s AND version = %s",
                            (term_code.system, term_code.code, term_code.version if term_code.version else ''))
        result = self.cursor.fetchone()
        return bool(result)

    def ui_profile_exists(self, ui_profile_name):
        """
        Checks if the given ui profile exists in the UI_PROFILE table
        :param ui_profile_name: the ui profile name to be checked
        :return: True if exists, False otherwise
        """
        self.cursor.execute("SELECT 1 FROM ui_profile WHERE id = %s", (ui_profile_name,))
        return bool(self.cursor.fetchone())

    def link_contextualized_term_code_to_ui_profile(self,
                                                    contextualized_term_codes: List[Tuple[TermCode, TermCode, str]]):
        """
        Links a list of contextualized term codes to their corresponding ui profiles
        :param contextualized_term_codes: List of tuples each containing a context, a term code, and a UI profile name
        """
        values = [(self.calculate_context_term_code_hash(context, term_code), context.system, context.code,
                   context.version if context.version else '',
                   term_code.system, term_code.code, term_code.version if term_code.version else '',
                   ui_profile_name)
                  for context, term_code, ui_profile_name in contextualized_term_codes]

        psycopg2.extras.execute_batch(self.cursor, """
            INSERT INTO contextualized_termcode (context_termcode_hash, context_id, termcode_id, ui_profile_id) 
            SELECT %s, C.id, T.id, U.id
            FROM 
                (SELECT id FROM context WHERE system = %s AND code = %s AND version = %s) C,
                (SELECT id FROM termcode WHERE system = %s AND code = %s AND version = %s) T,
                (SELECT id FROM ui_profile WHERE name = %s) U
            ON CONFLICT (context_termcode_hash)
            DO UPDATE SET ui_profile_id = EXCLUDED.ui_profile_id;
            """, values)
        self.db_connection.commit()

    def link_contextualized_term_code_to_mapping(self,
                                                 contextualized_term_codes: List[Tuple[TermCode, TermCode, str, str]]):
        values = [(self.calculate_context_term_code_hash(context, term_code), context.system, context.code,
                   context.version if context.version else '',
                   term_code.system, term_code.code, term_code.version if term_code.version else '',
                   mapping_name, mapping_type)
                  for context, term_code, mapping_name, mapping_type in contextualized_term_codes]

        psycopg2.extras.execute_batch(self.cursor, """
            INSERT INTO contextualized_termcode (context_termcode_hash , context_id, termcode_id, mapping_id) 
            SELECT %s, C.id, T.id, M.id
            FROM 
                (SELECT id FROM context WHERE system = %s AND code = %s AND version = %s) C,
                (SELECT id FROM termcode WHERE system = %s AND code = %s AND version = %s) T,
                (SELECT id FROM mapping WHERE name = %s AND type = %s) M
            ON CONFLICT (context_termcode_hash)
            DO UPDATE SET mapping_id = EXCLUDED.mapping_id;
            """, values)
        self.db_connection.commit()

    def insert_ui_profiles(self, named_ui_profile: Dict[str, UIProfile]):
        """
        Inserts the ui profile into the database
        :param named_ui_profile: the ui profile to be inserted
        """
        # Insert the UI profile
        values = [(name, profile.to_json()) for name, profile in named_ui_profile.items()]
        psycopg2.extras.execute_batch(self.cursor,
                                      "INSERT INTO ui_profile (name , ui_profile) VALUES (%s, %s)", values)
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
                                      "INSERT INTO mapping (name, type, content) VALUES (%s, %s, %s)", values)
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
            INNER JOIN UI_PROFILE AS UP ON CCTUP.ui_profile_id = UP.id
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
            INNER JOIN context AS C ON CCTM.context_id = C.id
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

    def add_value_set(self, canonical_url, entries: List[TermCode]):
        """
        Adds the value set to the database
        :param canonical_url: canonical url of the value set
        :param entries: entries to add to the value set
        """
        self.cursor.execute(
            """INSERT INTO criteria_set (url) VALUES (%s) ON CONFLICT DO NOTHING""",
            (canonical_url,))
        # TODO: Remove this context once we know the context:
        context = TermCode("fdpg.mii.bkfz", "Diagnose", "Diagnose", "1.0.0")
        self.insert_context_codes([context])

        self.insert_term_codes(entries)

        contextualized_termcode_values = [
            (self.calculate_context_term_code_hash(context, term_code), context.system, context.code,
             context.version if context.version else '',
             term_code.system, term_code.code, term_code.version if term_code.version else '') for term_code in entries]
        psycopg2.extras.execute_batch(self.cursor,
                                      """INSERT INTO contextualized_termcode (context_termcode_hash, context_id, termcode_id) 
                                         SELECT %s, C.id, T.id
                                         FROM 
                                            (SELECT id FROM context WHERE system = %s AND code = %s AND version = %s) C,
                                            (SELECT id FROM termcode WHERE system = %s AND code = %s AND version = %s) T
                                         ON CONFLICT DO NOTHING""", contextualized_termcode_values)
        self.db_connection.commit()

        values = [(self.calculate_context_term_code_hash(context, term_code), canonical_url) for term_code in entries]
        print(canonical_url)
        psycopg2.extras.execute_batch(self.cursor,
                                      """
                                      INSERT INTO contextualized_termcode_to_criteria_set (context_termcode_hash, criteria_set_id) 
                                      SELECT %s, CS.id 
                                      FROM criteria_set CS 
                                      WHERE CS.url = %s 
                                      ON CONFLICT DO NOTHING
                                      """,
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

    def write_ui_profiles_to_db(self, contextualized_term_code_to_ui_profile, named_ui_profiles,
                                contextualized_codes_exist: bool = False):
        context_codes = [context_code for (context_code, _) in contextualized_term_code_to_ui_profile.keys()]
        term_codes = [term_code for (_, term_code) in contextualized_term_code_to_ui_profile.keys()]
        if not contextualized_codes_exist:
            self.insert_context_codes(context_codes)
            self.insert_term_codes(term_codes)
        self.insert_ui_profiles(named_ui_profiles)
        values = [(context_code, term_code, ui_profile_name) for (context_code, term_code), ui_profile_name in
                  contextualized_term_code_to_ui_profile.items()]
        self.link_contextualized_term_code_to_ui_profile(values)

    def write_mapping_to_db(self, contextualized_term_code_to_mapping, named_mappings, mapping_type,
                            contextualized_codes_exist: bool = False):
        context_codes = [context_code for (context_code, _) in contextualized_term_code_to_mapping.keys()]
        term_codes = [term_code for (_, term_code) in contextualized_term_code_to_mapping.keys()]
        if not contextualized_codes_exist:
            self.insert_context_codes(context_codes)
            self.insert_term_codes(term_codes)
        self.insert_mappings(named_mappings, mapping_type)
        values = [(context_code, term_code, mapping_name, mapping_type) for (context_code, term_code), mapping_name in
                  contextualized_term_code_to_mapping.items()]
        self.link_contextualized_term_code_to_mapping(values)

    def write_vs_to_db(self, profiles: List[UIProfile]):
        for ui_profile in profiles:
            for attribute_definition in ui_profile.attributeDefinitions:
                if attribute_definition.type == "reference":
                    vs = attribute_definition.referenceCriteriaSet
                    # TODO: Maybe better to get them upfront
                    term_codes = get_termcodes_from_onto_server(vs)
                    self.add_value_set(vs, term_codes)
