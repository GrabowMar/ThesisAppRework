import sqlite3
import os
import time

DB_PATH = 'src/data/thesis_app.db'

print('DB file exists:', os.path.exists(DB_PATH))
print('DB file size:', os.path.getsize(DB_PATH))

# Check current status with fresh connection
conn1 = sqlite3.connect(DB_PATH, timeout=10, isolation_level=None)  # Autocommit
c1 = conn1.cursor()
c1.execute("SELECT task_id, status FROM analysis_tasks WHERE task_id='task_68a4102d7c93'")
print('FRESH READ 1:', c1.fetchone())
conn1.close()

# Update with new connection
conn2 = sqlite3.connect(DB_PATH, timeout=10, isolation_level=None)  # Autocommit
c2 = conn2.cursor()

# Show file modification time before
print('File mtime before:', os.path.getmtime(DB_PATH))

c2.execute("UPDATE analysis_tasks SET status='pending' WHERE task_id='task_68a4102d7c93'")
c2.execute("UPDATE analysis_tasks SET status='pending' WHERE parent_task_id='task_68a4102d7c93'")
print(f'Rows changed: {c2.rowcount}')

# Show file modification time after
print('File mtime after:', os.path.getmtime(DB_PATH))
conn2.close()

# Small delay
time.sleep(0.5)

# Verify with another fresh connection
conn3 = sqlite3.connect(DB_PATH, timeout=10, isolation_level=None)  # Autocommit
c3 = conn3.cursor()
c3.execute("SELECT task_id, status FROM analysis_tasks WHERE task_id='task_68a4102d7c93' OR parent_task_id='task_68a4102d7c93'")
for row in c3.fetchall():
    print('AFTER:', row)
conn3.close()

