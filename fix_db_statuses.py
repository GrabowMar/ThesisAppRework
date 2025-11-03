import sqlite3

# Connect to the database
conn = sqlite3.connect('src/data/thesis_app.db')
cursor = conn.cursor()

# Fix all uppercase status values to lowercase
print("Fixing status values in database...")

status_mappings = {
    'PENDING': 'pending',
    'RUNNING': 'running',
    'COMPLETED': 'completed',
    'FAILED': 'failed',
    'CANCELLED': 'cancelled'
}

for old, new in status_mappings.items():
    cursor.execute("UPDATE analysis_tasks SET status = ? WHERE status = ?", (new, old))
    rows = cursor.rowcount
    if rows > 0:
        print(f"  Updated {rows} tasks from '{old}' to '{new}'")

conn.commit()

# Verify the fix
cursor.execute("""
    SELECT task_id, status, is_main_task 
    FROM analysis_tasks 
    WHERE status = 'pending' 
      AND (is_main_task = 1 OR is_main_task IS NULL)
    ORDER BY created_at DESC
    LIMIT 10
""")
main_pending = cursor.fetchall()
print(f"\nPENDING main tasks after fix: {len(main_pending)}")
for t in main_pending:
    print(f"  {t[0]}: status='{t[1]}', is_main={t[2]}")

conn.close()
print("\nDatabase fixed!")
