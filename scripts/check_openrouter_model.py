"""Check if model exists on OpenRouter"""
import requests
import json

api_key = "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"

response = requests.get(
    "https://openrouter.ai/api/v1/models",
    headers={"Authorization": f"Bearer {api_key}"}
)

if response.status_code == 200:
    data = response.json()
    models = data.get('data', [])
    
    # Search for agentica or deepcoder models
    matches = [m for m in models if 'agentica' in m['id'].lower() or 'deepcoder' in m['id'].lower()]
    
    print(f"\n=== Found {len(matches)} matching models ===\n")
    for m in matches:
        print(f"ID: {m['id']}")
        print(f"Name: {m.get('name', 'N/A')}")
        print(f"Context: {m.get('context_length', 'N/A')}")
        print(f"RAW JSON: {json.dumps(m, indent=2)}")
        print()
else:
    print(f"Error: {response.status_code}")
    print(response.text)
