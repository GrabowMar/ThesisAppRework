#!/usr/bin/env python3
"""
Check database content directly
"""

import sqlite3

conn = sqlite3.connect('src/data/thesis_app.db')
cursor = conn.cursor()

# Check if table exists
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='model_capabilities'")
table_exists = cursor.fetchone()

if table_exists:
    print('✅ model_capabilities table exists')
    
    # Count records
    cursor.execute('SELECT COUNT(*) FROM model_capabilities')
    count = cursor.fetchone()[0]
    print(f'📊 Total models in database: {count}')
    
    if count > 0:
        # Show sample records  
        cursor.execute('SELECT canonical_slug, model_name, provider FROM model_capabilities LIMIT 5')
        models = cursor.fetchall()
        print('📋 Sample models:')
        for slug, name, provider in models:
            print(f'  - {slug} | {name} | {provider}')
    else:
        print('❌ Table is empty!')
else:
    print('❌ model_capabilities table does not exist')

conn.close()
