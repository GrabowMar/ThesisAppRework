import sqlite3
import os

db_path = 'data/thesis_app.db'
if os.path.exists(db_path):
    print(f'Database exists at: {os.path.abspath(db_path)}')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if table exists
    cursor.execute('SELECT name FROM sqlite_master WHERE type="table" AND name="generated_applications"')
    table_exists = cursor.fetchone()
    print(f'Table exists: {bool(table_exists)}')
    
    if table_exists:
        cursor.execute('SELECT COUNT(*) FROM generated_applications')
        count = cursor.fetchone()[0]
        print(f'Records in generated_applications: {count}')
        
        # Show first few records
        cursor.execute('SELECT model_slug, app_number, app_type FROM generated_applications LIMIT 5')
        records = cursor.fetchall()
        print('First 5 records:')
        for record in records:
            print(f'  {record[0]}/app{record[1]} - {record[2]}')
    
    conn.close()
else:
    print(f'Database does not exist at: {os.path.abspath(db_path)}')
