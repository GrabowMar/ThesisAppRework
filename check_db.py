import sqlite3
conn = sqlite3.connect('C:/Users/grabowmar/Desktop/ThesisAppRework/src/data/thesis_app.db')
cursor = conn.cursor()

# List tables
cursor.execute('SELECT name FROM sqlite_master WHERE type="table"')
tables = [t[0] for t in cursor.fetchall()]
print(f'Tables ({len(tables)}): {", ".join(tables)}')

# Check for generated_applications
if 'generated_applications' in tables:
    cursor.execute('SELECT COUNT(*) FROM generated_applications')
    count = cursor.fetchone()[0]
    print(f'\n✅ Apps in database: {count}')
    
    if count > 0:
        cursor.execute('SELECT model_slug, app_number FROM generated_applications ORDER BY model_slug, app_number')
        apps = cursor.fetchall()
        print('\nApps:')
        for slug, num in apps:
            print(f'  {slug} app{num}')
else:
    print('\n❌ generated_applications table not found!')

conn.close()
