"""Test generation API endpoint with model lookup fix."""
import requests
import json

# Test with a known model
payload = {
    'model_slug': 'anthropic_claude-4.5-haiku-20251001',
    'template_id': 1,
    'app_num': 999,
    'generate_frontend': False,
    'generate_backend': True
}

print('Testing generation API endpoint...')
print(f'Payload: {json.dumps(payload, indent=2)}\n')

try:
    response = requests.post('http://localhost:5000/api/gen/generate', json=payload, timeout=60)
    result = response.json()
    
    print(f'Status Code: {response.status_code}')
    print(f'Success: {result.get("success")}')
    print(f'Message: {result.get("message")}')
    
    if not result.get('success'):
        backend_error = result.get('backend_error', '')
        if backend_error:
            print(f'\nBackend Error:')
            # Show first 500 chars of error
            print(backend_error[:500])
            if 'not a valid model ID' in backend_error:
                print('\n✗ ISSUE: Still sending wrong model ID format to OpenRouter!')
            elif 'Model not found in database' in backend_error:
                print('\n✓ FIX WORKING: Database lookup is happening!')
            else:
                print('\n? Unknown error - check details above')
    else:
        print('\n✓ SUCCESS: Generation completed!')
        if result.get('backend_result'):
            print(f'  Backend: {result["backend_result"][:100]}...')
            
except Exception as e:
    print(f'\n✗ Request failed: {e}')
