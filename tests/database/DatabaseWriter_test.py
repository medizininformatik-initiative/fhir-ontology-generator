import unittest

import docker

from cohort_selection_ontology.model.mapping import CQLMapping
from cohort_selection_ontology.model.ui_data import TermCode
from cohort_selection_ontology.model.ui_profile import UIProfile
from cohort_selection_ontology.util.database import DataBaseWriter
from common.constants.docker import POSTGRES_IMAGE


class DataBaseWriterTest(unittest.TestCase):
    container = None
    client = None

    # before each tests
    @classmethod
    def setUp(cls):
        # start up docker container with database
        cls.client = docker.from_env()
        cls.container = cls.client.containers.run(
            POSTGRES_IMAGE,
            detach=True,
            ports={"5432/tcp": 5432},
            name="test_db",
            environment={
                "POSTGRES_USER": "codex-postgres",
                "POSTGRES_PASSWORD": "codex-password",
                "POSTGRES_DB": "codex_ui",
            },
        )

        cls.dbw = DataBaseWriter()

    @classmethod
    def tearDown(cls):
        # stop and remove the container
        cls.container.stop()
        cls.container.remove()

    def test_insert_term_codes(self):
        term_codes = [
            TermCode(system="http://test.com", code="tests", display="test"),
            TermCode(system="http://test.com", code="test2", display="test2"),
        ]
        self.dbw.insert_term_codes(term_codes)
        for term_code in term_codes:
            self.assertTrue(self.dbw.termcode_exists(term_code))

    def test_insert_ui_profile(self):
        term_code = TermCode(system="http://test.com", code="test", display="test")
        context = TermCode(system="http://test.com", code="context", display="context")
        ui_profile = UIProfile("test")
        self.dbw.insert_term_codes([term_code])
        self.dbw.insert_context_codes([context])
        self.dbw.insert_ui_profile(context, term_code, ui_profile)
        self.assertTrue(
            UIProfile(**self.dbw.get_ui_profile(context, term_code)) == ui_profile
        )

    def test_insert_value_set(self):
        term_codes = [
            TermCode(system="http://test.com", code="test", display="test"),
            TermCode(system="http://test.com", code="test2", display="test2"),
        ]
        self.dbw.add_critieria_set("test", term_codes)
        self.assertTrue(self.dbw.get_term_codes_from_value_set("test") == term_codes)

    def test_insert_mapping(self):
        term_code = TermCode(system="http://test.com", code="test", display="test")
        context = TermCode(system="http://test.com", code="context", display="context")
        mapping = CQLMapping("test")
        self.dbw.insert_term_codes([term_code])
        self.dbw.insert_context_codes([context])
        self.assertTrue(
            CQLMapping.from_json(self.dbw.get_mapping(context, term_code, "CQL"))
            == mapping
        )
