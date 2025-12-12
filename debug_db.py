import sqlite3
conn = sqlite3.connect('src/data/thesis_app.db', isolation_level='EXCLUSIVE')
c = conn.cursor()

print('BEFORE:')
c.execute("SELECT task_id, status FROM analysis_tasks WHERE task_id='task_68a4102d7c93' OR parent_task_id='task_68a4102d7c93' ORDER BY task_id")
for row in c.fetchall():
    print(f'  {row}')

print('\nUPDATE:')
c.execute("UPDATE analysis_tasks SET status='pending' WHERE task_id='task_68a4102d7c93'")
print(f'  Main task: {c.rowcount} rows')
c.execute("UPDATE analysis_tasks SET status='pending' WHERE parent_task_id='task_68a4102d7c93'")
print(f'  Subtasks: {c.rowcount} rows')

conn.commit()
print('\nCOMMITTED')

print('\nAFTER:')
c.execute("SELECT task_id, status FROM analysis_tasks WHERE task_id='task_68a4102d7c93' OR parent_task_id='task_68a4102d7c93' ORDER BY task_id")
for row in c.fetchall():
    print(f'  {row}')

conn.close()
print('\nCONNECTION CLOSED')

# Check with fresh connection
print('\nFRESH CONNECTION:')
conn2 = sqlite3.connect('src/data/thesis_app.db')
c2 = conn2.cursor()
c2.execute("SELECT task_id, status FROM analysis_tasks WHERE task_id='task_68a4102d7c93' OR parent_task_id='task_68a4102d7c93' ORDER BY task_id")
for row in c2.fetchall():
    print(f'  {row}')
conn2.close()
