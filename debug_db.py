#!/usr/bin/env python3

import sys
sys.path.insert(0, 'src')
import sqlite3

# Check database structure
conn = sqlite3.connect('src/data/thesis_app.db')
cursor = conn.cursor()

print("Tables in database:")
result = cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in result.fetchall()]
for table in tables:
    print(f"  {table}")

if 'analysis_tasks' in tables:
    print("\nAnalysis types in database:")
    result = cursor.execute("SELECT DISTINCT analysis_type FROM analysis_tasks")
    for row in result.fetchall():
        print(f"  {row[0]}")
    
    print("\nTask count by analysis_type:")
    result = cursor.execute("SELECT analysis_type, COUNT(*) FROM analysis_tasks GROUP BY analysis_type")
    for row in result.fetchall():
        print(f"  {row[0]}: {row[1]}")

conn.close()