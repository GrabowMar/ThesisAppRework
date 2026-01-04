"""Debug script to inspect pipeline state."""
import sqlite3
import json

conn = sqlite3.connect('src/data/thesis_app.db')
cursor = conn.cursor()

# Get detailed pipeline info
cursor.execute('''
    SELECT pipeline_id, status, current_stage, current_job_index, error_message, progress_json 
    FROM pipeline_executions 
    WHERE pipeline_id LIKE 'pipeline_2775%'
''')
row = cursor.fetchone()

print('=== PIPELINE STATE ===')
print(f'ID: {row[0]}')
print(f'Status: {row[1]}')
print(f'Stage: {row[2]}')
print(f'Job Index: {row[3]}')
print(f'Error: {row[4]}')
print()

progress = json.loads(row[5]) if row[5] else {}
print('=== PROGRESS JSON ===')
print(json.dumps(progress, indent=2))

conn.close()
