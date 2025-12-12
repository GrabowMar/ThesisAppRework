import sqlite3
conn = sqlite3.connect('src/data/thesis_app.db')
c = conn.cursor()
c.execute("""SELECT task_id, status FROM analysis_tasks 
             WHERE task_id='task_68a4102d7c93' 
             OR parent_task_id='task_68a4102d7c93'""")
for row in c.fetchall():
    print(row)
conn.close()
