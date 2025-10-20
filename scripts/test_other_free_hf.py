"""Find and test another free HuggingFace model"""
import requests
import json

api_key = "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"

# Get all models
r = requests.get(
    'https://openrouter.ai/api/v1/models',
    headers={'Authorization': f'Bearer {api_key}'}
)

models = r.json()['data']

# Find free HuggingFace models (not agentica)
free_hf = [
    m for m in models 
    if m.get('pricing', {}).get('prompt') == '0' 
    and m.get('hugging_face_id')
    and 'agentica' not in m['id'].lower()
][:10]

print("Free HuggingFace Models:\n")
for m in free_hf:
    print(f"{m['id']}")
    print(f"  HF ID: {m.get('hugging_face_id')}")
    print(f"  Context: {m.get('context_length')}")
    print()

# Test the first one
if free_hf:
    test_model = free_hf[0]
    print(f"\n=== Testing: {test_model['id']} ===\n")
    
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://thesis-research-platform.local",
            "X-Title": "Thesis Research Platform"
        },
        json={
            "model": test_model['id'],
            "messages": [{"role": "user", "content": "Say hello"}],
            "max_tokens": 50
        }
    )
    
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        print("[SUCCESS] Model works!")
        content = response.json()['choices'][0]['message']['content']
        print(f"Response: {content}")
    else:
        print(f"[FAILED] Error: {response.json()}")
