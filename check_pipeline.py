#!/usr/bin/env python
"""Check pipeline state directly from DB."""
import sqlite3
import json

DB_PATH = 'c:\\Users\\grabowmar\\Desktop\\ThesisAppRework\\src\\data\\thesis_app.db'

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Check pipeline_c71c2817c082
cur.execute('''
    SELECT pipeline_id, status, current_stage, current_job_index, progress_json
    FROM pipeline_executions 
    WHERE pipeline_id = 'pipeline_c71c2817c082'
''')
row = cur.fetchone()
if row:
    print(f"Pipeline: {row[0]}")
    print(f"  Status: {row[1]}")
    print(f"  Stage: {row[2]}")
    print(f"  Job Index: {row[3]}")
    progress = json.loads(row[4])
    print(f"  Analysis task_ids: {progress.get('analysis', {}).get('task_ids', [])}")
else:
    print("Pipeline not found!")

# Check all running pipelines
cur.execute('''
    SELECT pipeline_id, status, current_stage, current_job_index
    FROM pipeline_executions 
    WHERE status = 'running'
''')
running = cur.fetchall()
print(f"\nRunning pipelines: {len(running)}")
for r in running:
    print(f"  - {r[0]}: stage={r[2]}, job_idx={r[3]}")

conn.close()
