import sqlite3

conn = sqlite3.connect('src/data/thesis_app.db')
cursor = conn.cursor()

cursor.execute("""
    SELECT task_id, status, is_main_task, created_at
    FROM analysis_tasks 
    WHERE status = 'pending' 
      AND (is_main_task = 1 OR is_main_task IS NULL)
    ORDER BY created_at DESC 
    LIMIT 10
""")
tasks = cursor.fetchall()

print(f"Pending main tasks: {len(tasks)}")
for t in tasks:
    print(f"  {t[0]}: status={t[1]}, is_main={t[2]}, created={t[3]}")

conn.close()
