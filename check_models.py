#!/usr/bin/env python3
"""Quick script to check available models in the database."""

import sqlite3
import json
from pathlib import Path

def check_models():
    db_path = Path("src/data/thesis_app.db")
    
    if not db_path.exists():
        print("❌ Database not found at src/data/thesis_app.db")
        return
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Check if ModelCapability table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='model_capabilities';")
        table_exists = cursor.fetchone()
        
        if not table_exists:
            print("❌ model_capabilities table not found in database")
            
            # Check what tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            print("📋 Available tables:")
            for table in tables:
                print(f"   - {table[0]}")
            
            conn.close()
            return
        
        # Get models from database
        cursor.execute("SELECT provider, model_name, canonical_slug FROM model_capabilities LIMIT 10;")
        models = cursor.fetchall()
        
        print(f"📊 Found {len(models)} models in database:")
        for provider, model_name, slug in models:
            print(f"   - {provider}/{model_name} ({slug})")
        
        # Check for popular models
        popular_models = ['claude-3-sonnet', 'claude-3.7-sonnet', 'gpt-4', 'gpt-4o', 'gemini-pro']
        print("\n🔍 Checking for popular models:")
        
        for model in popular_models:
            cursor.execute("SELECT COUNT(*) FROM model_capabilities WHERE canonical_slug LIKE ?;", (f"%{model}%",))
            count = cursor.fetchone()[0]
            status = "✅" if count > 0 else "❌"
            print(f"   {status} {model}: {count} matches")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error checking database: {e}")

if __name__ == "__main__":
    check_models()
