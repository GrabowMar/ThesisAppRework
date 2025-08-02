#!/usr/bin/env python3
"""
Check database URI being used
"""

import sys
sys.path.append('src')
from app import create_app

app = create_app()
print(f"Database URI: {app.config['SQLALCHEMY_DATABASE_URI']}")

# Extract the path
uri = app.config['SQLALCHEMY_DATABASE_URI']
if 'sqlite:///' in uri:
    db_path = uri.replace('sqlite:///', '')
    print(f"Database file path: {db_path}")
    
    import os
    if os.path.exists(db_path):
        print("✅ Database file exists")
        print(f"File size: {os.path.getsize(db_path)} bytes")
    else:
        print("❌ Database file not found")
