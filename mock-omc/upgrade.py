"""Small utility to ensure mock db has latest columns."""
import sqlite3, os
DB_PATH = os.path.join(os.path.dirname(__file__), "mock_omc.db")
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute("PRAGMA table_info(devices)")
cols = {row[1] for row in cur.fetchall()}
if 'cell_name' not in cols:
    cur.execute("ALTER TABLE devices ADD COLUMN cell_name TEXT")
    print('Added column cell_name')
conn.commit(); conn.close()
