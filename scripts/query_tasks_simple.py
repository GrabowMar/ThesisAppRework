import sqlite3
from pathlib import Path

db_path = Path(__file__).parent.parent / 'src' / 'data' / 'thesis_app.db'
conn = sqlite3.connect(str(db_path))
cur = conn.cursor()

print("\n=== Recent openai_codex-mini tasks ===\n")

rows = cur.execute("""
    SELECT task_id, target_app_number, status, is_main_task, service_name, 
           error_message, created_at, parent_task_id, total_steps, completed_steps
    FROM analysis_tasks 
    WHERE target_model='openai_codex-mini' 
    ORDER BY created_at DESC 
    LIMIT 30
""").fetchall()

main_tasks = [r for r in rows if r[3] == 1]
subtasks = [r for r in rows if r[3] == 0]

print(f"Found {len(main_tasks)} main tasks and {len(subtasks)} subtasks\n")

for r in main_tasks:
    task_id, app_num, status, is_main, svc_name, error, created, parent, total, completed = r
    print(f"MAIN: {task_id[:16]}... | App{app_num} | Status: {status}")
    print(f"      Steps: {completed}/{total} | Created: {created}")
    if error:
        print(f"      ERROR: {error[:80]}")
    
    # Find subtasks
    task_subtasks = [st for st in subtasks if st[7] == task_id]
    for st in task_subtasks:
        st_id, st_app, st_status, _, st_svc, st_err, st_created, _, _, _ = st
        print(f"      └─ {st_svc}: {st_status}", end='')
        if st_err:
            print(f" (ERROR: {st_err[:50]})")
        else:
            print()
    print()

conn.close()
