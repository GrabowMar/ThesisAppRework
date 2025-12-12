import sqlite3
conn = sqlite3.connect('src/data/thesis_app.db')
c = conn.cursor()

# Raw SQL update - reset main task  
c.execute("UPDATE analysis_tasks SET status='pending', error_message=NULL, started_at=NULL, completed_at=NULL WHERE task_id='task_68a4102d7c93'")
print(f'Updated {c.rowcount} rows (main task)')

# Raw SQL update - reset subtasks
c.execute("UPDATE analysis_tasks SET status='pending', error_message=NULL, started_at=NULL, completed_at=NULL WHERE parent_task_id='task_68a4102d7c93'")
print(f'Updated {c.rowcount} subtasks')

conn.commit()
print('Committed')

# Verify
c.execute("SELECT task_id, status FROM analysis_tasks WHERE task_id='task_68a4102d7c93' OR parent_task_id='task_68a4102d7c93'")
for row in c.fetchall():
    print(f'After commit: {row}')
conn.close()
