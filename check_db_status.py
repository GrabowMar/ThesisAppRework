import sqlite3

# Connect to the database
conn = sqlite3.connect('src/data/thesis_app.db')
cursor = conn.cursor()

# Check task_e72e455f2245 with ALL columns
cursor.execute("SELECT * FROM analysis_tasks WHERE task_id = ?", ('task_e72e455f2245',))
columns = [description[0] for description in cursor.description]
task = cursor.fetchone()

if task:
    print("Task task_e72e455f2245 full details:")
    for col, val in zip(columns, task):
        print(f"  {col}: {val}")
else:
    print("Task task_e72e455f2245 not found")

# Check status values in database
cursor.execute("SELECT DISTINCT status FROM analysis_tasks ORDER BY status")
statuses = cursor.fetchall()
print(f"\nDistinct status values in DB:")
for s in statuses:
    print(f"  '{s[0]}'")

# Raw query matching the queue service query
cursor.execute("""
    SELECT task_id, status, is_main_task, parent_task_id
    FROM analysis_tasks 
    WHERE status = 'pending' 
      AND (is_main_task = 1 OR is_main_task IS NULL)
    ORDER BY created_at DESC
    LIMIT 10
""")
main_pending = cursor.fetchall()
print(f"\nPENDING main tasks (matching queue service query): {len(main_pending)}")
for t in main_pending:
    print(f"  {t[0]}: status='{t[1]}', is_main={t[2]}, parent={t[3]}")

conn.close()
