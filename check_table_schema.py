import sqlite3

conn = sqlite3.connect('src/data/thesis_app.db')
cursor = conn.cursor()
cursor.execute('SELECT sql FROM sqlite_master WHERE type="table" AND name="analysis_tasks"')
schema = cursor.fetchone()[0]
print(schema)
