from time import sleep
from typing import List

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
                CREATE TABLE IF NOT EXISTS TERMCODES(
                system VARCHAR(255) NOT NULL,
                code VARCHAR(255) NOT NULL,
                version VARCHAR(255),
                PRIMARY KEY (system, code, version),
                display VARCHAR(255) NOT NULL
            );
"""

"""
creates the table UI_PROFILE_TABLE:
system | code | version | UI_Profile 
With the combination of system, code and version as primary key
"""
create_ui_profile_table = """
    CREATE TABLE IF NOT EXISTS UI_PROFILE_TABLE(
    profile_name VARCHAR(255) NOT NULL,
    PRIMARY KEY (profile_name),
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
    system VARCHAR(255) NOT NULL,
    code VARCHAR(255) NOT NULL,
    version VARCHAR(255),
    PRIMARY KEY (system, code, version),
    display VARCHAR(255) NOT NULL
    );
"""

"""
creates the table CONTEXTUALIZED_CONCEPT_TO_UI_PROFILE:
with the primary key from the table CONTEXT, the table TERMCODE and the table UI_PROFILE_TABLE
"""
create_contextualized_concept_to_ui_profile_table = """
    CREATE TABLE IF NOT EXISTS CONTEXTUALIZED_CONCEPT_TO_UI_PROFILE(
    context_system VARCHAR(255) NOT NULL,
    context_code VARCHAR(255) NOT NULL,
    context_version VARCHAR(255),
    termcode_system VARCHAR(255) NOT NULL,
    termcode_code VARCHAR(255) NOT NULL,
    termcode_version VARCHAR(255),
    profile_name VARCHAR(255) NOT NULL,
    CONSTRAINT CONTEXT_ID FOREIGN KEY (context_system, context_code, context_version) 
    REFERENCES CONTEXT(system, code, version),
    CONSTRAINT CONCEPT_ID FOREIGN KEY (termcode_system, termcode_code, termcode_version) 
    REFERENCES TERMCODES(system, code, version),
    CONSTRAINT PROFILE_NAME FOREIGN KEY (profile_name) REFERENCES UI_PROFILE_TABLE(profile_name)
    );
"""

"""
creates the table MAPPING:
mapping_name | mapping_type | mapping_json
With the combination of mapping_name and mapping_type as primary key
"""
create_mapping_table = """
    CREATE TABLE IF NOT EXISTS MAPPING(
    mapping_name VARCHAR(255) NOT NULL,
    mapping_type VARCHAR(255) NOT NULL,
    PRIMARY KEY (mapping_name),
    mapping_json JSON NOT NULL
    );
"""

"""
creates the table CONTEXTUALIZED_CONCEPT_TO_MAPPING:
with the primary key from the table CONTEXT, the table TERMCODE and the table MAPPING
"""
create_contextualized_concept_to_mapping_table = """
    CREATE TABLE IF NOT EXISTS CONTEXTUALIZED_CONCEPT_TO_MAPPING(
    context_system VARCHAR(255) NOT NULL,
    context_code VARCHAR(255) NOT NULL,
    context_version VARCHAR(255),
    termcode_system VARCHAR(255) NOT NULL,
    termcode_code VARCHAR(255) NOT NULL,
    termcode_version VARCHAR(255),
    mapping_name VARCHAR(255) NOT NULL,
    CONSTRAINT CONTEXT_ID FOREIGN KEY (context_system, context_code, context_version) 
    REFERENCES CONTEXT(system, code, version),
    CONSTRAINT CONCEPT_ID FOREIGN KEY (termcode_system, termcode_code, termcode_version) 
    REFERENCES TERMCODES(system, code, version),
    CONSTRAINT MAPPING_NAME FOREIGN KEY (mapping_name) REFERENCES MAPPING(mapping_name)
    );
"""

"""
creates the table VALUE_SET:
"""
create_value_set_table = """
    CREATE TABLE IF NOT EXISTS VALUE_SET(
    canonical_url VARCHAR(255) NOT NULL,
    system VARCHAR(255) NOT NULL,
    code VARCHAR(255) NOT NULL,
    version VARCHAR(255),
    PRIMARY KEY (canonical_url, system, code, version)
    );
