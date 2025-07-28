import sqlite3
import json

db_path = 'src/data/thesis_app.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check what tables exist
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print('Tables in database:')
for table in tables:
    print(f'- {table[0]}')

# If port_configurations exists, check its contents
if any('port_configurations' in table for table in tables):
    cursor.execute('SELECT id, frontend_port, backend_port, metadata_json FROM port_configurations LIMIT 5')
    ports = cursor.fetchall()
    print('\nPort configurations:')
    for port in ports:
        metadata = json.loads(port[3]) if port[3] else {}
        model_name = metadata.get('model', 'NOT_SET')
        print(f'ID: {port[0]}, Frontend: {port[1]}, Backend: {port[2]}, Model: {model_name}')
    
    cursor.execute('SELECT COUNT(*) FROM port_configurations')
    count = cursor.fetchone()[0]
    print(f'\nTotal port configurations: {count}')

conn.close()
