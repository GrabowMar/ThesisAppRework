#!/usr/bin/env python3
"""
Debug script to check if task metadata contains selected tools
"""
import os
import sys
import sqlite3
import json
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))

# Connect to database
db_path = src_path / 'data' / 'development.db'
if not db_path.exists():
    print(f"Database not found at {db_path}")
    sys.exit(1)

conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

# Get all table names to understand the schema
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cursor.fetchall()]
print("Available tables:", tables)

# Find the analysis task table
task_table = None
for table in tables:
    if 'task' in table.lower() or 'analysis' in table.lower():
        print(f"\nChecking table: {table}")
        cursor.execute(f"PRAGMA table_info({table})")
        columns = cursor.fetchall()
        col_names = [col[1] for col in columns]
        print("Columns:", col_names)
        
        if 'metadata_json' in col_names or 'custom_options' in col_names:
            task_table = table
            break

if not task_table:
    print("No task table found with metadata")
    conn.close()
    sys.exit(1)

# Query recent tasks
print(f"\nQuerying recent tasks from {task_table}:")
cursor.execute(f"""
    SELECT * FROM {task_table} 
    ORDER BY created_at DESC 
    LIMIT 5
""")

rows = cursor.fetchall()
cursor.execute(f"PRAGMA table_info({task_table})")
columns = [col[1] for col in cursor.fetchall()]

for row in rows:
    task_data = dict(zip(columns, row))
    print(f"\nTask ID: {task_data.get('task_id', 'N/A')}")
    print(f"Type: {task_data.get('analysis_type', 'N/A')}")
    print(f"Status: {task_data.get('status', 'N/A')}")
    print(f"Created: {task_data.get('created_at', 'N/A')}")
    
    # Check for metadata/custom_options
    for field in ['metadata_json', 'custom_options']:
        if field in task_data and task_data[field]:
            try:
                data = json.loads(task_data[field])
                print(f"{field}: {json.dumps(data, indent=2)}")
            except:
                print(f"{field} (raw): {task_data[field]}")

conn.close()