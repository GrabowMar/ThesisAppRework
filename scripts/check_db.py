#!/usr/bin/env python3
"""Check SQLite database corruption and attempt recovery."""
import sqlite3
import os

DB_PATH = '/app/src/data/thesis_app.db'
BACKUP_PATH = '/app/src/data/thesis_app.db.bak'
NEW_PATH = '/app/src/data/thesis_app_new.db'

def check_db():
    print(f"Checking database at {DB_PATH}")
    print(f"File exists: {os.path.exists(DB_PATH)}")
    print(f"File size: {os.path.getsize(DB_PATH)} bytes")
    
    # Try to connect and check integrity
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.execute("PRAGMA integrity_check")
        result = cursor.fetchall()
        print(f"Integrity check: {result}")
    except Exception as e:
        print(f"Integrity check failed: {e}")
    
    # Try to list tables
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"Tables found: {tables}")
    except Exception as e:
        print(f"Table listing failed: {e}")
    
    # Try quick_check pragma
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.execute("PRAGMA quick_check")
        result = cursor.fetchall()
        print(f"Quick check: {result}")
    except Exception as e:
        print(f"Quick check failed: {e}")

if __name__ == "__main__":
    check_db()
