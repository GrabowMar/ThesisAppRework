#!/usr/bin/env python3
"""Test environment variable loading."""

import os
import sys
sys.path.insert(0, 'src')

print("=" * 80)
print("Environment Check")
print("=" * 80)

# Check if .env exists
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
print(f"Looking for .env at: {env_path}")
print(f".env exists: {os.path.exists(env_path)}")

# Check environment variable
key = os.environ.get('OPENROUTER_API_KEY', None)
if key:
    print(f"✅ OPENROUTER_API_KEY is set (length: {len(key)})")
    print(f"   First 20 chars: {key[:20]}...")
else:
    print("❌ OPENROUTER_API_KEY is NOT set")
    
# Try loading with python-dotenv
try:
    from dotenv import load_dotenv
    load_dotenv(env_path)
    key_after = os.environ.get('OPENROUTER_API_KEY', None)
    if key_after:
        print(f"✅ After load_dotenv: OPENROUTER_API_KEY is set (length: {len(key_after)})")
    else:
        print("❌ After load_dotenv: OPENROUTER_API_KEY still NOT set")
except Exception as e:
    print(f"⚠️  load_dotenv failed: {e}")

# Now test with app
print("\n" + "=" * 80)
print("Testing with Flask App")
print("=" * 80)

from app import create_app
app = create_app()

with app.app_context():
    key_in_app = os.environ.get('OPENROUTER_API_KEY', None)
    if key_in_app:
        print(f"✅ In app context: OPENROUTER_API_KEY is set")
    else:
        print("❌ In app context: OPENROUTER_API_KEY is NOT set")
