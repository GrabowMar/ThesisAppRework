#!/usr/bin/env python3

import sys
import sqlite3
sys.path.insert(0, 'src')

# Fix invalid COMPOSITE analysis_type entries
conn = sqlite3.connect('src/app/data/thesis_app.db')
cursor = conn.cursor()

# Update COMPOSITE to SECURITY
cursor.execute('UPDATE analysis_tasks SET analysis_type = "SECURITY" WHERE analysis_type = "COMPOSITE"')
conn.commit()
print(f'Updated {cursor.rowcount} tasks with COMPOSITE type to SECURITY')

# Check for any other invalid enum values
cursor.execute('SELECT DISTINCT analysis_type FROM analysis_tasks')
analysis_types = [row[0] for row in cursor.fetchall()]
print(f'Current analysis types in database: {analysis_types}')

conn.close()
print('Database fix completed')