"""

add_value_set_table_canonical_url_index = """
    CREATE INDEX IF NOT EXISTS canonical_url_index ON VALUE_SET(canonical_url);
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
            # self.drop_tables('TERMCODE')
            # self.drop_tables('UI_PROFILE_TABLE')
            self.cursor.execute(create_term_code_table)
            self.cursor.execute(create_ui_profile_table)
            self.cursor.execute(create_context_table)
            self.cursor.execute(create_contextualized_concept_to_ui_profile_table)
            self.cursor.execute(create_mapping_table)
            self.cursor.execute(create_contextualized_concept_to_mapping_table)
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
        values = [(term_code.system, term_code.code, term_code.version if term_code.version else "", term_code.display)
                  for term_code in term_codes]
        psycopg2.extras.execute_batch(self.cursor, "INSERT INTO TERMCODES VALUES (%s, %s, %s, %s)", values)
        self.db_connection.commit()

    def insert_context(self, context_codes: List[TermCode]):
        """
        Inserts the context codes into the database
        :param context_codes: the context codes to be inserted
        """
        values = [(context_code.system, context_code.code, context_code.version if context_code.version else "",
                   context_code.display)
                  for context_code in context_codes]
        psycopg2.extras.execute_batch(self.cursor, "INSERT INTO CONTEXT VALUES (%s, %s, %s, %s)", values)
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
        self.cursor.execute("SELECT 1 FROM TERMCODES WHERE system = %s AND code = %s AND version = %s",
                            (term_code.system, term_code.code, term_code.version if term_code.version else ''))
        result = self.cursor.fetchone()
        return bool(result)

    def insert_ui_profile(self, context: TermCode, term_code: TermCode, ui_profile: UIProfile):
        """
        Inserts the ui profile into the database
        :param context: The context associated with the term code and UI profile
        :param term_code: The term code defining the primary key to resolve the ui profile
        :param ui_profile: the ui profile to be inserted
        """
        if not self.context_exists(context) or not self.termcode_exists(term_code):
            raise Exception("Context or termcode does not exist in database")

        self.cursor.execute(
            "INSERT INTO UI_PROFILE_TABLE (profile_name, UI_Profile) "
            "VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (ui_profile.name, ui_profile.to_json()))

        contextualized_concept_values = (
            context.system, context.code, context.version, term_code.system, term_code.code, term_code.version,
            ui_profile.name)
        self.cursor.execute(
            "INSERT INTO CONTEXTUALIZED_CONCEPT_TO_UI_PROFILE (context_system, context_code, context_version, "
            "termcode_system, termcode_code, termcode_version, profile_name) VALUES (%s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT DO NOTHING",
            contextualized_concept_values)

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
        mapping_values = (mapping_name, mapping_type, mapping_json)
        self.cursor.execute(
            "INSERT INTO MAPPING (mapping_name, mapping_type, mapping_json) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
            mapping_values)

        contextualized_mapping_values = (
            context.system, context.code, context.version, term_code.system, term_code.code, term_code.version,
            mapping_name)
        self.cursor.execute(
            "INSERT INTO CONTEXTUALIZED_CONCEPT_TO_MAPPING (context_system, context_code, context_version, "
            "termcode_system, termcode_code, termcode_version, mapping_name) VALUES (%s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT DO NOTHING",
            contextualized_mapping_values)
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
            INNER JOIN CONTEXT AS C ON CCTUP.context_system = C.system AND CCTUP.context_code = C.code 
            AND (CCTUP.context_version = C.version OR CCTUP.context_version IS NULL)
            INNER JOIN TERMCODES AS T ON CCTUP.termcode_system = T.system AND CCTUP.termcode_code = T.code 
            AND (CCTUP.termcode_version = T.version OR CCTUP.termcode_version IS NULL)
            INNER JOIN UI_PROFILE_TABLE AS UP ON CCTUP.profile_name = UP.profile_name
            WHERE C.system = %s AND C.code = %s AND (C.version = %s or C.version is NULL) 
            AND T.system = %s AND T.code = %s AND (T.version = %s or T.version is NULL);
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
            SELECT M.mapping_json
            FROM CONTEXTUALIZED_CONCEPT_TO_MAPPING AS CCTM
            INNER JOIN CONTEXT AS C ON CCTM.context_system = C.system AND CCTM.context_code = C.code 
            AND (CCTM.context_version = C.version or CCTM.context_version IS NULL)
            INNER JOIN TERMCODES AS T ON CCTM.termcode_system = T.system AND CCTM.termcode_code = T.code 
            AND (CCTM.termcode_version = T.version or CCTM.termcode_version IS NULL)
            INNER JOIN MAPPING AS M ON CCTM.mapping_name = M.mapping_name
            WHERE C.system = %s AND C.code = %s AND (C.version = %s OR C.version IS NULL)
            AND T.system = %s AND T.code = %s AND (T.version = %s OR T.version IS NULL)
            AND M.mapping_type = %s;
            """, (context.system, context.code, context.version if context.version else '', term_code.system,
                  term_code.code, term_code.version if term_code.version else '',
                  mapping_type))
        result = self.cursor.fetchall()
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
        for entry in entries:
            self.cursor.execute(
                "INSERT INTO VALUE_SET (canonical_url, system, code, version) VALUES (%s, %s, %s, %s) "
                "ON CONFLICT DO NOTHING",
                (canonical_url, entry.system, entry.code, entry.version if entry.version else ''))

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
