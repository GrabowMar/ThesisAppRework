#!/usr/bin/env python3
"""Database repair script for corrupted SQLite database.

This script attempts to:
1. Check database integrity
2. Backup the corrupted database
3. Export salvageable data to a new clean database
4. Optionally reinitialize if repair fails
"""

import sqlite3
import os
import shutil
from datetime import datetime
from pathlib import Path

def main():
    # Get paths
    project_root = Path(__file__).parent.parent
    db_path = project_root / 'src' / 'data' / 'thesis_app.db'
    backup_dir = project_root / 'src' / 'data' / 'backups'
    backup_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f'thesis_app_corrupted_{timestamp}.db'
    new_db_path = project_root / 'src' / 'data' / 'thesis_app_new.db'
    
    print(f"Database path: {db_path}")
    print(f"Database size: {db_path.stat().st_size / (1024*1024):.2f} MB")
    print()
    
    # Step 1: Check integrity
    print("=== Step 1: Checking database integrity ===")
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute('PRAGMA integrity_check')
        result = cursor.fetchall()
        print(f"Integrity check result: {result}")
        
        if result[0][0] == 'ok':
            print("Database integrity is OK!")
            print("The error might be transient. Try restarting the Flask app.")
            
            # Still try to vacuum/repair
            print("\nAttempting VACUUM to rebuild database...")
            try:
                cursor.execute('VACUUM')
                conn.commit()
                print("VACUUM completed successfully!")
            except Exception as e:
                print(f"VACUUM failed: {e}")
        
        conn.close()
    except Exception as e:
        print(f"Integrity check failed: {e}")
    
    # Step 2: List tables and count rows
    print("\n=== Step 2: Examining table contents ===")
    table_info = {}
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [t[0] for t in cursor.fetchall()]
        print(f"Tables found: {tables}")
        
        for table in tables:
            try:
                cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
                count = cursor.fetchone()[0]
                table_info[table] = {'count': count, 'ok': True}
                print(f"  {table}: {count} rows")
            except Exception as e:
                table_info[table] = {'count': 0, 'ok': False, 'error': str(e)}
                print(f"  {table}: ERROR - {e}")
        
        conn.close()
    except Exception as e:
        print(f"Failed to examine tables: {e}")
    
    # Step 3: Backup corrupted database
    print(f"\n=== Step 3: Backing up to {backup_path} ===")
    try:
        shutil.copy2(db_path, backup_path)
        print(f"Backup created: {backup_path}")
    except Exception as e:
        print(f"Backup failed: {e}")
    
    # Step 4: Ask user what to do
    print("\n=== Options ===")
    print("1. Try VACUUM repair (non-destructive)")
    print("2. Export data to new database (preserves most data)")
    print("3. Reinitialize database (LOSES ALL DATA)")
    print("4. Exit without changes")
    
    choice = input("\nEnter choice (1-4): ").strip()
    
    if choice == '1':
        print("\nRunning VACUUM...")
        try:
            conn = sqlite3.connect(str(db_path))
            conn.execute('VACUUM')
            conn.commit()
            conn.close()
            print("VACUUM completed! Try restarting Flask app.")
        except Exception as e:
            print(f"VACUUM failed: {e}")
    
    elif choice == '2':
        print("\nExporting data to new database...")
        export_to_new_db(db_path, new_db_path, table_info)
        print(f"\nNew database created at: {new_db_path}")
        print("To use it, rename it to thesis_app.db:")
        print(f"  mv {new_db_path} {db_path}")
    
    elif choice == '3':
        confirm = input("This will DELETE ALL DATA. Type 'yes' to confirm: ")
        if confirm.lower() == 'yes':
            print("\nReinitializing database...")
            os.remove(db_path)
            
            # Run init_db.py
            import subprocess
            result = subprocess.run(
                ['python', str(project_root / 'src' / 'init_db.py')],
                cwd=str(project_root),
                capture_output=True,
                text=True
            )
            print(result.stdout)
            if result.returncode != 0:
                print(f"Error: {result.stderr}")
            else:
                print("Database reinitialized successfully!")
        else:
            print("Cancelled.")
    
    else:
        print("Exiting without changes.")


def export_to_new_db(old_path: Path, new_path: Path, table_info: dict):
    """Export data from corrupted database to a new clean database."""
    if new_path.exists():
        os.remove(new_path)
    
    old_conn = sqlite3.connect(str(old_path))
    new_conn = sqlite3.connect(str(new_path))
    
    old_cursor = old_conn.cursor()
    new_cursor = new_conn.cursor()
    
    # Get schema
    old_cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL")
    schemas = old_cursor.fetchall()
    
    # Create tables in new database
    for (sql,) in schemas:
        try:
            new_cursor.execute(sql)
            print(f"Created table from: {sql[:50]}...")
        except Exception as e:
            print(f"Failed to create table: {e}")
    
    new_conn.commit()
    
    # Copy data table by table
    for table, info in table_info.items():
        if not info.get('ok'):
            print(f"Skipping corrupted table: {table}")
            continue
        
        try:
            old_cursor.execute(f'SELECT * FROM "{table}"')
            rows = old_cursor.fetchall()
            
            if rows:
                # Get column count
                old_cursor.execute(f'PRAGMA table_info("{table}")')
                columns = old_cursor.fetchall()
                placeholders = ','.join(['?' for _ in columns])
                
                new_cursor.executemany(
                    f'INSERT INTO "{table}" VALUES ({placeholders})',
                    rows
                )
                print(f"Copied {len(rows)} rows to {table}")
        except Exception as e:
            print(f"Failed to copy {table}: {e}")
    
    new_conn.commit()
    old_conn.close()
    new_conn.close()


if __name__ == '__main__':
    main()
