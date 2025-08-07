#!/usr/bin/env python3
"""List all real models in the database."""

import sqlite3
from pathlib import Path

def list_all_models():
    db_path = Path("src/data/thesis_app.db")
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        cursor.execute("SELECT provider, model_name, canonical_slug FROM model_capabilities ORDER BY provider, model_name;")
        models = cursor.fetchall()
        
        print(f"📊 All {len(models)} models in database:")
        for provider, model_name, slug in models:
            print(f"   - {provider}/{model_name} ({slug})")
        
        # Group by provider
        print("\n📋 Models by provider:")
        providers = {}
        for provider, model_name, slug in models:
            if provider not in providers:
                providers[provider] = []
            providers[provider].append((model_name, slug))
        
        for provider, model_list in providers.items():
            print(f"\n{provider}:")
            for model_name, slug in model_list:
                print(f"   - {model_name} ({slug})")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    list_all_models()
