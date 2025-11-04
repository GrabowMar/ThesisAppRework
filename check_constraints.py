import sqlite3

conn = sqlite3.connect('src/data/thesis_app.db')
cursor = conn.cursor()

# Get all constraints
cursor.execute("""
    SELECT sql FROM sqlite_master 
    WHERE type='table' AND name='analysis_tasks'
""")
result = cursor.fetchone()
if result:
    schema = result[0]
    # Check for CHECK constraints
    if 'CHECK' in schema:
        print("CHECK constraints found in schema:")
        print(schema)
    else:
        print("No CHECK constraints in schema")
        print("\nTable schema:")
        print(schema)
else:
    print("Table not found")
