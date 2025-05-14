from psycopg2._psycopg import connection


def test_ui_profile_data(database: connection):
    cursor = database.cursor()

    # Ensure that all contextualized term code entries reference a UI profile
    cursor.execute("""
        SELECT tc.system AS system_url, COUNT(*) AS cnt FROM contextualized_termcode ct 
        JOIN termcode tc ON ct.termcode_id = tc.id
        WHERE ct.ui_profile_id IS NULL GROUP BY tc.system;
    """)
    rows = cursor.fetchall()
    if len(rows) > 0:
        result_str = str(cursor.description) + "\n" + "\n".join(map(lambda r: str(r), rows))
        assert False, f"There are contextualized term codes without a UI profile reference:\n{result_str}"
