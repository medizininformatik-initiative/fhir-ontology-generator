import os
import re

import docker
import time
import psycopg2

from core.docker.Images import POSTGRES_IMAGE
from common.util.log.functions import get_logger

from importlib.resources import files


logger = get_logger(__file__)
sql_resources_dir = files(resources.sql)


def insert_content(base_file, content_to_insert, insert_after='SET row_security = off;'):
    with open(content_to_insert, 'r', encoding="UTF-8") as inserted_content_file:
        inserted_content = inserted_content_file.read()

    with open(base_file, 'r', encoding="UTF-8") as target_file:
        base_content = target_file.readlines()

    if insert_after is not None:
        for i, line in enumerate(base_content):
            if insert_after in line:
                insert_index = i + 1
                break
        else:
            raise ValueError(f"Anchor '{insert_after}' not found in {base_file}")
    else:
        raise ValueError("No place to insert content was given.")

    base_content.insert(insert_index, inserted_content + "\n")

    with open(base_file, 'w',encoding="UTF-8") as target_file:
        target_file.writelines(base_content)

    logger.debug(f"Content of {content_to_insert} has been inserted into {base_file}.")


class SqlMerger:
    def __init__(self,
                 container_name='pg_container',
                 db_name='merge_db',
                 db_user='dbuser',
                 db_password='dbpassword',
                 db_port=5430,
                 sql_init_script_dir='../../resources/sql',
                 sql_script_dir='source',
                 sql_mapped_dir='/tmp/sql',
                 repeatable_scripts_prefix='R__Load_latest_ui_profile_'
                 ):
        self.db_container = None
        self.conn = None
        self.container_name = container_name
        self.db_name = db_name
        self.db_user = db_user
        self.db_password = db_password
        self.db_port = db_port
        self.sql_init_script_dir = sql_init_script_dir
        self.sql_script_dir = sql_script_dir
        self.sql_mapped_dir = sql_mapped_dir
        self.repeatable_scripts_prefix = repeatable_scripts_prefix
        self.match_expression = f"^{repeatable_scripts_prefix}(\\d+)\\.sql$"
        self.pattern = re.compile(self.match_expression)

    def shutdown(self):
        if self.conn:
            logger.debug('Closing database connection')
            self.conn.close()
        logger.debug('Shutting down container')
        self.db_container.stop()
        self.db_container.remove()

    def setup_db_container(self):
        client = docker.from_env()
        logger.info(f"Starting PostgreSQL Docker container and binding to port {self.db_port}")
        self.db_container = client.containers.run(
            POSTGRES_IMAGE,
            name=self.container_name,
            environment={
                "POSTGRES_DB": self.db_name,
                "POSTGRES_USER": self.db_user,
                "POSTGRES_PASSWORD": self.db_password,
            },
            volumes={
                os.path.abspath(self.sql_script_dir): {
                    "bind": self.sql_mapped_dir,
                    "mode": "rw",
                }
            },
            ports={"5432/tcp": self.db_port},
            detach=True,
        )

    def get_connection(self):
        for _ in range(5):
            try:
                self.conn = psycopg2.connect(
                    dbname=self.db_name,
                    user=self.db_user,
                    password=self.db_password,
                    host="localhost",
                    port=self.db_port,
                )
            except psycopg2.OperationalError as e:
                logger.info("Connection failed => Retrying")
                time.sleep(5)

    def setup_container_and_get_connection(self):
        self.setup_db_container()
        time.sleep(5)
        self.get_connection()

    def populate_db(self):
        # init empty public schema (ddl only)
        with (sql_resources_dir.joinpath("init.sql").open(mode='r', encoding="UTF-8") as template,
              open(os.path.join(self.sql_script_dir, "public_init.sql"), mode='w', encoding="UTF-8") as target):
            target.write(template.read())

        with (sql_resources_dir.joinpath("create_functions.sql").open(mode='r', encoding="UTF-8") as template,
              open(os.path.join(self.sql_script_dir, "public_create_functions.sql"), mode='w', encoding="UTF-8") as target):
            target.write(template.read())

        cmd = f"sh -c 'psql -U {self.db_user} -d {self.db_name} < {self.sql_mapped_dir}/public_init.sql'"
        self.db_container.exec_run(cmd=cmd)

        # create functions to return existing ids if present on public schema
        cmd = f"sh -c 'psql -U {self.db_user} -d {self.db_name} < {self.sql_mapped_dir}/public_create_functions.sql'"
        self.db_container.exec_run(cmd=cmd)

        os.remove(os.path.join(self.sql_script_dir, "public_init.sql"))
        os.remove(os.path.join(self.sql_script_dir, "public_create_functions.sql"))

        # create and populate schemas for each load_ui_profile file
        for filename in os.listdir(self.sql_script_dir):
            if os.path.isfile(os.path.join(self.sql_script_dir, filename)):
                if re.match(self.match_expression, filename):
                    db_index = self.pattern.search(filename).group(1)
                    schema_name = f"import_{db_index}"
                    # initialize the db
                    with (sql_resources_dir.joinpath("init.sql").open(mode='r' ,encoding="UTF-8") as template, open(
                            os.path.join(self.sql_script_dir, f"init_{db_index}.sql"), mode='w' ,encoding="UTF-8") as target):
                        target.write(f"CREATE schema {schema_name};\n")
                        target.write(f"SET search_path TO {schema_name};\n\n")
                        target.write(template.read())

                    cmd = f"sh -c 'psql -U {self.db_user} -d {self.db_name} < {self.sql_mapped_dir}/init_{db_index}.sql'"
                    time.sleep(5)
                    logger.debug(f"Executing command {cmd}")
                    self.db_container.exec_run(cmd=cmd)
                    os.remove(os.path.join(self.sql_script_dir, f"init_{db_index}.sql"))

                    # import the data
                    with open(os.path.join(self.sql_script_dir, filename), mode='r', encoding="UTF-8") as template, open(
                            os.path.join(self.sql_script_dir, f"modified_{filename}"), mode='w',encoding="UTF-8") as target:
                        target.write(template.read().replace('public.', f'{schema_name}.'))
                    cmd = f"sh -c 'psql -U {self.db_user} -d {self.db_name} < {self.sql_mapped_dir}/modified_{filename}'"
                    time.sleep(5)
                    logger.debug(f"Executing command {cmd}")
                    self.db_container.exec_run(cmd=cmd)
                    os.remove(os.path.join(self.sql_script_dir, filename))
                    os.remove(os.path.join(self.sql_script_dir, f"modified_{filename}"))

                    # remove fk constraints
                    with sql_resources_dir.joinpath("remove_fk_constraints.sql").open(mode='r',encoding="UTF-8") as template, open(
                            os.path.join(self.sql_script_dir, "modified_remove_fk_constraints.sql"), mode='w',encoding="UTF-8") as target:
                        target.write(f"SET search_path TO {schema_name};\n\n")
                        target.write(template.read())
                    cmd = f"sh -c 'psql -U {self.db_user} -d {self.db_name} < {self.sql_mapped_dir}/modified_remove_fk_constraints.sql'"
                    time.sleep(5)
                    logger.debug(f"Executing command {cmd}")
                    self.db_container.exec_run(cmd=cmd)
                    os.remove(os.path.join(self.sql_script_dir, "modified_remove_fk_constraints.sql"))
                else:
                    logger.warning(f"{filename} does not match pattern {self.match_expression}")

    def merge_schemas(self):
        cur = self.conn.cursor()
        query_for_schemas = """
        SELECT schema_name
        FROM information_schema.schemata
        ORDER BY schema_name ASC;
        """

        cur.execute(query_for_schemas)
        schema_result = cur.fetchall()
        for schema in schema_result:
            if schema[0].startswith("import_"):
                schema_name = schema[0]
                logger.debug(f"Importing schema {schema_name}...to public")
                # Import the context table and write back new foreign keys to import schema
                query_copy_context = """
                WITH source_data AS (
                    SELECT id AS source_id, system, code, version, display
                    FROM {schema_name}.context
                ),
                updated_data AS (
                    SELECT sd.source_id, insert_context(sd.system, sd.code, sd.version, sd.display) AS target_id
                    FROM source_data sd
                )
                UPDATE {schema_name}.contextualized_termcode ict
                SET context_id = ud.target_id
                FROM updated_data ud
                WHERE ict.context_id = ud.source_id;
                """.format(schema_name=schema_name)

                # Import the termcode table and write back new foreign keys to import schema
                query_copy_termcode = """
                WITH source_data AS (
                    SELECT id AS source_id, system, code, version, display
                    FROM {schema_name}.termcode
                ),
                updated_data AS (
                    SELECT sd.source_id, insert_termcode(sd.system, sd.code, sd.version, sd.display) AS target_id
                    FROM source_data sd
                )
                UPDATE {schema_name}.contextualized_termcode ict
                SET termcode_id = ud.target_id
                FROM updated_data ud
                WHERE ict.termcode_id = ud.source_id;
                """.format(schema_name=schema_name)

                # Import the ui_profile table and write back new foreign keys to import schema
                query_copy_uiprofile = """
                WITH source_data AS (
                    SELECT id AS source_id, name, ui_profile
                    FROM {schema_name}.ui_profile
                ),
                updated_data AS (
                    SELECT sd.source_id, insert_uiprofile(sd.name, sd.ui_profile) AS target_id
                    FROM source_data sd
                )
                UPDATE {schema_name}.contextualized_termcode ict
                SET ui_profile_id = ud.target_id
                FROM updated_data ud
                WHERE ict.ui_profile_id = ud.source_id;
                """.format(schema_name=schema_name)

                cur.execute(query_copy_context)
                cur.execute(query_copy_termcode)
                cur.execute(query_copy_uiprofile)
                # commit those changes so that the foreign keys can be found in the following statement
                self.conn.commit()

                # Import the ui_profile table and write back new foreign keys to import schema
                query_copy_contextualized_termcodes = """
                INSERT INTO public.contextualized_termcode (context_termcode_hash, context_id, termcode_id, mapping_id, ui_profile_id)
                SELECT context_termcode_hash, context_id, termcode_id, mapping_id, ui_profile_id
                FROM {schema_name}.contextualized_termcode
                ON CONFLICT DO NOTHING;
                """.format(schema_name=schema_name)
                cur.execute(query_copy_contextualized_termcodes)
                self.conn.commit()

    def dump_merged_schema(self):
        cmd = f"pg_dump -U {self.db_user} -d {self.db_name} -a -O -t termcode -t context -t ui_profile -t mapping -t contextualized_termcode -t contextualized_termcode_to_criteria_set -t criteria_set -f {self.sql_mapped_dir}/R__Load_latest_ui_profile.sql"
        self.db_container.exec_run(cmd=cmd)
        self.db_container.exec_run(cmd=f'chown {os.geteuid()}:{os.getegid()} {self.sql_mapped_dir}/R__Load_latest_ui_profile.sql')
        insert_content(os.path.join(self.sql_script_dir, "R__Load_latest_ui_profile.sql"), str(sql_resources_dir.joinpath("delete_statements.sql")), )

    def create_functions(self):
        cmd = f"sh -c 'psql -U {self.db_user} -d {self.db_name} < {self.sql_mapped_dir}/create_functions.sql'"
        self.db_container.exec_run(cmd=cmd)

    def execute_merge(self):
        logger.info("Setting up container")
        self.setup_container_and_get_connection()
        logger.info("Populate database with initial values")
        self.populate_db()
        logger.info("Merge database schemata")
        self.merge_schemas()
        logger.info("Dump merged schema")
        self.dump_merged_schema()
