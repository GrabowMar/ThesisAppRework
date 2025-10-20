"""Test the EXACT free model ID from OpenRouter website"""
import requests
import json

api_key = "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"

print("Testing EXACT ID from OpenRouter website")
print("Model: agentica-org/deepcoder-14b-preview:free")
print("=" * 60)

response = requests.post(
    "https://openrouter.ai/api/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://thesis-research-platform.local",
        "X-Title": "Thesis Research Platform"
    },
    json={
        "model": "agentica-org/deepcoder-14b-preview:free",
        "messages": [
            {
                "role": "user",
                "content": "Write a simple Python function to add two numbers."
            }
        ],
        "max_tokens": 200
    }
)

print(f"Status Code: {response.status_code}")
print(f"\nResponse Body:")
print(json.dumps(response.json(), indent=2))

if response.status_code == 200:
    print("\n[SUCCESS] Model is working!")
    content = response.json().get('choices', [{}])[0].get('message', {}).get('content', '')
    print(f"\nGenerated Content:\n{content}")
else:
    print("\n[FAILED] Model returned error")
