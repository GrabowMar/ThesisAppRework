import requests
import json

BASE_URL = 'http://localhost:5000'
TOKEN = 'WCVNOZZ125gzTx_Z1F6pjnW34JIWqYLyh9xTytVbaJnTUfXYFrir2EJcadpYgelI'

headers = {'Authorization': f'Bearer {TOKEN}'}

# Check applications
r = requests.get(f'{BASE_URL}/api/applications', headers=headers)
print(f'Status: {r.status_code}')

if r.status_code == 200:
    data = r.json()
    apps = data.get('applications', [])
    print(f'\nFound {len(apps)} applications:')
    for app in apps[:15]:
        print(f"  - {app['model_slug']}/app{app['app_number']}")
else:
    print(f'Error: {r.text[:200]}')
