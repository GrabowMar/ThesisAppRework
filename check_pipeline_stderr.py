#!/usr/bin/env python
"""Check pipeline state - writes to stderr to bypass Flask output capture."""
import sqlite3
import json
import sys

DB_PATH = 'c:\\Users\\grabowmar\\Desktop\\ThesisAppRework\\src\\data\\thesis_app.db'

def write(msg):
    sys.stderr.write(msg + "\n")
    sys.stderr.flush()

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

write("=" * 60)
write("PIPELINE STATE CHECK")
write("=" * 60)

# Check pipeline_c71c2817c082
cur.execute('''
    SELECT pipeline_id, status, current_stage, current_job_index, progress_json
    FROM pipeline_executions 
    WHERE pipeline_id = 'pipeline_c71c2817c082'
''')
row = cur.fetchone()
if row:
    write(f"Pipeline: {row[0]}")
    write(f"  Status: {row[1]}")
    write(f"  Stage: {row[2]}")
    write(f"  Job Index: {row[3]}")
    progress = json.loads(row[4])
    write(f"  Analysis task_ids: {progress.get('analysis', {}).get('task_ids', [])}")
else:
    write("Pipeline not found!")

# Check all running pipelines
cur.execute('''
    SELECT pipeline_id, status, current_stage, current_job_index
    FROM pipeline_executions 
    WHERE status = 'running'
''')
running = cur.fetchall()
write(f"\nRunning pipelines: {len(running)}")
for r in running:
    write(f"  - {r[0]}: stage={r[2]}, job_idx={r[3]}")

write("=" * 60)
conn.close()
