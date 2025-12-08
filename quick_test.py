#!/usr/bin/env python
"""Quick test to verify app_number is returned in generation response."""
import requests
import json

API_BASE = "http://localhost:5000"
TOKEN = "8RRBq32-tP0ZyXUc1uCdVd9xmRaCpnbLmkPRd-FagTWZf3lb0JIlT7gSve8NDxEQ"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

print("Testing generation API app_number fix...")
print("=" * 50)

# Step 1: Health check
print("\n1. Health check...")
try:
    r = requests.get(f"{API_BASE}/api/health", timeout=5)
    print(f"   Status: {r.status_code}")
except Exception as e:
    print(f"   ERROR: {e}")
    exit(1)

# Step 2: Generate a small app
print("\n2. Generating test app (this may take 1-2 minutes)...")
payload = {
    "model_slug": "cohere/command-r7b-12-2024",
    "template_slug": "crud_todo_list",
    "generate_frontend": True,
    "generate_backend": True
}

try:
    r = requests.post(
        f"{API_BASE}/api/gen/generate",
        headers=headers,
        json=payload,
        timeout=300
    )
    print(f"   Status: {r.status_code}")
    
    if r.status_code == 200:
        data = r.json().get("data", {})
        print(f"\n3. Response fields:")
        print(f"   success: {data.get('success')}")
        print(f"   app_number: {data.get('app_number')}")
        print(f"   app_num: {data.get('app_num')}")
        print(f"   app_dir: {data.get('app_dir')}")
        print(f"   model_slug: {data.get('model_slug')}")
        print(f"   template_slug: {data.get('template_slug')}")
        print(f"   backend_port: {data.get('backend_port')}")
        print(f"   frontend_port: {data.get('frontend_port')}")
        
        if data.get('app_number'):
            print("\n✅ FIX VERIFIED: app_number is now returned!")
        else:
            print("\n❌ FIX FAILED: app_number is still missing!")
    else:
        print(f"   Error: {r.text[:500]}")

except Exception as e:
    print(f"   ERROR: {e}")

print("\n" + "=" * 50)
print("Test complete.")
