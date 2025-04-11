import unittest
import os
from util.sql.SqlMerger import SqlMerger


class SqlMergerTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.sql_merger = SqlMerger(
            sql_init_script_dir='../../resources/sql',
            sql_script_dir='./scripts'
        )
        cls.merged_script_targetfile = os.path.abspath(f'{cls.sql_merger.sql_script_dir}/R__Load_latest_ui_profile.sql')

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.merged_script_targetfile):
            os.remove(cls.merged_script_targetfile)

    def test_merge(self):
        self.sql_merger.execute_merge()
        self.assertTrue(os.path.exists(self.merged_script_targetfile))


if __name__ == '__main__':
    unittest.main()
