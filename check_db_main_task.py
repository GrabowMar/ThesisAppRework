import sqlite3

# Connect to the database
conn = sqlite3.connect('src/data/thesis_app.db')
cursor = conn.cursor()

# Check schema for analysis_tasks table
cursor.execute("PRAGMA table_info(analysis_tasks)")
columns = cursor.fetchall()

print("Column info for is_main_task:")
for col in columns:
    if 'is_main_task' in col[1]:
        print(f"  {col}")

# Check task_e72e455f2245 specifically
cursor.execute("SELECT task_id, is_main_task, parent_task_id, status FROM analysis_tasks WHERE task_id = ?", ('task_e72e455f2245',))
task = cursor.fetchone()

if task:
    print(f"\nTask task_e72e455f2245:")
    print(f"  task_id: {task[0]}")
    print(f"  is_main_task: {task[1]}")
    print(f"  parent_task_id: {task[2]}")
    print(f"  status: {task[3]}")
else:
    print("\nTask task_e72e455f2245 not found")

# Check all recent pending tasks
cursor.execute("""
    SELECT task_id, is_main_task, parent_task_id, status, created_at 
    FROM analysis_tasks 
    WHERE status = 'pending' 
    ORDER BY created_at DESC 
    LIMIT 10
""")
tasks = cursor.fetchall()

print(f"\n{len(tasks)} recent PENDING tasks:")
for t in tasks:
    print(f"  {t[0]}: is_main_task={t[1]}, parent_task={t[2]}, status={t[3]}")

conn.close()
