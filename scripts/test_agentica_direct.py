"""Test if agentica model actually works on OpenRouter"""
import requests

api_key = "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"

# Test 1: Lowercase (should fail)
print("=== Test 1: Lowercase ID ===")
response1 = requests.post(
    "https://openrouter.ai/api/v1/chat/completions",
    headers={"Authorization": f"Bearer {api_key}"},
    json={
        "model": "agentica-org/deepcoder-14b-preview",
        "messages": [{"role": "user", "content": "Hello"}],
        "max_tokens": 10
    }
)
print(f"Status: {response1.status_code}")
print(f"Response: {response1.json()}\n")

# Test 2: Proper case (should work?)
print("=== Test 2: Proper Case ID ===")
response2 = requests.post(
    "https://openrouter.ai/api/v1/chat/completions",
    headers={"Authorization": f"Bearer {api_key}"},
    json={
        "model": "agentica-org/DeepCoder-14B-Preview",
        "messages": [{"role": "user", "content": "Hello"}],
        "max_tokens": 10
    }
)
print(f"Status: {response2.status_code}")
print(f"Response: {response2.json()}\n")

# Test 3: Free variant
print("=== Test 3: Free Variant ===")
response3 = requests.post(
    "https://openrouter.ai/api/v1/chat/completions",
    headers={"Authorization": f"Bearer {api_key}"},
    json={
        "model": "agentica-org/deepcoder-14b-preview:free",
        "messages": [{"role": "user", "content": "Hello"}],
        "max_tokens": 10
    }
)
print(f"Status: {response3.status_code}")
print(f"Response: {response3.json()}")
