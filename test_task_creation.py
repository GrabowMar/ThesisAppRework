import requests

# Test POST to analysis creation endpoint
data = {
    'model_slug': 'nousresearch_hermes-4-405b',
    'app_number': '1',
    'analysis_mode': 'profile',
    'analysis_profile': 'security',
    'priority': 'normal'
}

response = requests.post('http://127.0.0.1:5000/analysis/create', data=data, allow_redirects=False)
print(f'Status: {response.status_code}')
print(f'Headers: {dict(response.headers)}')
if response.text:
    print(f'Response: {response.text[:500]}...' if len(response.text) > 500 else f'Response: {response.text}')