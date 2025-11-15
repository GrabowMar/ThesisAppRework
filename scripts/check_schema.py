"""Check the current database schema for generated_applications table."""
import sqlite3

db_path = r"C:\Users\grabowmar\Desktop\ThesisAppRework\src\data\thesis_app.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get table schema
cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='generated_applications'")
result = cursor.fetchone()
if result:
    print("Current schema:")
    print(result[0])
    print("\n" + "="*80 + "\n")

# Get indexes
cursor.execute("SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='generated_applications'")
indexes = cursor.fetchall()
if indexes:
    print("Indexes:")
    for idx in indexes:
        if idx[0]:  # Skip auto-generated indexes
            print(idx[0])

conn.close()
